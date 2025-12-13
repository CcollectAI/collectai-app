#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://localhost:8080}"
USER_ID="${USER_ID:-00000000-0000-0000-0000-000000000001}"
CATEGORY="${CATEGORY:-lego}"
TITLE="${TITLE:-X-Wing test}"

set -a; [ -f ./.env ] && . ./.env; set +a

echo "== /health =="
curl -sS -w "\nHTTP %{http_code}\n" "$BASE/health" | tee /tmp/health.json

echo "== /items/upsert =="
UP=$(curl -sS -w "\nHTTP %{http_code}\n" \
  -H 'content-type: application/json' -X POST "$BASE/items/upsert" \
  -d '{
        "user_id":"'"$USER_ID"'",
        "category":"'"$CATEGORY"'",
        "title":"'"$TITLE"'",
        "sealed":true,
        "attributes_json":{"set_no":"10240","sealed":true,"retired":true,"piece_count":1559}
      }')

# Print the JSON part safely (first line) then capture HTTP code (last line)
echo "$UP" | head -n1 | jq . || true
CODE=$(echo "$UP" | tail -n1 | awk '{print $2}')
if [ "$CODE" != "200" ]; then
  echo "ERROR: upsert HTTP $CODE"; exit 2
fi

ITEM_ID=$(echo "$UP" | head -n1 | jq -r '.item_id // empty')

if [ -z "$ITEM_ID" ]; then
  echo "== /items/list (fallback) =="
  LIST=$(curl -sS "$BASE/items/list?user_id=$USER_ID&category=$CATEGORY&limit=1")
  echo "$LIST" | jq .
  ITEM_ID=$(echo "$LIST" | jq -r '.items[0].id // empty')
fi

if [ -z "${ITEM_ID:-}" ]; then
  echo "ERROR: Could not determine ITEM_ID"; exit 3
fi
echo "ITEM_ID=$ITEM_ID"

# Build JSON with item_id as a STRING (UUID)
jq -n --arg item_id "$ITEM_ID" --arg grade "PSA 10" --argjson sealed true \
  '{item_id: $item_id, attributes:{grade:$grade, sealed:$sealed}}' > /tmp/predict_body.json

echo "== request body =="
cat /tmp/predict_body.json

echo "== /predict_v2 =="
OUT=$(curl -sS -w "\nHTTP %{http_code}\n" \
  -H 'content-type: application/json' -X POST "$BASE/predict_v2" \
  --data-binary @/tmp/predict_body.json)
echo "$OUT" | head -n1 | jq . || true
CODE=$(echo "$OUT" | tail -n1 | awk '{print $2}')
if [ "$CODE" != "200" ]; then
  echo "ERROR: predict_v2 HTTP $CODE"; exit 4
fi
