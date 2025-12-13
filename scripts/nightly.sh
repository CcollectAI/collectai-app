#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/.."; pwd)"
LOG_DIR="$APP_DIR/logs"; mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/nightly.log"
exec >>"$LOG" 2>&1
echo "[$(date -Is)] nightly start"

set -a; [ -f "$APP_DIR/env/.env" ] && . "$APP_DIR/env/.env"; set +a
REGION="${AWS_REGION:-eu-north-1}"
: "${ARTIFACT_BUCKET:?ARTIFACT_BUCKET missing}"; : "${DATASET_BUCKET:?DATASET_BUCKET missing}"
ART_PREFIX="s3://${ARTIFACT_BUCKET}/artifacts/price"

echo "[$(date -Is)] build dataset"
DS_URI="$(python3 "$APP_DIR/scripts/build_dataset_from_feedback.py" || true)"
echo "[$(date -Is)] dataset=${DS_URI:-none}"

CAT="${NIGHTLY_CATEGORY:-pokemon}"
VER="v$(date +%Y.%m.%d.%H%M%S)"
ALPHA="${RIDGE_ALPHA:-1.0}"

if [ -n "${DS_URI:-}" ] && [ -f "$APP_DIR/scripts/train_ridge_from_csv.py" ]; then
  echo "[$(date -Is)] train ridge cat=$CAT ver=$VER alpha=$ALPHA"
  python3 "$APP_DIR/scripts/train_ridge_from_csv.py" "$CAT" "$VER" "$DS_URI" "$ALPHA" || true
else
  echo "[$(date -Is)] skip train (no dataset or trainer)"
fi

echo "[$(date -Is)] eval/gate"
python3 "$APP_DIR/scripts/eval_mae_and_gate.py" --artifact-prefix "$ART_PREFIX" --gate-config "$APP_DIR/config/gate.yaml" || true

echo "[$(date -Is)] nightly done"
