#!/usr/bin/env python3
import json
import os
import pathlib
from collections import defaultdict

import numpy as np

CALIB = os.environ.get("CALIB_LOG", "data/training/calibration.jsonl")
MODELS = pathlib.Path(os.environ.get("MODELS_DIR", "/opt/models"))


def read_jsonl(p):
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except:
                pass
    return out


rows = read_jsonl(CALIB)
by = defaultdict(list)
for r in rows:
    try:
        pct_err = abs(r["y_true"] - r["y_pred"]) / max(1e-6, r["y_true"])
        by[r["category"]].append(min(1.0, pct_err))
    except:
        pass

for cat, errs in by.items():
    if len(errs) < 25:  # need enough points
        continue
    e = np.array(errs)
    # simple mapping: conf = 1 - clip(a*err + b, 0, 1)
    # fit a,b by least squares to match historical subjective conf ~ 1-err
    X = np.vstack([e, np.ones_like(e)]).T
    y = 1 - e
    a, b = np.linalg.lstsq(X, y, rcond=None)[0]
    calib = {"a": float(a), "b": float(b), "n": int(len(e))}
    (MODELS / cat / "calib.json").write_text(json.dumps(calib, indent=2))
    print(f"[{cat}] calib a={a:.3f}, b={b:.3f}, n={len(e)}")
print("[ok] calibration done")
