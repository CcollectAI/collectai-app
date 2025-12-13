#!/usr/bin/env bash
set -euo pipefail
: "${BUCKET:?set BUCKET env}"
PREFIXES=("raw/pokemon_cards/" "curated/pokemon_cards/" "train/pokemon_cards/v1/" "spool/vision/raw/")
TMP="ops/_s3_check_$(date +%s).txt"
echo "hello $(date)" > "$TMP"
for p in "${PREFIXES[@]}"; do
  key="${p}s3_check_$(date +%s).txt"
  echo "== $p =="
  if aws s3 cp "$TMP" "s3://$BUCKET/$key" >/dev/null; then echo "Put: PASS"; else echo "Put: FAIL"; fi
  if aws s3 cp "s3://$BUCKET/$key" /tmp/_s3_check_dl.txt >/dev/null; then echo "Get: PASS"; else echo "Get: FAIL"; fi
  if aws s3api delete-object --bucket "$BUCKET" --key "$key" >/dev/null; then echo "Delete: PASS"; else echo "Delete: FAIL"; fi
done
rm -f "$TMP" /tmp/_s3_check_dl.txt
