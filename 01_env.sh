set -euo pipefail
REF="ykqrruipzmrrvjcvwfgp"
DB_HOST="db.${REF}.supabase.co"

# get password (hidden)
if [ -z "${PW_POOLER:-}" ]; then
  read -s -p "Postgres password for user 'postgres': " PW_POOLER; echo
fi

PW_ENC="$(python3 - "$PW_POOLER" <<'PY'
import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=''))
PY
)"

DATABASE_URL="postgresql://postgres:${PW_ENC}@${DB_HOST}:6543/postgres?sslmode=require&connect_timeout=5"
printf "DATABASE_URL=%s\nDB_ENABLED=true\nAUTH_PROTECT_ROUTES=false\nREQUIRE_JWT=false\nAUTH_ALLOW_ANY_BEARER=true\nAUTH_ADMIN_KEY=devkey123\n" \
  "$DATABASE_URL" > .env

umask 077
cat > ~/.pgpass <<PG
${DB_HOST}:6543:postgres:postgres:${PW_POOLER}
${DB_HOST}:5432:postgres:postgres:${PW_POOLER}
PG
chmod 600 ~/.pgpass
echo "[ok] .env and ~/.pgpass set"
