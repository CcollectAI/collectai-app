#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo "[nightly] train start: $(date -Is)"
./scripts/train_from_events.sh
curl -fsS -X POST http://127.0.0.1:8081/admin/reload_models_now >/dev/null || true
echo "[nightly] train done:  $(date -Is)"
