#!/usr/bin/env python3
import json
import logging
import os
import pathlib
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

IN = "data/training/training.jsonl"
MODELS_DIR = pathlib.Path(os.environ.get("MODELS_DIR", "/opt/models"))
LOW_N = int(os.environ.get("TRAIN_MIN_N", "8"))
ALPHA = float(os.environ.get("RIDGE_ALPHA", "1.0"))


def load_rows(p):
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if j.get("y") is None:
                continue
            out.append(j)
    return out


rows = load_rows(IN)
by = defaultdict(list)
for r in rows:
    by[r["category"]].append(r)
ts = int(time.time())
for cat, lst in by.items():
    ys = [float(x["y"]) for x in lst]
    n = len(ys)
    X = pd.get_dummies(
        pd.json_normalize([x.get("features", {}) for x in lst]), dummy_na=True
    )
    catdir = MODELS_DIR / cat
    catdir.mkdir(parents=True, exist_ok=True)
    if n >= LOW_N:
        m = Ridge(alpha=ALPHA).fit(X.values, np.array(ys))
        joblib.dump(
            {"model": "ridge", "sk": m, "cols": list(X.columns)},
            catdir / f"model_v{ts}.joblib",
        )
        (catdir / "model.joblib").unlink(missing_ok=True)
        (catdir / f"model_v{ts}.joblib").rename(catdir / "model.joblib")
        info = {
            "category": cat,
            "n_obs": n,
            "model_name": "ridge",
            "dummies": list(X.columns),
            "alpha": ALPHA,
            "ts": ts,
        }
    else:
        med = float(np.median(ys)) if n else 30.0
        joblib.dump({"model": "dummy", "median": med}, catdir / f"model_v{ts}.joblib")
        (catdir / "model.joblib").unlink(missing_ok=True)
        (catdir / f"model_v{ts}.joblib").rename(catdir / "model.joblib")
        info = {
            "category": cat,
            "n_obs": n,
            "model_name": "dummy",
            "median": med,
            "ts": ts,
        }
    (catdir / f"model_info_v{ts}.json").write_text(json.dumps(info, indent=2))
    (catdir / "model_info.json").write_text(json.dumps(info, indent=2))
logger.info("versioned training complete %s", ts)
