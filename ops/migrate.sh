#!/usr/bin/env bash
set -euo pipefail
: "${DB_HOST:?}"; : "${DB_USER:?}"; : "${DB_PASSWORD:?}"; : "${DB_DATABASE:?}"
export PGPASSWORD="$DB_PASSWORD"

for f in $(ls -1 ops/sql/*.sql | sort); do
  echo "==> applying $f"
  psql "host=$DB_HOST port=${DB_PORT:-5432} user=$DB_USER dbname=$DB_DATABASE sslmode=${DB_SSLMODE:-require}" \
    -v ON_ERROR_STOP=1 -f "$f"
done
echo "✅ Migration complete"
