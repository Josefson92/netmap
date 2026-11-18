#!/bin/sh
# Start kontejneru (docs/nas.md). Běží jako root jen chvíli: najde uživatele, který smí
# zapisovat do data/ a config/, předá mu je a server spustí pod ním, bez práv roota.
# Nic se nemusí nastavovat ručně; PUID/PGID v docker-compose.yml volbu jen vynutí.
set -e

DIRS="/app/data /app/config"

if [ "$(id -u)" != 0 ]; then
  exec "$@"
fi

# as_user UID:GID příkaz… = příkaz pod tímto uživatelem, bez skupin navíc
as_user() {
  ug=$1
  shift
  setpriv --reuid="${ug%:*}" --regid="${ug#*:}" --clear-groups "$@"
}

# can_write UID:GID = uživatel smí zapisovat do všech složek
can_write() {
  for d in $DIRS; do
    as_user "$1" sh -c "mkdir '$d/.netmap-test-$$' && rmdir '$d/.netmap-test-$$'" 2>/dev/null || return 1
  done
}

# give UID:GID = předá soubory uživateli (mění jen ty s jiným vlastníkem, rychlé i s mnoha zálohami)
give() {
  for d in $DIRS; do
    find "$d" \( ! -user "${1%:*}" -o ! -group "${1#*:}" \) -exec chown -h "$1" {} +
  done
}

for d in $DIRS; do
  mkdir -p "$d"
done

# Kandidáti: ruční PUID/PGID, jinak vlastník složky data/ (když to není root), 1000:1000
# a 1000:101 (Synology: o zápisu rozhoduje ACL a skupina administrators = GID 101 ho má).
if [ -n "$PUID$PGID" ]; then
  cands="${PUID:-1000}:${PGID:-1000}"
else
  cands="1000:1000 1000:101"
  own=$(stat -c %u:%g /app/data)
  case $own in
    0:* | 1000:1000 | 1000:101) ;;
    *) cands="$own $cands" ;;
  esac
fi

who=
for c in $cands; do
  if can_write "$c"; then
    who=$c
    break
  fi
done

# Nikdo nesmí zapisovat (např. čerstvé složky po rootovi bez ACL): předat je prvnímu kandidátovi.
if [ -z "$who" ]; then
  first=${cands%% *}
  give "$first"
  if can_write "$first"; then
    who=$first
  fi
fi

if [ -z "$who" ]; then
  cat >&2 <<EOF

netmap: no user can write to $DIRS (tried $cands).
netmap: do $DIRS nemůže zapisovat žádný uživatel (zkoušeno $cands).

  Set PUID and PGID in docker-compose.yml to a user and group with write
  access to the folders data/ and config/, then start the container again.
  V docker-compose.yml nastav PUID a PGID na uživatele a skupinu, kteří mají
  do složek data/ a config/ právo zápisu, a kontejner spusť znovu.

EOF
  exit 1
fi

give "$who"
echo "netmap: server runs as $who"
exec setpriv --reuid="${who%:*}" --regid="${who#*:}" --clear-groups "$@"
