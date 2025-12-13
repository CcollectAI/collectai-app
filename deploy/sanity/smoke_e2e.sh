#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://localhost:8080}"
echo "Waiting for API at $BASE ..."; 
for i in $(seq 1 20); do 
  if curl -fsS "$BASE/health" >/dev/null 2>&1; then break; fi; 
  sleep 0.5; 
  if [ "$i" -eq 20 ]; then echo "API not reachable (timeout)"; exit 7; fi; 
done
USER_ID="${USER_ID:-00000000-0000-0000-0000-000000000001}"

echo "1) /health"
curl -s "$BASE/health" | jq .

echo "2) /sanity/ready"
curl -s "$BASE/sanity/ready" | jq .

echo "3) /sanity/e2e (lego)"
curl -s -X POST "$BASE/sanity/e2e?user_id=$USER_ID&category=lego" | jq .

echo "4) /market/normalize"
curl -s "$BASE/market/normalize?text=LEGO%2010240%20X-Wing%20Starfighter&category=lego" | jq .

echo "5) /portfolio/aggregate"
curl -s "$BASE/portfolio/aggregate?user_id=$USER_ID" | jq .

echo "OK ✅"
