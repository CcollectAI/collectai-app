#!/usr/bin/env bash
set -euo pipefail
: "${BUCKET:?set BUCKET env}"
PREFIX="${1:-spool/vision/raw/}"
THRESH="${2:-4096}"
DRY="${DRY_RUN:-1}" # set DRY_RUN=0 to actually delete

mapfile -t KEYS < <(aws s3api list-objects-v2 \
  --bucket "$BUCKET" \
  --prefix "$PREFIX" \
  --query "Contents[?Size < \`${THRESH}\`].Key" \
  --output text | tr '\t' '\n' | sed '/^$/d')

echo "Found ${#KEYS[@]} objects < ${THRESH}B under s3://$BUCKET/$PREFIX"
for k in "${KEYS[@]}"; do
  if [[ "$DRY" == "0" ]]; then
    aws s3api delete-object --bucket "$BUCKET" --key "$k"
    echo "deleted $k"
  else
    echo "would delete $k"
  fi
done
