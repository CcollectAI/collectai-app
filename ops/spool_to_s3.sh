#!/usr/bin/env bash
set -euo pipefail
REPO="/home/ubuntu/collectors-merge-recovered"
SPOOL_DIR="${INGEST_SPOOL_DIR:-$REPO/ops/spool}"
BUCKET="${SPOOL_S3_BUCKET:?set SPOOL_S3_BUCKET}"
PREFIX="${SPOOL_S3_PREFIX:-spool/}"
shopt -s nullglob
for f in "$SPOOL_DIR"/agent_ingest_*.jsonl; do
  base=$(basename "$f")
  aws s3 cp "$f" "s3://$BUCKET/${PREFIX}${base}"
done
