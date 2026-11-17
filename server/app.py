"""Mapa domácí sítě: malý server pro NAS (Docker, např. Synology).

Spuštění serveru:  uvicorn app:app --host 0.0.0.0 --port 8780
Nastavení účtu:    python app.py passwd | python app.py 2fa on | python app.py 2fa off
Ukázková síť:      python app.py demo [cs|en]
Jazyk příkazové řádky: NETMAP_LANG=cs|en, jinak podle LANG (cs/sk = čeština, jinak angličtina).

Návrh je v docs/nas.md. Server data nikdy sám nemění: network.md generuje prohlížeč.
Data jsou po objektech (dům, chata…): data/<id>/ s vlastními soubory a zálohami.
"""

import base64
import getpass
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# ---------- konstanty ----------

ROOT = Path(os.environ.get('NETMAP_ROOT', Path(__file__).resolve().parent.parent))
WWW = Path(os.environ.get('NETMAP_WWW', ROOT / 'www'))
DATA = Path(os.environ.get('NETMAP_DATA', ROOT / 'data'))
CONFIG = Path(os.environ.get('NETMAP_CONFIG', ROOT / 'config'))
AUTH = CONFIG / 'auth.json'
SESSIONS = CONFIG / 'sessions.json'

FILES = {'net': 'network.json', 'lay': 'layout.json', 'md': 'network.md'}
COOKIE = 'netmap_s'
SESSION_DAYS = 30
BACKUP_IDLE = 30 * 60       # záloha jen na začátku úprav: když se data aspoň 30 minut neměnila
BACKUP_KEEP = 4             # nechávají se 4 nejnovější zálohy
MAX_BODY = 20 * 1024 * 1024
FAILS_FREE = 5              # po 5 špatných pokusech se čeká
FAIL_WAIT = 60              # 1 minutu, s každou další chybou dvakrát déle
STAMP = '%Y-%m-%d_%H%M%S'
SCAN_LAST = DATA / 'scan' / 'last.json'
NMAP = os.environ.get('NETMAP_NMAP', 'nmap')  # jiná cesta jen pro test (falešný nmap)
SCAN_TIMEOUT = 300
SCAN_MAX = 1024             # největší skenovaná síť (/22), ať se omylem neskenuje celé /8
META = 'meta.json'          # {name, desc, nas, img} objektu
OBJ_RE = re.compile(r'[a-z0-9][a-z0-9-]{0,39}')  # id objektu = název složky v data/
DELETED = DATA / '_deleted'  # smazané objekty (jdou ručně vrátit ve File Station)
NAME_MAX = 60
DESC_MAX = 300
IMG_MAX = 500_000           # vlastní obrázek náhledu (data URL, editor ho zmenší na 800 px), '' = náhled z topologie
IMG_RE = re.compile(r'data:image/(webp|png|jpeg);base64,[A-Za-z0-9+/=]+')
LANGS = ('cs', 'en')         # jazyky stránek a ukázky; editor posílá ruční volbu v cookie LANG_COOKIE
LANG_COOKIE = 'netmapLang'
FIRST = {'cs': 'Domov', 'en': 'Home'}  # první objekt (převod dat z doby před objekty jde vždy do „Domov“)
DEMO = Path(os.environ.get('NETMAP_DEMO', ROOT / 'ukazka'))  # fiktivní síť pro objekt „Ukázka“, anglická vedle s -en
DEMO_NAME = {'cs': 'Ukázka', 'en': 'Demo'}
DEMO_DESC = {'cs': 'Fiktivní síť na vyzkoušení editoru', 'en': 'Fictional network to try out the editor'}

# ---------- pomocné funkce ----------


def lang_of(cookie, accept):
    """Jazyk stránky: ruční volba z editoru (cookie), jinak první jazyk prohlížeče
    (Accept-Language podle q; cs/sk = čeština, jinak angličtina), stejně jako editor."""
    if cookie in LANGS:
        return cookie
    best, bq = '', -1.0
    for part in (accept or '').split(','):
        tag, _, q = part.strip().partition(';q=')
        try:
            q = float(q) if q else 1.0
        except ValueError:
            continue
        if tag and q > bq:
            best, bq = tag.lower(), q
    return 'cs' if re.match(r'(cs|sk)(-|$)', best) else 'en'


# jazyk příkazové řádky
CLI_LANG = lang_of(os.environ.get('NETMAP_LANG'), os.environ.get('LANG', '').split('.')[0].replace('_', '-'))


def tl(cs, en):
    """Hláška příkazové řádky v jejím jazyce."""
    return cs if CLI_LANG == 'cs' else en


def read_text(p):
    try:
        return p.read_text(encoding='utf-8')
    except FileNotFoundError:
        return None


def write_atomic(p, text):
    """Zápis přes *.tmp a os.replace: výpadek uprostřed zápisu soubor nepoškodí."""
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def read_json(p, default):
    t = read_text(p)
    return json.loads(t) if t else default


def write_json(p, obj):
    write_atomic(p, json.dumps(obj, ensure_ascii=False, indent=1))


def rev_of(net, lay):
    """Verze dat = otisk obsahu, takže nepotřebuje žádný další stav."""
    return hashlib.sha256((net + '\0' + (lay or '')).encode()).hexdigest()[:16]


# ---------- heslo a TOTP ----------


def pw_hash(pw, salt=None):
    salt = salt or secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f'scrypt$16384$8$1${salt.hex()}${h.hex()}'


def pw_check(pw, stored):
    try:
        _, n, r, p, salt, h = stored.split('$')
        got = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=len(h) // 2)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got.hex(), h)


def totp(secret, step):
    """RFC 6238: HMAC-SHA1, 30 s, 6 číslic."""
    key = base64.b32decode(secret + '=' * (-len(secret) % 8))
    d = hmac.new(key, struct.pack('>Q', step), hashlib.sha1).digest()
    o = d[-1] & 15
    return '%06d' % ((struct.unpack('>I', d[o:o + 4])[0] & 0x7FFFFFFF) % 1_000_000)


def totp_step(secret, code, now=None):
    """Krok, ve kterém kód platí (tolerance ±1 krok), jinak None."""
    code = (code or '').replace(' ', '')
    t = int((now or time.time()) // 30)
    for s in (t, t - 1, t + 1):
        if hmac.compare_digest(totp(secret, s), code):
            return s
    return None


def auth():
    return read_json(AUTH, None)


# ---------- relace ----------
# V souboru je jen otisk tokenu (sha256), samotný token zná jen cookie prohlížeče.
# Soubor se znovu načte, když se změní (např. `passwd` z příkazové řádky odhlásí všechny).

_lock = threading.Lock()
_sess = {'mtime': None, 'map': {}}


def _sessions():
    m = SESSIONS.stat().st_mtime if SESSIONS.exists() else None
    if m != _sess['mtime']:
        _sess['map'] = read_json(SESSIONS, {})
        _sess['mtime'] = m
    now = time.time()
    return {k: v for k, v in _sess['map'].items() if v > now}


def _sessions_save(s):
    write_json(SESSIONS, s)
    _sess['map'] = s
    _sess['mtime'] = SESSIONS.stat().st_mtime


def tok_key(tok):
    return hashlib.sha256(tok.encode()).hexdigest()


def session_new():
    tok = secrets.token_urlsafe(32)
    with _lock:
        s = _sessions()
        s[tok_key(tok)] = time.time() + SESSION_DAYS * 86400
        _sessions_save(s)
    return tok


def session_ok(tok):
    if not tok:
        return False
    with _lock:
        return tok_key(tok) in _sessions()


def session_end(tok):
    with _lock:
        s = _sessions()
        if s.pop(tok_key(tok or ''), None):
            _sessions_save(s)


# ---------- objekty ----------
# Každý objekt má složku data/<id>/: network.json, layout.json, network.md, meta.json a backup/.
# id vznikne z názvu a už se nemění; přejmenování mění jen meta.json (editor má podle id
# uložené věci v localStorage). Ve složce data/ jsou kromě objektů jen scan/ a _deleted/.

_obj_lock = threading.Lock()
_dev_n = {}  # cesta → (mtime, počet zařízení), ať se network.json nečte při každém výpisu


def obj_dir(oid):
    """Složka existujícího objektu, jinak None. id jen podle OBJ_RE, takže žádná cesta mimo data/."""
    if not isinstance(oid, str) or not OBJ_RE.fullmatch(oid):
        return None
    d = DATA / oid
    return d if (d / META).is_file() else None


def obj_meta(d):
    m = read_json(d / META, {})
    return {'name': m.get('name') or d.name, 'desc': m.get('desc', ''), 'nas': bool(m.get('nas')), 'img': m.get('img', '')}


def obj_dirs():
    if not DATA.exists():
        return []
    return [d for d in DATA.iterdir() if obj_dir(d.name)]


def nas_obj():
    """Objekt označený „tady je NAS“ (jen ten smí skenovat), jinak None."""
    return next((d for d in obj_dirs() if obj_meta(d)['nas']), None)


def dev_count(d):
    p = d / FILES['net']
    try:
        m = p.stat().st_mtime
    except FileNotFoundError:
        return 0
    if _dev_n.get(p, (None,))[0] != m:
        try:
            n = len(json.loads(read_text(p)).get('devices') or [])
        except (ValueError, AttributeError, TypeError):
            n = 0
        _dev_n[p] = (m, n)
    return _dev_n[p][1]


def obj_info(d):
    """Údaje pro přehled objektů. changed = poslední uložení dat (u prázdného objektu založení)."""
    ts = [(d / FILES[k]).stat().st_mtime for k in ('net', 'lay') if (d / FILES[k]).exists()]
    changed = max(ts) if ts else (d / META).stat().st_mtime
    return {'id': d.name, **obj_meta(d), 'devices': dev_count(d),
            'changed': datetime.fromtimestamp(changed).isoformat(timespec='seconds')}


def objects():
    """Všechny objekty: nejdřív ten s NAS, pak podle názvu."""
    out = [obj_info(d) for d in obj_dirs()]
    out.sort(key=lambda o: (not o['nas'], o['name'].casefold()))
    return out


def slug(name):
    """Název → id: bez diakritiky, malá písmena, místo mezer pomlčky („Chata Lipno“ → chata-lipno).
    Obsazené id (i scan/ nebo jiná složka) dostane číslo: chata-2."""
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')[:30].strip('-') or 'objekt'
    oid, i = s, 2
    while (DATA / oid).exists():
        oid = f'{s}-{i}'
        i += 1
    return oid


def clean_meta(b):
    """Kontrola polí z editoru: name 1–60 znaků, desc nejvýš 300, nas ano/ne, img = data URL obrázku
    nebo ''. Chyba = ValueError."""
    m = {}
    if 'name' in b:
        m['name'] = b['name'].strip() if isinstance(b['name'], str) else ''
        if not 0 < len(m['name']) <= NAME_MAX:
            raise ValueError('name')
    if 'desc' in b:
        m['desc'] = b['desc'].strip() if isinstance(b['desc'], str) else None
        if m['desc'] is None or len(m['desc']) > DESC_MAX:
            raise ValueError('desc')
    if 'nas' in b:
        if not isinstance(b['nas'], bool):
            raise ValueError('nas')
        m['nas'] = b['nas']
    if 'img' in b:
        m['img'] = b['img'] if isinstance(b['img'], str) else None
        if m['img'] is None or len(m['img']) > IMG_MAX or (m['img'] and not IMG_RE.fullmatch(m['img'])):
            raise ValueError('img')
    return m


def obj_set(d, m):
    """Zapíše změny do meta.json. NAS může být jen v jednom objektu, ostatním se značka smaže."""
    if m.get('nas'):
        for o in obj_dirs():
            if o != d and obj_meta(o)['nas']:
                write_json(o / META, {**obj_meta(o), 'nas': False})
    write_json(d / META, {**obj_meta(d), **m})


def obj_new(name, desc='', nas=False, files=(), texts=None):
    """Nový objekt; složka vznikne celá najednou (přes .tmp a os.replace). files = soubory
    a složky, které se do něj přesunou (převod starých dat), texts = {název souboru: obsah}."""
    oid = slug(name)
    tmp = DATA / f'.{oid}.tmp'
    tmp.mkdir(parents=True, exist_ok=True)  # po výpadku uprostřed převodu v ní už část dat je, nemazat
    write_json(tmp / META, {'name': name, 'desc': desc, 'nas': False})
    for f in files:
        if f.exists():
            os.replace(f, tmp / f.name)
    for n, t in (texts or {}).items():
        write_atomic(tmp / n, t)
    os.replace(tmp, DATA / oid)
    if nas:
        obj_set(DATA / oid, {'nas': True})
    return DATA / oid


def obj_delete(d):
    """Objekt se nemaže, jen přesune do data/_deleted/<id>_<čas>/."""
    DELETED.mkdir(parents=True, exist_ok=True)
    os.replace(d, DELETED / f'{d.name}_{datetime.now().strftime(STAMP)}')


def demo_dir(lang):
    """Složka ukázky v jazyce: ukazka/ (čeština), ukazka-en/ (angličtina); chybějící = česká."""
    d = DEMO if lang == 'cs' else DEMO.with_name(f'{DEMO.name}-{lang}')
    return d if (d / FILES['net']).exists() else DEMO


def demo_new(lang='cs'):
    """Objekt „Ukázka“ / „Demo“ s fiktivní sítí ze složky ukázky. Když složka chybí, vrátí None."""
    src = demo_dir(lang)
    texts = {n: read_text(src / n) for n in FILES.values()}
    if not texts[FILES['net']]:
        return None
    return obj_new(DEMO_NAME[lang], desc=DEMO_DESC[lang], texts={n: x for n, x in texts.items() if x})


_fresh = False  # prázdný server: první objekty se založí až v jazyce prvního, kdo otevře přehled


def fresh_start(lang):
    """Na prázdném serveru (po startu) založí prázdný „Domov“ s NAS a ukázku v jazyce lang."""
    global _fresh
    with _obj_lock:
        if not _fresh:
            return
        _fresh = False
        if obj_dirs():
            return
        obj_new(FIRST[lang], nas=True)
        demo_new(lang)


def migrate():
    """Při startu: data z doby před objekty (data/network.json, layout.json, network.md, backup/)
    se přesunou do prvního objektu „Domov“ s NAS. Prázdný server dostane prázdný „Domov“ a k němu
    objekt „Ukázka“ až při prvním otevření přehledu (fresh_start), aby byly v jazyce prohlížeče."""
    global _fresh
    with _obj_lock:
        if obj_dirs():
            return
        DATA.mkdir(parents=True, exist_ok=True)
        old = [DATA / n for n in FILES.values()] + [DATA / 'backup']
        if any(f.exists() for f in old):
            obj_new(FIRST['cs'], nas=True, files=old)
        else:
            _fresh = True


# ---------- zálohy ----------
# Každý objekt má vlastní zálohy v data/<id>/backup/<čas>/; o = složka objektu.


def backups(o):
    bk = o / 'backup'
    if not bk.exists():
        return []
    out = []
    for d in sorted(bk.iterdir(), reverse=True):
        try:
            at = datetime.strptime(d.name, STAMP)
        except ValueError:
            continue
        size = sum(f.stat().st_size for f in d.iterdir() if f.is_file())
        out.append({'id': d.name, 'at': at.isoformat(timespec='seconds'), 'size': size})
    return out


def backup_prune(o):
    """Nechá BACKUP_KEEP nejnovějších záloh, starší smaže."""
    for b in backups(o)[BACKUP_KEEP:]:  # backups() je od nejnovější
        shutil.rmtree(o / 'backup' / b['id'], ignore_errors=True)


def backup_same(o, bid):
    """Záloha má stejná data (network.json a layout.json) jako současná verze."""
    return all(read_text(o / 'backup' / bid / FILES[k]) == read_text(o / FILES[k]) for k in ('net', 'lay'))


def backup_maybe(o, force=False):
    """Zkopíruje současnou (= předchozí) verzi na začátku úprav, tj. když se data aspoň
    BACKUP_IDLE neměnila (editor ukládá po každé změně, takže jedny úpravy = jedna záloha).
    force = vždy, např. před obnovou zálohy z editoru. Vrací id zálohy, nebo None."""
    if not (o / FILES['net']).exists():
        return None
    now = datetime.now()
    changed = max((o / FILES[k]).stat().st_mtime for k in ('net', 'lay') if (o / FILES[k]).exists())
    if not force and now.timestamp() - changed < BACKUP_IDLE:
        return None
    last = backups(o)
    if last and backup_same(o, last[0]['id']):  # beze změny od poslední zálohy: nová by byla jen kopie
        return last[0]['id']
    d = o / 'backup' / now.strftime(STAMP)
    if d.exists():  # dvě zálohy v jedné sekundě: stačí ta první
        return d.name
    tmp = o / 'backup' / ('.' + d.name)
    tmp.mkdir(parents=True, exist_ok=True)
    for name in FILES.values():
        if (o / name).exists():
            shutil.copy2(o / name, tmp / name)
    os.replace(tmp, d)
    backup_prune(o)
    return d.name


# ---------- sken sítě ----------
# Jen ručně z editoru, jeden najednou. nmap -sn (ping sken): ve vlastní síti NAS jde přes ARP,
# takže vrátí i MAC a výrobce. Párování s mapou dělá editor (zná strom, VLANy a typy zařízení).

_scan = {'state': 'idle'}
_scan_lock = threading.Lock()


def default_net():
    """Síť NAS (/24) podle adresy, ze které jde provoz ven. Nic se neposílá, UDP connect jen vybere rozhraní."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('192.0.2.1', 9))
            ip = s.getsockname()[0]
    except OSError:
        return []
    return [str(ipaddress.ip_network(ip + '/24', strict=False))]


def scan_nets():
    """SCAN_NETS = sítě oddělené čárkou nebo mezerou; jen platné IPv4 sítě, nejvýš /22 (1024 adres)."""
    raw = os.environ.get('SCAN_NETS', '').replace(',', ' ').split()
    nets = []
    for n in raw:
        try:
            net = ipaddress.ip_network(n, strict=False)
        except ValueError:
            continue
        if net.version == 4 and net.num_addresses <= SCAN_MAX:
            nets.append(str(net))
    return nets or default_net()


def parse_nmap(xml):
    """XML z nmap -oX → [{ip, mac, vendor, name}] jen pro zařízení, která odpověděla."""
    hosts = []
    for h in ET.fromstring(xml).iter('host'):
        st = h.find('status')
        if st is None or st.get('state') != 'up':
            continue
        r = {}
        for a in h.iter('address'):
            if a.get('addrtype') == 'ipv4':
                r['ip'] = a.get('addr')
            elif a.get('addrtype') == 'mac':
                r['mac'] = a.get('addr', '').lower()
                if a.get('vendor'):
                    r['vendor'] = a.get('vendor')
        hn = h.find('hostnames/hostname')
        if hn is not None and hn.get('name'):
            r['name'] = hn.get('name')
        if r.get('ip'):
            hosts.append(r)
    hosts.sort(key=lambda r: ipaddress.ip_address(r['ip']))
    return hosts


def scan_run(nets):
    """Běží ve vlákně. Výsledek (i chyba) jde do data/scan/last.json, ať ho editor najde i po obnovení."""
    at = datetime.now().isoformat(timespec='seconds')
    res = {'at': at, 'nets': nets, 'hosts': []}
    t = time.time()
    try:
        p = subprocess.run([NMAP, '-sn', '-oX', '-', *nets], capture_output=True, text=True, timeout=SCAN_TIMEOUT)
        if p.returncode:
            raise RuntimeError(p.stderr.strip()[:300] or f'nmap skončil s kódem {p.returncode}')
        res['hosts'] = parse_nmap(p.stdout)
    except FileNotFoundError:
        res['error'] = 'nmap není nainstalovaný'
    except subprocess.TimeoutExpired:
        res['error'] = f'sken trval déle než {SCAN_TIMEOUT} s'
    except (RuntimeError, ET.ParseError) as e:
        res['error'] = str(e)
    res['secs'] = round(time.time() - t, 1)
    write_json(SCAN_LAST, res)
    with _scan_lock:
        _scan.clear()
        _scan['state'] = 'idle'


def scan_start():
    """False = sken už běží."""
    with _scan_lock:
        if _scan.get('state') == 'running':
            return False
        nets = scan_nets()
        _scan.update(state='running', since=datetime.now().isoformat(timespec='seconds'), nets=nets)
    threading.Thread(target=scan_run, args=(nets,), daemon=True).start()
    return True


def scan_state():
    with _scan_lock:
        s = dict(_scan)
    if s['state'] == 'idle':
        s.update(read_json(SCAN_LAST, {}))
        s.setdefault('nets', scan_nets())
    return s


# ---------- ochrana proti hádání hesla ----------

_fails = {}  # ip → [počet chyb, do kdy se čeká]


def wait_left(ip):
    f = _fails.get(ip)
    return max(0, int(f[1] - time.time()) + 1) if f and f[1] > time.time() else 0


def fail(ip):
    n = _fails.get(ip, [0, 0])[0] + 1
    _fails[ip] = [n, time.time() + FAIL_WAIT * 2 ** (n - FAILS_FREE) if n >= FAILS_FREE else 0]


# ---------- aplikace ----------
# FastAPI se importuje až tady, aby `python app.py passwd` fungoval i bez něj.

if __name__ != '__main__':
    from fastapi import FastAPI, Request
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    _data_lock = threading.Lock()
    _used_steps = {}  # poslední použitý krok TOTP (kód nejde použít dvakrát)

    def client_ip(req):
        """Za reverzní proxy DSM (spojení z localhostu) platí X-Forwarded-For."""
        ip = req.client.host if req.client else ''
        if ip in ('127.0.0.1', '::1') and req.headers.get('x-forwarded-for'):
            ip = req.headers['x-forwarded-for'].split(',')[-1].strip()
        return ip

    def is_https(req):
        if req.url.scheme == 'https':
            return True
        local = req.client and req.client.host in ('127.0.0.1', '::1')
        return bool(local and req.headers.get('x-forwarded-proto') == 'https')

    def req_lang(req):
        return lang_of(req.cookies.get(LANG_COOKIE), req.headers.get('accept-language'))

    def err(code, msg, **kw):
        return JSONResponse({'error': msg, **kw}, status_code=code)

    PUBLIC = {'/api/health', '/api/login', '/api/logout'}

    @app.middleware('http')
    async def guard(req: Request, call_next):
        """Bez účtu jen nastavovací hláška, bez relace přihlašovací stránka (API vrací 401)."""
        p = req.url.path
        api = p.startswith('/api/')
        if p in PUBLIC:
            return await call_next(req)
        if not auth():
            return err(503, 'setup') if api else HTMLResponse(SETUP_HTML[req_lang(req)], status_code=503)
        if not session_ok(req.cookies.get(COOKIE)):
            if api:
                return err(401, 'login')
            return HTMLResponse(LOGIN_HTML[req_lang(req)], status_code=401, headers={'Cache-Control': 'no-store'})
        return await call_next(req)

    @app.middleware('http')
    async def headers(req: Request, call_next):
        r = await call_next(req)
        r.headers.setdefault('Cache-Control', 'no-store')
        r.headers['X-Content-Type-Options'] = 'nosniff'
        r.headers['X-Frame-Options'] = 'DENY'
        r.headers['Referrer-Policy'] = 'no-referrer'
        return r

    @app.get('/api/health')
    def health():
        return {'app': 'netmap', 'ok': True}

    @app.get('/')
    def index(req: Request):
        f = WWW / 'mapa.html'
        if not f.exists():
            return HTMLResponse('Chybí www/mapa.html' if req_lang(req) == 'cs' else 'Missing www/mapa.html', status_code=500)
        return FileResponse(f, media_type='text/html; charset=utf-8', headers={'Cache-Control': 'no-cache'})

    @app.get('/mapa.html')
    def index_alias():
        return Response(status_code=302, headers={'Location': './'})

    # ---------- přihlášení ----------

    @app.post('/api/login')
    async def login(req: Request):
        a = auth()
        if not a:
            return err(503, 'setup')
        ip = client_ip(req)
        w = wait_left(ip)
        if w:
            return err(429, 'wait', wait=w)
        try:
            b = await req.json()
            user, pw, code = str(b.get('user', '')), str(b.get('pass', '')), b.get('code')
        except (ValueError, AttributeError):
            return err(400, 'bad request')
        ok = hmac.compare_digest(user.encode(), a['user'].encode()) & pw_check(pw, a['hash'])
        if ok and a.get('totp'):
            if not code:
                return {'need': 'code'}
            s = totp_step(a['totp'], str(code))
            ok = s is not None and s > _used_steps.get(a['user'], -1)
            if ok:
                _used_steps[a['user']] = s
        if not ok:
            fail(ip)
            w = wait_left(ip)
            return err(401, 'wrong', **({'wait': w} if w else {}))
        _fails.pop(ip, None)
        r = JSONResponse({'ok': True})
        r.set_cookie(COOKIE, session_new(), max_age=SESSION_DAYS * 86400, httponly=True,
                     samesite='strict', secure=is_https(req), path='/')
        return r

    @app.post('/api/logout')
    def logout(req: Request):
        session_end(req.cookies.get(COOKIE))
        r = JSONResponse({'ok': True})
        r.delete_cookie(COOKIE, path='/')
        return r

    # ---------- objekty ----------
    # Data, zálohy a sken mají cestu /api/objects/{oid}/…. Staré cesty bez objektu (/api/data,
    # /api/backups, /api/scan) platí pro objekt s NAS, aby fungoval i editor z doby před objekty.

    migrate()

    def obj_of(oid):
        """Složka objektu z cesty; bez oid (stará cesta) objekt s NAS."""
        return obj_dir(oid) if oid else nas_obj()

    async def body_json(req):
        b = await req.body()
        if len(b) > MAX_BODY:
            raise ValueError
        b = json.loads(b)
        if not isinstance(b, dict):
            raise ValueError
        return b

    @app.get('/api/objects')
    def objects_get(req: Request):
        fresh_start(req_lang(req))
        return objects()

    @app.post('/api/objects')
    async def objects_post(req: Request):
        try:
            m = clean_meta(await body_json(req))
            if 'name' not in m:
                raise ValueError('name')
        except (ValueError, TypeError) as e:
            return err(400, 'invalid', field=str(e) or None)
        with _obj_lock:
            d = obj_new(m['name'], m.get('desc', ''), m.get('nas', False))
        return JSONResponse(obj_info(d), status_code=201)

    @app.get('/api/objects/{oid}')
    def object_get(oid: str):
        d = obj_dir(oid)
        return obj_info(d) if d else err(404, 'no object')

    # přejmenování, popisek a značka NAS: {name?, desc?, nas?}
    @app.patch('/api/objects/{oid}')
    async def object_patch(oid: str, req: Request):
        try:
            m = clean_meta(await body_json(req))
        except (ValueError, TypeError) as e:
            return err(400, 'invalid', field=str(e) or None)
        with _obj_lock:
            d = obj_dir(oid)
            if not d:
                return err(404, 'no object')
            obj_set(d, m)
        return obj_info(d)

    @app.delete('/api/objects/{oid}')
    def object_delete(oid: str):
        with _obj_lock, _data_lock:
            d = obj_dir(oid)
            if not d:
                return err(404, 'no object')
            obj_delete(d)
        return {'ok': True}

    # ---------- data ----------

    def current(o):
        net = read_text(o / FILES['net'])
        if net is None:
            return None
        lay = read_text(o / FILES['lay']) or ''
        return {'net': net, 'lay': lay, 'rev': rev_of(net, lay)}

    @app.get('/api/data')
    @app.get('/api/objects/{oid}/data')
    def data_get(oid: str = ''):
        o = obj_of(oid)
        if not o:
            return err(404, 'no object')
        c = current(o)
        return c if c else err(404, 'empty')

    @app.put('/api/data')
    @app.put('/api/objects/{oid}/data')
    async def data_put(req: Request, oid: str = ''):
        body = await req.body()
        if len(body) > MAX_BODY:
            return err(413, 'too large')
        try:
            b = json.loads(body)
            net, lay, md = b['net'], b['lay'], b.get('md', '')
            if not (isinstance(net, str) and isinstance(lay, str) and isinstance(md, str)):
                raise ValueError
            if not isinstance(json.loads(net).get('devices'), list) or not isinstance(json.loads(lay), dict):
                raise ValueError
        except (ValueError, KeyError, TypeError, AttributeError):
            return err(400, 'invalid data')
        want = req.headers.get('if-match', '').strip('"')
        with _data_lock:
            o = obj_of(oid)  # až pod zámkem: objekt mohl být mezitím smazán
            if not o:
                return err(404, 'no object')
            c = current(o)
            if c and want != c['rev']:
                return err(409, 'conflict', rev=c['rev'])
            backup_maybe(o)
            write_atomic(o / FILES['net'], net)
            write_atomic(o / FILES['lay'], lay)
            write_atomic(o / FILES['md'], md)
            return {'rev': rev_of(net, lay)}

    # ---------- zálohy ----------

    @app.get('/api/backups')
    @app.get('/api/objects/{oid}/backups')
    def backup_list(oid: str = ''):
        o = obj_of(oid)
        return backups(o) if o else err(404, 'no object')

    # záloha současné verze hned (editor ji dělá před obnovou, aby šla obnova vrátit)
    @app.post('/api/backups')
    @app.post('/api/objects/{oid}/backups')
    def backup_now(oid: str = ''):
        with _data_lock:
            o = obj_of(oid)
            bid = backup_maybe(o, force=True) if o else None
        return {'id': bid} if bid else err(404, 'empty')

    @app.get('/api/backups/{bid}')
    @app.get('/api/objects/{oid}/backups/{bid}')
    def backup_get(bid: str, oid: str = ''):
        o = obj_of(oid)
        if not o or bid not in {b['id'] for b in backups(o)}:
            return err(404, 'no backup')
        d = o / 'backup' / bid
        return {'net': read_text(d / FILES['net']), 'lay': read_text(d / FILES['lay']) or ''}

    # ruční smazání zálohy z editoru (id jen ze seznamu, takže žádná cesta mimo backup/)
    @app.delete('/api/backups/{bid}')
    @app.delete('/api/objects/{oid}/backups/{bid}')
    def backup_delete(bid: str, oid: str = ''):
        with _data_lock:
            o = obj_of(oid)
            if not o or bid not in {b['id'] for b in backups(o)}:
                return err(404, 'no backup')
            shutil.rmtree(o / 'backup' / bid, ignore_errors=True)
        return {'ok': True}

    # ---------- sken ----------
    # Sken je jeden pro celý server (síť NAS); smí ho jen objekt označený „tady je NAS“.

    def scan_obj(oid):
        o = obj_of(oid)
        if not o:
            return err(404, 'no object')
        return None if obj_meta(o)['nas'] else err(403, 'not nas')

    @app.post('/api/scan')
    @app.post('/api/objects/{oid}/scan')
    def scan_post(oid: str = ''):
        e = scan_obj(oid)
        if e:
            return e
        if not scan_start():
            return err(409, 'running', **scan_state())
        return JSONResponse(scan_state(), status_code=202)

    @app.get('/api/scan')
    @app.get('/api/objects/{oid}/scan')
    def scan_get(oid: str = ''):
        return scan_obj(oid) or scan_state()


# ---------- stránky (přihlášení, nastavení) ----------
# Každá stránka je ve dvou jazycích (LOGIN_HTML['cs'|'en']), vybírá req_lang. Přepínač CZ/EN vpravo nahoře
# zapíše volbu stejně jako editor (cookie netmapLang a localStorage) a stránku obnoví.

PAGE = '''<!doctype html><html lang="LANG"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>TITLE</title>
<style>
:root{--bg:#f4f5f7;--pn:#fff;--tx:#1d2330;--mu:#6b7280;--bd:#d6d9e0;--ac:#2563eb;--er:#c2410c}
@media (prefers-color-scheme:dark){:root{--bg:#14171d;--pn:#1d2129;--tx:#e6e8ec;--mu:#9aa1ad;--bd:#343a46;--ac:#60a5fa;--er:#fb923c}}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--tx);font:15px system-ui,sans-serif}
form,.box{background:var(--pn);border:1px solid var(--bd);border-radius:10px;padding:24px;width:min(320px,calc(100vw - 32px));box-sizing:border-box}
h1{font-size:18px;margin:0 0 16px}
label{display:block;font-size:13px;color:var(--mu);margin:10px 0 4px}
input{width:100%;box-sizing:border-box;padding:8px;border:1px solid var(--bd);border-radius:6px;background:var(--bg);color:var(--tx);font:inherit}
button{margin-top:16px;width:100%;padding:9px;border:0;border-radius:6px;background:var(--ac);color:#fff;font:inherit;cursor:pointer}
#lang{position:fixed;top:12px;right:12px;width:auto;margin:0;padding:4px 9px;background:var(--pn);color:var(--tx);border:1px solid var(--bd);font-size:13px}
#msg{color:var(--er);font-size:13px;min-height:18px;margin-top:10px}
code{font-size:13px}
</style></head><body>
<button id="lang" type="button" title="SWITCH">OTHER</button>
BODY
<script>
document.getElementById('lang').onclick = () => {
  const l = 'LANG' == 'cs' ? 'en' : 'cs';
  document.cookie = 'netmapLang=' + l + '; path=/; max-age=31536000; samesite=strict';
  try { localStorage.setItem('netmapLang', JSON.stringify(l)); } catch {}
  location.reload();
};
</script></body></html>'''

PT = {
    'cs': {
        'TITLE': 'Mapa sítě', 'OTHER': 'EN', 'SWITCH': 'English',
        'user': 'Jméno', 'pass': 'Heslo', 'code': 'Kód z aplikace (2FA)', 'go': 'Přihlásit',
        'wait': 'Moc pokusů, zkus to znovu za ${j.wait} s.', 'wrong': 'Špatné jméno, heslo nebo kód.',
        'server': 'Chyba serveru (', 'setup1': 'Účet ještě není nastavený. V terminálu kontejneru spusť:',
        'setup2': 'a pak tuto stránku obnov.',
    },
    'en': {
        'TITLE': 'Network map', 'OTHER': 'CZ', 'SWITCH': 'Čeština',
        'user': 'User name', 'pass': 'Password', 'code': 'Code from the app (2FA)', 'go': 'Sign in',
        'wait': 'Too many attempts, try again in ${j.wait} s.', 'wrong': 'Wrong user name, password or code.',
        'server': 'Server error (', 'setup1': 'The account is not set up yet. In the container terminal run:',
        'setup2': 'and then reload this page.',
    },
}


def page(lang, body):
    s = PAGE.replace('BODY', body).replace('LANG', lang)
    for k, v in PT[lang].items():
        s = s.replace(k if k.isupper() else '{' + k + '}', v)
    return s


LOGIN = '''<form id="f">
<h1>🖧 {TITLE}</h1>
<label>{user}<input name="user" autocomplete="username" required autofocus></label>
<label>{pass}<input name="pass" type="password" autocomplete="current-password" required></label>
<div id="cd" hidden><label>{code}<input name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6"></label></div>
<button>{go}</button>
<div id="msg"></div>
</form>
<script>
const f = document.getElementById('f'), msg = document.getElementById('msg');
f.onsubmit = async e => {
  e.preventDefault();
  msg.textContent = '';
  const b = Object.fromEntries(new FormData(f));
  if (!b.code) delete b.code;
  const r = await fetch('api/login', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)});
  const j = await r.json().catch(() => ({}));
  if (r.ok && j.need == 'code') {
    document.getElementById('cd').hidden = false;
    f.code.focus();
  } else if (r.ok) location.reload();
  else if (j.wait) msg.textContent = `{wait}`;
  else msg.textContent = r.status == 401 ? '{wrong}' : '{server}' + r.status + ').';
};
</script>'''

SETUP = '''<div class="box">
<h1>🖧 {TITLE}</h1>
<p>{setup1}</p>
<p><code>python app.py passwd</code></p>
<p>{setup2}</p>
</div>'''

LOGIN_HTML = {g: page(g, LOGIN.replace('{TITLE}', PT[g]['TITLE'])) for g in LANGS}
SETUP_HTML = {g: page(g, SETUP.replace('{TITLE}', PT[g]['TITLE'])) for g in LANGS}


# ---------- příkazová řádka: passwd, 2fa on/off, demo ----------


def cli_passwd():
    a = auth() or {}
    user = input(tl('Jméno', 'User name') + f' [{a.get("user", "admin")}]: ').strip() or a.get('user', 'admin')
    while True:
        p1 = getpass.getpass(tl('Nové heslo (aspoň 10 znaků): ', 'New password (at least 10 characters): '))
        if len(p1) < 10:
            print(tl('Heslo je moc krátké.', 'The password is too short.'))
            continue
        if p1 != getpass.getpass(tl('Heslo znovu: ', 'Password again: ')):
            print(tl('Hesla se neshodují.', 'The passwords do not match.'))
            continue
        break
    a.update(user=user, hash=pw_hash(p1))
    write_json(AUTH, a)
    write_json(SESSIONS, {})  # změna hesla odhlásí všechny
    print(tl('Heslo nastavené, všechny relace jsou odhlášené.', 'Password set, all sessions are signed out.'))


def cli_2fa(on):
    a = auth()
    if not a:
        sys.exit(tl('Nejdřív nastav heslo: python app.py passwd', 'Set a password first: python app.py passwd'))
    if not on:
        a.pop('totp', None)
        write_json(AUTH, a)
        print(tl('2FA je vypnuté.', '2FA is off.'))
        return
    secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')
    issuer = tl('Mapa%20s%C3%ADt%C4%9B', 'Network%20map')
    url = f'otpauth://totp/{issuer}:{a["user"]}?secret={secret}&issuer={issuer}'
    print(tl('Naskenuj QR kód v aplikaci (Google Authenticator, Aegis, 1Password…):\n',
             'Scan the QR code in an authenticator app (Google Authenticator, Aegis, 1Password…):\n'))
    try:
        import qrcode
        q = qrcode.QRCode(border=1)
        q.add_data(url)
        q.print_ascii(invert=True)
    except ImportError:
        pass
    print(tl(f'\nNebo zadej ručně klíč: {secret}\nOdkaz: {url}\n', f'\nOr enter the key manually: {secret}\nLink: {url}\n'))
    for _ in range(3):
        if totp_step(secret, input(tl('Kód z aplikace: ', 'Code from the app: '))) is not None:
            a['totp'] = secret
            write_json(AUTH, a)
            print(tl('2FA je zapnuté.', '2FA is on.'))
            return
        print(tl('Kód nesedí.', 'Wrong code.'))
    sys.exit(tl('2FA zůstává vypnuté.', '2FA stays off.'))


def cli_demo(lang):
    with _obj_lock:
        d = demo_new(lang)
    if not d:
        sys.exit(tl('Chybí ukázková síť: ', 'The demo network is missing: ') + str(DEMO / FILES['net']))
    print(tl(f'Objekt „{DEMO_NAME[lang]}“ je založený (data/{d.name}/).', f'Object "{DEMO_NAME[lang]}" created (data/{d.name}/).'))


if __name__ == '__main__':
    cmd = sys.argv[1:]
    if cmd == ['passwd']:
        cli_passwd()
    elif cmd in (['2fa', 'on'], ['2fa', 'off']):
        cli_2fa(cmd[1] == 'on')
    elif cmd[:1] == ['demo'] and len(cmd) <= 2 and (cmd[1:] or [CLI_LANG])[0] in LANGS:
        cli_demo((cmd[1:] or [CLI_LANG])[0])
    else:
        sys.exit(tl('Použití: python app.py passwd | 2fa on | 2fa off | demo [cs|en]',
                    'Usage: python app.py passwd | 2fa on | 2fa off | demo [cs|en]'))
