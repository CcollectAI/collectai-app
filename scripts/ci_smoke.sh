#!/usr/bin/env bash
set -euo pipefail
BASE=${BASE:-http://127.0.0.1:8081}
echo "[1] health:"; curl -sS $BASE/health | jq .
echo "[2] version:"; curl -sS $BASE/version | jq .
echo "[3] routes:"; curl -sS $BASE/health/details | jq '.routes|length'
echo "[4] mtg predict:"; curl -sS -H "X-API-Key: ${PUBLIC_API_KEY:-demo-key-123}" -H 'Content-Type: application/json' -d '{"set":"mom","finish":"foil","rarity":"mythic"}' $BASE/predict/mtg | jq .
echo "[5] metrics:"; curl -sS "$BASE/metrics/preview?category=mtg" | jq .
echo "[ok]"
