#!/usr/bin/env bash
set -euo pipefail
REGION="${AWS_REGION:-eu-north-1}"
BUCKET="${ARTIFACT_BUCKET:?missing ARTIFACT_BUCKET}"
STAMP="$(date +%Y%m%d_%H%M%S)"

train_one() {
  local CAT="$1"
  local OUT="artifacts/${CAT}/${STAMP}"
  mkdir -p "${OUT}"
  python3 - <<PY
from pathlib import Path
import numpy as np, joblib, os, json, sys
from sklearn.dummy import DummyRegressor
from sklearn.pipeline import Pipeline

cat = "${CAT}"
out = Path("${OUT}")
out.mkdir(parents=True, exist_ok=True)

# choose expected feature length per category (keep in sync with request payloads)
n_features = 6 if cat=="diecast" else 6

X = np.vstack([np.zeros(n_features), np.ones(n_features)]).astype(float)
y = np.array([120.0, 240.0]) if cat=="diecast" else np.array([150.0, 150.0])

m = Pipeline([("reg", DummyRegressor(strategy="mean"))]).fit(X,y)
joblib.dump(m, out/"model.pkl")
print(json.dumps({"cat":cat, "model":str(out/"model.pkl"), "size": (out/"model.pkl").stat().st_size}))
PY

  # move "active" symlink
  ln -sfn "$(readlink -f "${OUT}")" "artifacts/${CAT}/active"
}

promote_pointers() {
  local CAT="$1"
  local VER="$(basename "$(readlink -f "artifacts/${CAT}/active")")"
  printf '{"version":"%s"}' "$VER" | aws s3 cp - "s3://${BUCKET}/artifacts/price/${CAT}/ACTIVE.json"   --region "$REGION" --content-type application/json
  printf '{"version":"%s"}' "$VER" | aws s3 cp - "s3://${BUCKET}/artifacts/price/${CAT}/CANDIDATE.json" --region "$REGION" --content-type application/json || true
  echo "${CAT} -> ${VER}"
}

train_one diecast
train_one lego
promote_pointers diecast
promote_pointers lego
