#!/usr/bin/env bash
set -euo pipefail
export PYTHONUNBUFFERED=1

# Move to repo root (this file lives in deploy/)
cd "$(dirname "$0")/.."

# Ensure local repo is at the front of module resolution
export PYTHONPATH="$(pwd):${PYTHONPATH:-}"

# Let uvicorn itself load .env (and we’re in repo root)
exec uvicorn services.collectors_merge.api.main:app \
  --app-dir . \
  --host 0.0.0.0 --port 8080 --proxy-headers \
  --env-file .env
