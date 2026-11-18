"""Zálohy. Každý objekt má vlastní zálohy v data/<id>/backup/<čas>/; o = složka objektu."""

import os
import shutil
from datetime import datetime

from .config import BACKUP_IDLE, BACKUP_KEEP, FILES, STAMP
from .store import read_text


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


def backup_dir(o, bid):
    """Složka zálohy podle id, jen když je v seznamu (žádná cesta mimo backup/), jinak None."""
    return o / 'backup' / bid if bid in {b['id'] for b in backups(o)} else None


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
