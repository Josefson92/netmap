"""Cesty, limity a jazyk. Cesty mění proměnné prostředí NETMAP_* (test, Docker)."""

import os
import re
from pathlib import Path

# ---------- cesty ----------

ROOT = Path(os.environ.get('NETMAP_ROOT', Path(__file__).resolve().parents[2]))
WWW = Path(os.environ.get('NETMAP_WWW', ROOT / 'www'))
EDITOR = ROOT / 'mapa.html'  # editor z image (v repozitáři vedle server/); www/mapa.html má přednost
DATA = Path(os.environ.get('NETMAP_DATA', ROOT / 'data'))
CONFIG = Path(os.environ.get('NETMAP_CONFIG', ROOT / 'config'))
DEMO = Path(os.environ.get('NETMAP_DEMO', ROOT / 'ukazka'))  # fiktivní síť pro objekt „Ukázka“, anglická vedle s -en
AUTH = CONFIG / 'auth.json'
SESSIONS = CONFIG / 'sessions.json'
SCAN_LAST = DATA / 'scan' / 'last.json'
DELETED = DATA / '_deleted'  # smazané objekty (jdou ručně vrátit ve File Station)

FILES = {'net': 'network.json', 'lay': 'layout.json', 'md': 'network.md'}
META = 'meta.json'           # {name, desc, nas, img} objektu

# ---------- přihlášení ----------

COOKIE = 'netmap_s'
PW_MIN = 10                  # nejkratší heslo
SESSION_DAYS = 30
FAILS_FREE = 5               # po 5 špatných pokusech z jedné adresy se čeká
FAIL_WAIT = 60               # 1 minutu, s každou další chybou dvakrát déle
FAIL_FORGET = 3600           # hodinu bez chyby = adresa začíná znovu od nuly
FAILS_ALL = 30               # víc chyb za minutu ze všech adres dohromady = přihlášení na minutu stojí

# ---------- limity požadavků a dat ----------

MAX_BODY = 20 * 1024 * 1024  # uložení mapy (network.json + layout.json + network.md)
LOGIN_BODY = 4096            # přihlášení (jméno, heslo, kód)
META_BODY = 1024 * 1024      # údaje objektu včetně obrázku náhledu
NAME_MAX = 60
DESC_MAX = 300
IMG_MAX = 500_000            # vlastní obrázek náhledu (data URL, editor ho zmenší na 800 px), '' = náhled z topologie
IMG_RE = re.compile(r'data:image/(webp|png|jpeg);base64,[A-Za-z0-9+/=]+')
OBJ_RE = re.compile(r'[a-z0-9][a-z0-9-]{0,39}')  # id objektu = název složky v data/

# ---------- zálohy a sken ----------

STAMP = '%Y-%m-%d_%H%M%S'
BACKUP_IDLE = 30 * 60        # záloha jen na začátku úprav: když se data aspoň 30 minut neměnila
BACKUP_KEEP = 4              # nechávají se 4 nejnovější zálohy
NMAP = os.environ.get('NETMAP_NMAP', 'nmap')  # jiná cesta jen pro test (falešný nmap)
SCAN_TIMEOUT = 300
SCAN_MAX = 1024              # největší skenovaná síť (/22), ať se omylem neskenuje celé /8

# ---------- jazyk ----------

LANGS = ('cs', 'en')         # jazyky stránek a ukázky; editor posílá ruční volbu v cookie LANG_COOKIE
LANG_COOKIE = 'netmapLang'
FIRST = {'cs': 'Domov', 'en': 'Home'}  # první objekt (převod dat z doby před objekty jde vždy do „Domov“)
DEMO_NAME = {'cs': 'Ukázka', 'en': 'Demo'}
DEMO_DESC = {'cs': 'Fiktivní síť na vyzkoušení editoru', 'en': 'Fictional network to try out the editor'}


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
