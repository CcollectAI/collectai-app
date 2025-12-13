#!/usr/bin/env bash
set -euo pipefail

API_KEY="${API_KEY:-dev-local-secret-collectai}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8081}"

echo "== marketplace health =="
curl -sS "$BASE_URL/marketplace/health" | jq .

echo
echo "== listings (GET) =="
curl -sS "$BASE_URL/marketplace/listings" \
  -H "X-API-Key: $API_KEY" | jq .

echo
echo "== buyer-intents (GET) =="
curl -sS "$BASE_URL/marketplace/buyer-intents" \
  -H "X-API-Key: $API_KEY" | jq .

echo
echo "== agreements (GET) =="
curl -sS "$BASE_URL/marketplace/agreements" \
  -H "X-API-Key: $API_KEY" | jq .

echo
echo "== ratings (GET) =="
curl -sS "$BASE_URL/marketplace/ratings" \
  -H "X-API-Key: $API_KEY" | jq .
