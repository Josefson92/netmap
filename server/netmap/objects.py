"""Objekty (dům, chata…). Každý má složku data/<id>/: network.json, layout.json, network.md,
meta.json a backup/. id vznikne z názvu a už se nemění; přejmenování mění jen meta.json (editor má
podle id uložené věci v localStorage). Ve složce data/ jsou kromě objektů jen scan/ a _deleted/."""

import json
import os
import re
import threading
import unicodedata
from datetime import datetime

from .config import (DATA, DELETED, DEMO, DEMO_DESC, DEMO_NAME, DESC_MAX, FILES, FIRST, IMG_MAX, IMG_RE,
                     META, NAME_MAX, OBJ_RE, STAMP)
from .store import read_json, read_text, write_atomic, write_json

obj_lock = threading.Lock()
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


# ---------- ukázka a první spuštění ----------


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
    with obj_lock:
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
    with obj_lock:
        if obj_dirs():
            return
        DATA.mkdir(parents=True, exist_ok=True)
        old = [DATA / n for n in FILES.values()] + [DATA / 'backup']
        if any(f.exists() for f in old):
            obj_new(FIRST['cs'], nas=True, files=old)
        else:
            _fresh = True
