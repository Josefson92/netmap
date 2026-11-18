"""Kontrola nové verze: server se 1× denně zeptá GitHubu na poslední vydání (GET /releases/latest).
Ptá se server, ne prohlížeč (CSP editoru nepustí nic cizího). Dotaz prozradí GitHubu adresu serveru,
proto jde vypnout: NETMAP_UPDATE_CHECK=0. Server se sám neaktualizuje, editor jen ukáže upozornění."""

import json
import re
import threading
import time
import urllib.error
import urllib.request

from .config import UPDATE_CHECK, UPDATE_EVERY, UPDATE_REPO, UPDATE_RETRY, VERSION

state = {'latest': '', 'url': '', 'at': 0}  # poslední vydání z GitHubu, at = čas úspěšné kontroly
started = threading.Event()


def ver_of(v):
    """(1, 2, 3) z „v1.2.3“ i „v1.2.3-4-gabc“ (sestavení z main po vydání), jinak None (dev)."""
    m = re.match(r'v?(\d+)\.(\d+)\.(\d+)', v or '')
    return tuple(int(x) for x in m.groups()) if m else None


def newer(latest, cur):
    """Je vydání novější než běžící verze? Sestavení bez verze (dev) se neupozorňuje."""
    a, b = ver_of(latest), ver_of(cur)
    return bool(a and b and a > b)


def fetch():
    """{latest, url} posledního vydání; bez vydání (404) prázdné."""
    req = urllib.request.Request(f'https://api.github.com/repos/{UPDATE_REPO}/releases/latest', headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': f'netmap/{VERSION}',
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            j = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {'latest': '', 'url': ''}
        raise
    url = str(j.get('html_url', ''))[:300]
    return {'latest': str(j.get('tag_name', ''))[:40], 'url': url if url.startswith('https://github.com/') else ''}


def check_loop():
    while True:
        try:
            state.update(fetch(), at=int(time.time()))
            wait = UPDATE_EVERY
        except Exception as e:  # síť, GitHub, limit dotazů: nevadí, zkusí se později
            print(f'netmap: update check failed: {e}', flush=True)
            wait = UPDATE_RETRY
        time.sleep(wait)


def update_start():
    """Spustí kontrolu na pozadí (jednou za běh serveru)."""
    if UPDATE_CHECK and not started.is_set():
        started.set()
        threading.Thread(target=check_loop, name='update-check', daemon=True).start()


def update_info():
    """Pro editor: běžící verze, zapnutí kontroly a novější vydání (jen když opravdu je)."""
    new = newer(state['latest'], VERSION)
    return {
        'version': VERSION,
        'check': UPDATE_CHECK,
        'at': state['at'],
        'latest': state['latest'] if new else '',
        'url': state['url'] if new else '',
    }
