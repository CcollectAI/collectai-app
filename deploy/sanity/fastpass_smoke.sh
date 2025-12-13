#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-http://localhost:8080}"

tmp="$(mktemp /tmp/fp.XXXX).jpg"
printf 'fake image bytes\n' > "$tmp"

echo "== /readyz =="; curl -fsS "$BASE/readyz" | jq .
echo "== /ingest/fastpass_v2 =="

curl -fsS -X POST "$BASE/ingest/fastpass_v2" \
  -F "user_id=${USER_ID:-00000000-0000-0000-0000-000000000001}" \
  -F "category=${CATEGORY:-lego}" \
  -F "watchlist=1" \
  -F "guide_recent_days=90" \
  -F "guide_min_seller_score=0.98" \
  -F "guide_iqr_k=1.5" \
  -F "image=@${tmp}" | jq .

rm -f "$tmp"
echo "OK ✅"
