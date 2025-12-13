#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8081}"
echo "health:"
curl -sS "$BASE/health" | jq .
echo "predict v1 mtg:"
curl -sS -X POST "$BASE/predict/mtg" -H 'Content-Type: application/json' \
  -d '{"set":"mom","finish":"foil","rarity":"mythic","condition":"nm"}' | jq .
echo "predict2 mtg:"
curl -sS -X POST "$BASE/predict2/mtg" -H 'Content-Type: application/json' \
  -d '{"set":"mom","finish":"foil","rarity":"mythic","condition":"nm"}' | jq .
echo "market mtg:"
curl -sS -X POST "$BASE/market/mtg" -H 'Content-Type: application/json' \
  -d '{"name":"Atraxa","set":"mom","finish":"foil","rarity":"mythic","condition":"nm"}' | jq .
echo "admin models:"
curl -sS "$BASE/admin/models" | jq .
