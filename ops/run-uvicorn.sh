#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/collectors-merge-recovered

# --- hard env for offline mode + webhook ---
export PORT=8081
export DB_ENABLED=false
export DB_OPTIONAL=1
export METRICS_ENABLED=0

# API key (if not already present)
: "${INGEST_API_KEY:=}"
if [ -z "${INGEST_API_KEY}" ]; then
  export INGEST_API_KEY="$(openssl rand -hex 16)"
fi

# Webhook partner secret (example: acme)
: "${WEBHOOK_SECRET_ACME:=changeme_acme}"

# Spooling + idempotency
export INGEST_SPOOL_ENABLE=1
export INGEST_SPOOL_DIR="/home/ubuntu/collectors-merge-recovered/ops/spool"
export IDEMPOTENCY_DIR="/home/ubuntu/collectors-merge-recovered/ops/idem"

mkdir -p "$INGEST_SPOOL_DIR" "$IDEMPOTENCY_DIR"

# Run
exec ./.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port "$PORT"
