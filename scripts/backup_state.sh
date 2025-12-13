#!/usr/bin/env bash
set -euo pipefail
APP="$HOME/collectors-merge-recovered"
set -a; . "$APP/env/.env"; set +a
REGION="${AWS_REGION:-eu-north-1}"
DST="s3://${DATASET_BUCKET}/backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$APP/.bk"
tar -czf "$APP/.bk/repo.tgz" -C "$APP" env/.env config/ logs/ || true
aws s3 cp "$APP/.bk/repo.tgz" "$DST/repo.tgz" --region "$REGION"
aws s3 cp "s3://${ARTIFACT_BUCKET}/artifacts/price/ACTIVE.json" "$DST/ACTIVE.json" --region "$REGION" || true
echo "$DST"
