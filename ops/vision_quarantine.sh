#!/usr/bin/env bash
set -euo pipefail
: "${SPOOL_S3_BUCKET:?set SPOOL_S3_BUCKET}"
REGION="${AWS_DEFAULT_REGION:-eu-north-1}"
Q_PREFIX="${VISION_QUAR_PREFIX:-spool/vision/quarantine/}"

TMP="$(mktemp)"
AWS_DEFAULT_REGION="$REGION" python ops/vision_s3_sanity.py > "$TMP"

jq -r '.bad_items[] | select(.key) | .key' "$TMP" | while read -r KEY; do
  BASE="$(basename "$KEY")"
  echo "Quarantine $KEY -> s3://$SPOOL_S3_BUCKET/$Q_PREFIX$BASE"
  aws s3 mv "s3://$SPOOL_S3_BUCKET/$KEY" "s3://$SPOOL_S3_BUCKET/$Q_PREFIX$BASE"
done
rm -f "$TMP"
