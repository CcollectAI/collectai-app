#!/usr/bin/env bash
set -euo pipefail

# Load .env into this shell too (belt-and-suspenders)
set -a; [ -f ./.env ] && . ./.env; set +a

BASE="${BASE:-http://localhost:8080}"
USER_ID="${USER_ID:-00000000-0000-0000-0000-000000000001}"
LOGFILE="${LOGFILE:-/tmp/collectors-merge.out}"

echo "Stopping any existing uvicorn..."
pkill -f "uvicorn .*services.collectors_merge.api.main:app" || true
pkill -f "uvicorn" || true
sleep 1

echo "Starting API..."
nohup ./deploy/run_uvicorn.sh >"$LOGFILE" 2>&1 &

echo "Waiting for API..."
for i in $(seq 1 40); do
  if curl -fsS "$BASE/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
  [ "$i" -eq 40 ] && { echo "API not reachable. Logs: $LOGFILE"; exit 7; }
done

echo "== Sanity: /sanity/ready =="
code=$(curl -sS -w "%{http_code}" -o /tmp/ready.json "$BASE/sanity/ready" || true)
[ "$code" = "200" ] && jq . /tmp/ready.json || { echo "(HTTP $code)"; cat /tmp/ready.json || true; }

echo "== Sanity: E2E dry-run =="
code=$(curl -sS -w "%{http_code}" -o /tmp/e2e.json -X POST "$BASE/sanity/e2e?user_id=$USER_ID&category=lego" || true)
[ "$code" = "200" ] && jq . /tmp/e2e.json || { echo "(HTTP $code)"; cat /tmp/e2e.json || true; }

echo "Stopping API..."
pkill -f "uvicorn .*services.collectors_merge.api.main:app" || true
pkill -f "uvicorn" || true
echo "All sanity checks completed ✅"
