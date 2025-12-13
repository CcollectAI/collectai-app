#!/usr/bin/env bash
set -euo pipefail
: "${BUCKET:?Set BUCKET env first, e.g., export BUCKET='collectai-datasets'}"
: "${AWS_DEFAULT_REGION:=eu-central-1}"

OUT="ops/vision/predictions-$(date +%Y%m%dT%H%M%S).jsonl"
TMPDIR="$(mktemp -d)"
echo "Writing to $OUT"

# Pull up to 20 keys under raw/
mapfile -t KEYS < <(aws s3api list-objects-v2 \
  --bucket "$BUCKET" \
  --prefix "spool/vision/raw/" \
  --query 'Contents[?Size>`4096`].Key' \
  --max-items 20 \
  --output text | tr '\t' '\n' | sed '/^$/d')

if [ "${#KEYS[@]}" -eq 0 ]; then
  echo "No eligible images (>4KB) found under spool/vision/raw/ — aborting."
  exit 0
fi

for key in "${KEYS[@]}"; do
  f="$TMPDIR/$(basename "$key")"
  echo "Downloading s3://$BUCKET/$key"
  aws s3 cp "s3://$BUCKET/$key" "$f" >/dev/null

  echo "Predicting $f"
  RESP="$(curl -sS -F "file=@$f" http://127.0.0.1:8081/vision/predict || true)"
  if [ -z "$RESP" ]; then
    echo "WARN: empty response for $key" >&2
    continue
  fi
  # Write one JSON line: {key, response}
  printf '{"s3_key":%q,"prediction":%s}\n' "$key" "$RESP" >> "$OUT"
done

echo "Created $OUT"
aws s3 cp "$OUT" "s3://$BUCKET/spool/vision/predictions/$(basename "$OUT")"
echo "Uploaded to s3://$BUCKET/spool/vision/predictions/$(basename "$OUT")"

rm -rf "$TMPDIR"
