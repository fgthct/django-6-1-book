#!/usr/bin/env bash
# Usage: scripts/restore.sh backup/db-....dump backup/media-....tar
# DESTRUCTIVE: replaces the database and the files with those of the backup. Run it by hand, never from cron.
set -euo pipefail

DUMP="${1:?Usage: scripts/restore.sh <db.dump> <media.tar>}"
MEDIA="${2:?Usage: scripts/restore.sh <db.dump> <media.tar>}"

docker compose up -d --wait db
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' < "$DUMP"
docker compose exec -T -u root web sh -c 'rm -rf /data/media && tar -C /data -xf - && chown -R vault /data/media' < "$MEDIA"
docker compose up -d --wait

echo "Restore complete."
