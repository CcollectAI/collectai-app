#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/.."; pwd)"
LOG_DIR="$APP_DIR/logs"; mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/nightly_multi.log"
exec >>"$LOG" 2>&1
echo "[$(date -Is)] nightly-multi start"
set -a; [ -f "$APP_DIR/env/.env" ] && . "$APP_DIR/env/.env"; set +a
REGION="${AWS_REGION:-eu-north-1}"
: "${ARTIFACT_BUCKET:?}"; : "${DATASET_BUCKET:?}"
CATS="${CATEGORIES:-pokemon,diecast,lego}"
ART_BASE="s3://${ARTIFACT_BUCKET}/artifacts/price"

echo "[$(date -Is)] build datasets"
DS_JSON="$(python3 "$APP_DIR/scripts/build_dataset_from_feedback.py" || true)"
echo "[$(date -Is)] datasets=${DS_JSON}"

VER="v$(date +%Y.%m.%d.%H%M%S)"
echo "[$(date -Is)] train grid ver=$VER"
python3 - "$VER" <<'PY'
import os, json, subprocess
VER=os.environ["VER"]
CATS=[c.strip() for c in os.environ.get("CATS","").split(",") if c.strip()]
J=os.environ.get("DS_JSON","[]")
try: ds=json.loads(J)
except Exception: ds=[]
bycat={d["category"]:d["s3"] for d in ds if "category" in d and "s3" in d}
for cat in CATS:
    dsuri=bycat.get(cat)
    if not dsuri: 
        print(f"skip {cat} (no dataset)")
        continue
    print(f"grid-train {cat} {dsuri}")
    subprocess.run(["python3","scripts/train_ridge_grid.py",cat,VER,dsuri,"--alphas","0.1,0.3,1.0,3.0,10.0"],check=False)
PY

echo "[$(date -Is)] eval/gate"
python3 "$APP_DIR/scripts/eval_mae_and_gate.py" --artifact-prefix "$ART_BASE" --categories "$CATS" --gate-config "$APP_DIR/config/gate.yaml" || true
echo "[$(date -Is)] nightly-multi done"
