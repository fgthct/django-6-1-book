#!/usr/bin/env bash
# Usage: scripts/verify-backup.sh backup/db-....dump
# Restores the dump into a temporary database and compares the counts with the live one.
set -euo pipefail

DUMP="${1:?Usage: scripts/verify-backup.sh backup/db-....dump}"
TMP="verify_$$"
PSQL='psql -q -U "$POSTGRES_USER" -At'
COUNTS="SELECT 'documents ' || count(*) FROM documents_document UNION ALL SELECT 'versions ' || count(*) FROM documents_version UNION ALL SELECT 'passages ' || count(*) FROM documents_chunk"

docker compose exec -T db sh -c "$PSQL -d postgres -c 'CREATE DATABASE $TMP'"
trap 'docker compose exec -T db sh -c "$PSQL -d postgres -c \"DROP DATABASE IF EXISTS $TMP\"" > /dev/null' EXIT
docker compose exec -T db sh -c "pg_restore -U \"\$POSTGRES_USER\" -d $TMP --no-owner" < "$DUMP"

echo "--- in the backup"
docker compose exec -T db sh -c "$PSQL -d $TMP -c \"$COUNTS\""
echo "--- in the live database"
docker compose exec -T db sh -c "$PSQL -d \"\$POSTGRES_DB\" -c \"$COUNTS\""
