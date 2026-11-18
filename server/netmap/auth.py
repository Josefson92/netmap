"""Účet (heslo a TOTP), relace a ochrana proti hádání hesla."""

import base64
import hashlib
import hmac
import secrets
import struct
import threading
import time
from collections import deque

from .config import AUTH, FAIL_FORGET, FAIL_WAIT, FAILS_ALL, FAILS_FREE, SESSION_DAYS, SESSIONS
from .store import read_json, write_json

# ---------- heslo ----------
# scrypt s parametry podle OWASP (N=2^15, r=8, p=3: 32 MB paměti na jeden pokus).
# Parametry jsou v uloženém hashi, takže starší hash s jinými parametry se ověří dál.

SCRYPT = (2**15, 8, 3)
SCRYPT_MAXMEM = 256 * 1024 * 1024


def pw_hash(pw, salt=None):
    n, r, p = SCRYPT
    salt = salt or secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=n, r=r, p=p, maxmem=SCRYPT_MAXMEM, dklen=32)
    return f'scrypt${n}${r}${p}${salt.hex()}${h.hex()}'


def pw_check(pw, stored):
    try:
        _, n, r, p, salt, h = stored.split('$')
        got = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p),
                             maxmem=SCRYPT_MAXMEM, dklen=len(h) // 2)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got.hex(), h)


# ---------- TOTP ----------


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


def totp_new():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')


# ---------- účet a přihlášení ----------

_used_steps = {}  # poslední použitý krok TOTP (kód nejde použít dvakrát)


def auth():
    return read_json(AUTH, None)


def login_ok(a, user, pw, code):
    """Jméno, heslo a (se zapnutým 2FA) kód najednou. Odpověď je jen ano/ne, takže z ní nejde
    poznat, která část byla špatně; scrypt se počítá vždy (žádný rozdíl v čase)."""
    ok = hmac.compare_digest(user.encode(), a['user'].encode()) & pw_check(pw, a['hash'])
    if a.get('totp'):
        s = totp_step(a['totp'], code)
        ok = ok and s is not None and s > _used_steps.get(a['user'], -1)
        if ok:
            _used_steps[a['user']] = s
    return ok


# ---------- první nastavení účtu ----------
# Dokud účet není, vypíše server při startu do protokolu kontejneru jednorázový kód. S ním jde účet
# založit v prohlížeči; kdo stránku jen vidí v síti, účet nezaloží. Po založení účtu kód přestane platit.

_setup = {'code': ''}


def setup_start():
    """Nový kód, když ještě žádný neplatí; vrátí ho (k vypsání), jinak ''."""
    if _setup['code']:
        return ''
    _setup['code'] = '-'.join(''.join(secrets.choice('0123456789') for _ in range(4)) for _ in range(3))
    return _setup['code']


def setup_end():
    _setup['code'] = ''


def setup_ok(code):
    """Kód z protokolu (pomlčky a mezery se nepočítají)."""
    clean = lambda c: c.replace('-', '').replace(' ', '')
    return bool(_setup['code']) and hmac.compare_digest(clean(code).encode(), clean(_setup['code']).encode())


def account_set(user, pw):
    """Jméno a heslo; změna odhlásí všechny relace. 2FA zůstane, jak bylo."""
    a = auth() or {}
    a.update(user=user, hash=pw_hash(pw))
    write_json(AUTH, a)
    sessions_clear()


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


def sessions_clear():
    write_json(SESSIONS, {})


# ---------- ochrana proti hádání hesla ----------
# Po FAILS_FREE chybách z jedné adresy se čeká, každá další chyba čekání zdvojnásobí.
# Proti hádání z mnoha adres najednou platí i celkový limit FAILS_ALL chyb za minutu.

_fails = {}       # ip → [počet chyb, do kdy se čeká, čas poslední chyby]
_recent = deque()  # časy chyb ze všech adres za poslední minutu


def wait_left(ip):
    """Kolik sekund se ještě čeká (0 = smí se zkusit)."""
    now = time.time()
    while _recent and _recent[0] < now - 60:
        _recent.popleft()
    f = _fails.get(ip)
    until = f[1] if f else 0
    if len(_recent) >= FAILS_ALL:
        until = max(until, _recent[0] + 60)
    return int(until - now) + 1 if until > now else 0


def fail(ip):
    now = time.time()
    for k in [k for k, f in _fails.items() if now - f[2] > FAIL_FORGET]:
        del _fails[k]
    n = _fails.get(ip, [0])[0] + 1
    wait = FAIL_WAIT * 2 ** min(n - FAILS_FREE, 10) if n >= FAILS_FREE else 0
    _fails[ip] = [n, now + wait, now]
    _recent.append(now)


def fail_reset(ip):
    _fails.pop(ip, None)
