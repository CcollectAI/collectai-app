#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/.."; pwd)"
cd "$APP_DIR"

# env + defaults
set -a; [ -f "$APP_DIR/env/.env" ] && . "$APP_DIR/env/.env"; set +a
HOST="${HOST:-0.0.0.0}"; PORT="${PORT:-8080}"; WORKERS="${WORKERS:-2}"
IMPORT="${APP_IMPORT:-}"

# candidate list (ordered)
CAND=( "main:app" "app:app" "app.main:app" "app_placeholder:app" )

# pick target
TARGET=""
if [ -n "$IMPORT" ]; then
  TARGET="$IMPORT"
else
  for c in "${CAND[@]}"; do
    if "$APP_DIR/.venv/bin/python3" - <<PY 2>/dev/null
import importlib, sys
spec = "${c}"
mod, attr = (spec.split(":",1)+["app"])[:2]
m = importlib.import_module(mod)
getattr(m, attr)
print("OK")
PY
    then TARGET="$c"; break; fi
  done
fi

if [ -z "$TARGET" ]; then
  echo "[launcher] FATAL: ASGI app not found. Tried: ${CAND[*]} and APP_IMPORT='${IMPORT:-}'" >&2
  exit 1
fi

echo "[launcher] using TARGET=$TARGET on $HOST:$PORT (workers=$WORKERS)"
exec "$APP_DIR/.venv/bin/uvicorn" "$TARGET" --host "$HOST" --port "$PORT" --workers "$WORKERS"
