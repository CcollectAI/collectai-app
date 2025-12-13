#!/usr/bin/env bash
set -euo pipefail
JSONL="${1:-data/training/training.jsonl}"
PYTHON="python"
# ensure dirs
mkdir -p /opt/models
# Train each category model (ridge if enough data; else dummy)
$PYTHON - <<'PY'
from app.training.train_regressor import train_one
targets = {
    "lego": "/opt/models/lego/model.joblib",
    "diecast": "/opt/models/diecast/model.joblib",
    "mtg": "/opt/models/mtg/model.joblib",
    "lorcana": "/opt/models/lorcana/model.joblib",
    "fab": "/opt/models/fab/model.joblib",
    "warhammer": "/opt/models/warhammer/model.joblib",
    "gunpla": "/opt/models/gunpla/model.joblib",
    "designer_toys": "/opt/models/designer_toys/model.joblib",
}
for cat, out in targets.items():
    status = train_one(cat, "data/training/training.jsonl", out)
    print(f"[{cat}] {status} -> {out}")
PY
echo "[ok] training complete."
