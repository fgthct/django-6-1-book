#!/usr/bin/env bash
# Creates the PostgreSQL roles and databases used by chapters 3, 6, 7, 8, 9 and 10.
# Safe to run more than once. Default: runs psql as the "postgres" system user (Debian/Ubuntu).
# Another server? Set PSQL, for example:
#   PGPASSWORD=secret PSQL="psql -h localhost -p 5433 -U postgres" ./scripts/create-databases.sh
set -euo pipefail
PSQL="${PSQL:-sudo -u postgres psql}"

run() { $PSQL -v ON_ERROR_STOP=1 -qAt "$@"; }

# Chapters 6, 7 and 10 need the pgvector extension. Creating it in template1 means that the
# temporary test databases created by pytest-django get it too, without superuser rights.
run -d template1 -c "CREATE EXTENSION IF NOT EXISTS vector"

for name in blog semantics kb postbox saas vault; do
  if [ "$(run -c "SELECT 1 FROM pg_roles WHERE rolname='$name'")" != "1" ]; then
    run -c "CREATE ROLE $name WITH LOGIN PASSWORD '$name' CREATEDB"
  fi
  if [ "$(run -c "SELECT 1 FROM pg_database WHERE datname='$name'")" != "1" ]; then
    run -c "CREATE DATABASE $name OWNER $name"
  fi
  echo "ok: $name"
done
