"""Webová aplikace (FastAPI): editor, přihlášení a REST API. Jediný modul, který potřebuje FastAPI;
příkazová řádka (cli.py) ho neimportuje.

Spuštění: uvicorn netmap.api:app --host 0.0.0.0 --port 8780
Data, zálohy a sken mají cestu /api/objects/{oid}/…. Staré cesty bez objektu (/api/data,
/api/backups, /api/scan) platí pro objekt s NAS, aby fungoval i editor z doby před objekty."""

import base64
import io
import json
import shutil
import threading
from urllib.parse import urlsplit

import qrcode
import qrcode.image.svg
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from . import auth as A
from .backups import backup_dir, backup_maybe, backups
from .config import (COOKIE, EDITOR, FILES, ISSUER, LANG_COOKIE, LOGIN_BODY, MAX_BODY, META_BODY, NAME_MAX, PW_MIN,
                     SESSION_DAYS, WWW, lang_of)
from .objects import (clean_meta, fresh_start, migrate, nas_obj, obj_delete, obj_dir, obj_info, obj_lock,
                      obj_meta, obj_new, obj_set, objects)
from .pages import LOGIN_HTML, SETUP_HTML
from .scan import scan_start, scan_state
from .store import read_text, rev_of, write_atomic
from .update import update_info, update_start

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
data_lock = threading.Lock()
setup_lock = threading.Lock()

PUBLIC = {'/api/health', '/api/login', '/api/logout', '/api/setup'}
SAFE = {'GET', 'HEAD', 'OPTIONS'}

# Editor i přihlášení mají skripty a styly přímo ve stránce (jeden soubor), proto 'unsafe-inline'.
# Hlavní je connect-src a img-src: podstrčený skript by data neměl kam poslat a stránka nenačte nic cizího.
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; "
       "form-action 'self'; frame-ancestors 'none'")

# ---------- pomocné funkce ----------


class TooLarge(Exception):
    pass


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


def cross_site(req):
    """Požadavek z cizí stránky (CSRF). Prohlížeč posílá Sec-Fetch-Site; starší jen Origin.
    SameSite=Strict u cookie nestačí: jiná aplikace na stejném NAS (jiný port) je pro prohlížeč týž „site“."""
    s = req.headers.get('sec-fetch-site')
    if s:
        return s not in ('same-origin', 'none')
    o = req.headers.get('origin')
    return bool(o) and urlsplit(o).netloc != req.headers.get('host', '')


def req_lang(req):
    return lang_of(req.cookies.get(LANG_COOKIE), req.headers.get('accept-language'))


def err(code, msg, **kw):
    return JSONResponse({'error': msg, **kw}, status_code=code)


async def read_body(req, limit):
    """Tělo požadavku nejvýš limit bajtů. Čte se po částech, takže velký požadavek nezaplní paměť."""
    cl = req.headers.get('content-length')
    if cl and (not cl.isdigit() or int(cl) > limit):
        raise TooLarge
    b = bytearray()
    async for chunk in req.stream():
        b += chunk
        if len(b) > limit:
            raise TooLarge
    return bytes(b)


async def body_json(req, limit):
    """JSON objekt z těla; jiný obsah = ValueError."""
    b = json.loads(await read_body(req, limit))
    if not isinstance(b, dict):
        raise ValueError
    return b


@app.exception_handler(TooLarge)
async def too_large(req, e):
    return err(413, 'too large')


# ---------- kontrola každého požadavku ----------


@app.middleware('http')
async def guard(req: Request, call_next):
    """Změny jen z vlastní stránky. Bez účtu jen nastavovací hláška, bez relace přihlašovací stránka (API vrací 401)."""
    p = req.url.path
    api = p.startswith('/api/')
    if req.method not in SAFE and cross_site(req):
        return err(403, 'cross-site')
    if p in PUBLIC:
        return await call_next(req)
    if not A.auth():
        setup_banner()  # účet zmizel za běhu: nový kód do protokolu
        return err(503, 'setup') if api else HTMLResponse(SETUP_HTML[req_lang(req)], status_code=503)
    if not A.session_ok(req.cookies.get(COOKIE)):
        if api:
            return err(401, 'login')
        return HTMLResponse(LOGIN_HTML[req_lang(req)], status_code=401, headers={'Cache-Control': 'no-store'})
    return await call_next(req)


@app.middleware('http')
async def headers(req: Request, call_next):
    r = await call_next(req)
    r.headers.setdefault('Cache-Control', 'no-store')
    r.headers['Content-Security-Policy'] = CSP
    r.headers['X-Content-Type-Options'] = 'nosniff'
    r.headers['X-Frame-Options'] = 'DENY'
    r.headers['Referrer-Policy'] = 'no-referrer'
    return r


# ---------- stránky ----------


@app.get('/api/health')
def health():
    return {'app': 'netmap', 'ok': True}


@app.get('/api/version')
def version():
    """Verze serveru a novější vydání na GitHubu (jen přihlášeným; health verzi neprozrazuje)."""
    return update_info()


@app.get('/')
def index(req: Request):
    f = WWW / 'mapa.html'
    if not f.exists():
        f = EDITOR
    if not f.exists():
        return HTMLResponse('Chybí mapa.html' if req_lang(req) == 'cs' else 'Missing mapa.html', status_code=500)
    return FileResponse(f, media_type='text/html; charset=utf-8', headers={'Cache-Control': 'no-cache'})


@app.get('/mapa.html')
def index_alias():
    return Response(status_code=302, headers={'Location': './'})


# ---------- přihlášení ----------


@app.post('/api/login')
async def login(req: Request):
    a = A.auth()
    if not a:
        return err(503, 'setup')
    ip = client_ip(req)
    w = A.wait_left(ip)
    if w:
        return err(429, 'wait', wait=w)
    try:
        b = await body_json(req, LOGIN_BODY)
        user, pw, code = str(b.get('user', '')), str(b.get('pass', '')), str(b.get('code') or '')
    except ValueError:
        return err(400, 'bad request')
    ok = A.login_check(a, user, pw, code)
    if ok == 'code':  # heslo sedí, zapnuté 2FA: stránka ukáže pole pro kód
        return err(401, 'code')
    if not ok:
        A.fail(ip)
        w = A.wait_left(ip)
        return err(401, 'wrong', **({'wait': w} if w else {}))
    A.fail_reset(ip)
    return signed_in(req)


def signed_in(req):
    """Odpověď s cookie nové relace."""
    r = JSONResponse({'ok': True})
    r.set_cookie(COOKIE, A.session_new(), max_age=SESSION_DAYS * 86400, httponly=True,
                 samesite='strict', secure=is_https(req), path='/')
    return r


@app.post('/api/setup')
async def setup(req: Request):
    """První účet z prohlížeče: jednorázový kód z protokolu kontejneru, jméno a heslo.
    Špatný kód se počítá jako špatné přihlášení (stejné čekání)."""
    ip = client_ip(req)
    w = A.wait_left(ip)
    if w:
        return err(429, 'wait', wait=w)
    try:
        b = await body_json(req, LOGIN_BODY)
        code, user, pw = str(b.get('code', '')), str(b.get('user', '')).strip(), str(b.get('pass', ''))
    except ValueError:
        return err(400, 'bad request')
    with setup_lock:
        if A.auth():
            return err(409, 'done')
        if not A.setup_ok(code):
            A.fail(ip)
            w = A.wait_left(ip)
            return err(401, 'wrong', **({'wait': w} if w else {}))
        if not user or len(user) > NAME_MAX or len(pw) < PW_MIN:
            return err(400, 'short')
        A.account_set(user, pw)
        A.setup_end()
    A.fail_reset(ip)
    return signed_in(req)


def setup_banner():
    """Bez účtu vypíše do protokolu kontejneru kód pro první nastavení v prohlížeči (jednou za kód)."""
    code = '' if A.auth() else A.setup_start()
    if not code:
        return
    line = '=' * 64
    print('\n'.join(['', line,
                     ' netmap: no account yet / účet ještě není nastavený',
                     f' Setup code / kód pro nastavení:  {code}',
                     ' Open the server in a browser and enter the code there.',
                     ' Otevři server v prohlížeči a kód zadej tam.',
                     line, '']), flush=True)


@app.post('/api/logout')
def logout(req: Request):
    A.session_end(req.cookies.get(COOKIE))
    r = JSONResponse({'ok': True})
    r.delete_cookie(COOKIE, path='/')
    return r


# ---------- účet (okno 🔐 Účet v editoru) ----------
# Každá změna chce současné heslo (špatné se počítá jako špatné přihlášení), vypnutí 2FA i platný kód.
# Odpověď 403 (ne 401): editor by na 401 obnovil stránku a odhlásil se.


@app.get('/api/account')
def account_get():
    a = A.auth()
    return {'user': a['user'], 'totp': bool(a.get('totp')), 'min': PW_MIN}


async def account_req(req):
    """(účet, tělo požadavku), nebo (None, chybová odpověď), když nesedí heslo nebo se čeká."""
    ip = client_ip(req)
    w = A.wait_left(ip)
    if w:
        return None, err(429, 'wait', wait=w)
    try:
        b = await body_json(req, LOGIN_BODY)
    except ValueError:
        return None, err(400, 'bad request')
    a = A.auth()
    if not A.pw_check(str(b.get('pass', '')), a['hash']):
        A.fail(ip)
        w = A.wait_left(ip)
        return None, err(403, 'wrong', **({'wait': w} if w else {}))
    A.fail_reset(ip)
    return a, b


# změna jména a hesla: odhlásí všechna zařízení, tenhle prohlížeč dostane novou relaci
@app.post('/api/account/password')
async def account_password(req: Request):
    a, b = await account_req(req)
    if not a:
        return b
    user, new = str(b.get('user') or a['user']).strip(), str(b.get('new', ''))
    if not user or len(user) > NAME_MAX or len(new) < PW_MIN:
        return err(400, 'short')
    A.account_set(user, new)
    return signed_in(req)


def qr_svg(text):
    """QR kód jako data URL (SVG), editor ho ukáže v <img> (CSP povoluje data:)."""
    buf = io.BytesIO()
    qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, border=2).save(buf)
    return 'data:image/svg+xml;base64,' + base64.b64encode(buf.getvalue()).decode()


# nový klíč 2FA k naskenování; zapne se až s prvním kódem (/on), do té doby ho server nikam neukládá
@app.post('/api/account/2fa/new')
async def account_2fa_new(req: Request):
    a, b = await account_req(req)
    if not a:
        return b
    if a.get('totp'):
        return err(409, 'on')
    secret = A.totp_new()
    url = A.totp_url(a['user'], secret, ISSUER[req_lang(req)])
    return {'secret': secret, 'url': url, 'qr': qr_svg(url)}


@app.post('/api/account/2fa/on')
async def account_2fa_on(req: Request):
    a, b = await account_req(req)
    if not a:
        return b
    secret = b.get('secret')
    if a.get('totp'):
        return err(409, 'on')
    if not A.totp_valid(secret):
        return err(400, 'bad request')
    if not A.totp_use(a, secret, str(b.get('code', ''))):
        return err(403, 'code')  # překlep v kódu: heslo sedělo, nepočítá se jako hádání
    A.totp_set(secret)
    return {'ok': True}


@app.post('/api/account/2fa/off')
async def account_2fa_off(req: Request):
    a, b = await account_req(req)
    if not a:
        return b
    if not a.get('totp'):
        return {'ok': True}
    if not A.totp_use(a, a['totp'], str(b.get('code', ''))):
        A.fail(client_ip(req))  # kód k zapnutému 2FA se hádat nesmí
        return err(403, 'code')
    A.totp_set(None)
    return {'ok': True}


# ---------- objekty ----------

migrate()
setup_banner()
update_start()


def obj_of(oid):
    """Složka objektu z cesty; bez oid (stará cesta) objekt s NAS."""
    return obj_dir(oid) if oid else nas_obj()


@app.get('/api/objects')
def objects_get(req: Request):
    fresh_start(req_lang(req))
    return objects()


@app.post('/api/objects')
async def objects_post(req: Request):
    try:
        m = clean_meta(await body_json(req, META_BODY))
        if 'name' not in m:
            raise ValueError('name')
    except ValueError as e:
        return err(400, 'invalid', field=str(e) or None)
    with obj_lock:
        d = obj_new(m['name'], m.get('desc', ''), m.get('nas', False))
    return JSONResponse(obj_info(d), status_code=201)


@app.get('/api/objects/{oid}')
def object_get(oid: str):
    d = obj_dir(oid)
    return obj_info(d) if d else err(404, 'no object')


# přejmenování, popisek, obrázek a značka NAS: {name?, desc?, img?, nas?}
@app.patch('/api/objects/{oid}')
async def object_patch(oid: str, req: Request):
    try:
        m = clean_meta(await body_json(req, META_BODY))
    except ValueError as e:
        return err(400, 'invalid', field=str(e) or None)
    with obj_lock:
        d = obj_dir(oid)
        if not d:
            return err(404, 'no object')
        obj_set(d, m)
    return obj_info(d)


@app.delete('/api/objects/{oid}')
def object_delete(oid: str):
    with obj_lock, data_lock:
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
    try:
        b = await body_json(req, MAX_BODY)
        net, lay, md = b['net'], b['lay'], b.get('md', '')
        if not (isinstance(net, str) and isinstance(lay, str) and isinstance(md, str)):
            raise ValueError
        if not isinstance(json.loads(net).get('devices'), list) or not isinstance(json.loads(lay), dict):
            raise ValueError
    except (ValueError, KeyError, AttributeError):
        return err(400, 'invalid data')
    want = req.headers.get('if-match', '').strip('"')
    with data_lock:
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
    with data_lock:
        o = obj_of(oid)
        bid = backup_maybe(o, force=True) if o else None
    return {'id': bid} if bid else err(404, 'empty')


@app.get('/api/backups/{bid}')
@app.get('/api/objects/{oid}/backups/{bid}')
def backup_get(bid: str, oid: str = ''):
    o = obj_of(oid)
    d = o and backup_dir(o, bid)
    if not d:
        return err(404, 'no backup')
    return {'net': read_text(d / FILES['net']), 'lay': read_text(d / FILES['lay']) or ''}


@app.delete('/api/backups/{bid}')
@app.delete('/api/objects/{oid}/backups/{bid}')
def backup_delete(bid: str, oid: str = ''):
    with data_lock:
        o = obj_of(oid)
        d = o and backup_dir(o, bid)
        if not d:
            return err(404, 'no backup')
        shutil.rmtree(d, ignore_errors=True)
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
