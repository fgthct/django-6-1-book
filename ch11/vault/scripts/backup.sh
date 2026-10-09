#!/usr/bin/env bash
# Usage: scripts/backup.sh [folder]   (run it in the project folder, with the stack up)
set -euo pipefail

DEST="${1:-backup}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DEST"

# The database first, then the files: if an upload arrives in between, the backup contains one extra file
# without its row (an orphan, harmless), never a row without its file (that would be a broken document).
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$DEST/db-$STAMP.dump"
docker compose exec -T web tar -C /data -cf - media > "$DEST/media-$STAMP.tar"

# A backup that can't even be listed is already useless: you find out now, not on the day of the disaster.
docker compose exec -T db pg_restore --list < "$DEST/db-$STAMP.dump" > /dev/null
tar -tf "$DEST/media-$STAMP.tar" > /dev/null

echo "Backup complete: $DEST/db-$STAMP.dump  $DEST/media-$STAMP.tar"
