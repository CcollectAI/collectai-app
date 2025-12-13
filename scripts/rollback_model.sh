#!/usr/bin/env bash
set -euo pipefail
CAT="$1"; TS="$2"  # usage: scripts/rollback_model.sh mtg 1759350000
BASE="${MODELS_DIR:-/opt/models}/$CAT"
test -f "$BASE/model_v${TS}.joblib"
cp -f "$BASE/model_v${TS}.joblib" "$BASE/model.joblib"
test -f "$BASE/model_info_v${TS}.json" && cp -f "$BASE/model_info_v${TS}.json" "$BASE/model_info.json" || true
echo "[ok] rolled back $CAT to $TS"
