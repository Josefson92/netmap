"""Čtení a atomický zápis souborů, verze dat."""

import hashlib
import json
import os


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
