#!/usr/bin/env python3
import json
import os
import pathlib
import sys
from collections import defaultdict

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

IN = sys.argv[1] if len(sys.argv) > 1 else "data/training/training.jsonl"
MODELS_DIR = pathlib.Path(os.environ.get("MODELS_DIR", "/opt/models"))
LOW_N = int(os.environ.get("TRAIN_MIN_N", "25"))
ALPHA = float(os.environ.get("RIDGE_ALPHA", "1.0"))
WINSOR = float(os.environ.get("WINSOR", "0.05"))
TOPK = int(os.environ.get("FI_TOPK", "20"))


def winsorize(series: list[float], p: float) -> list[float]:
    if not series:
        return series
    lo = np.quantile(series, p)
    hi = np.quantile(series, 1 - p)
    return [min(max(v, lo), hi) for v in series]


def load_rows(path: str) -> list[dict]:
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
                if j.get("y") is None:
                    continue
                out.append(j)
            except Exception:
                pass
    return out


rows = load_rows(IN)
by_cat = defaultdict(list)
for r in rows:
    by_cat[r["category"]].append(r)

MODELS_DIR.mkdir(parents=True, exist_ok=True)
for cat, items in by_cat.items():
    X_rows, ys = [], []
    for it in items:
        feats = it.get("features", {})
        X_rows.append(feats)
        ys.append(float(it["y"]))

    n = len(ys)
    cat_dir = MODELS_DIR / cat
    cat_dir.mkdir(parents=True, exist_ok=True)

    y_arr = np.array(ys, dtype=float)
    y_w = winsorize(y_arr, WINSOR) if n >= 10 else y_arr

    df = pd.json_normalize(X_rows)
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype("string")
    X = pd.get_dummies(df, dummy_na=True)

    info = {
        "category": cat,
        "n_obs": n,
        "winsor_p": WINSOR if n >= 10 else 0.0,
        "features": list(df.columns),
        "dummies": list(X.columns),
        "trainer": "ridge" if n >= LOW_N else "dummy",
        "alpha": ALPHA,
    }

    model_path = cat_dir / "model.joblib"
    info_path = cat_dir / "model_info.json"

    if n >= LOW_N:
        mdl = Ridge(alpha=ALPHA, random_state=0)
        mdl.fit(X.values, y_w)
        joblib.dump({"model": "ridge", "sk": mdl, "cols": list(X.columns)}, model_path)
        # feature importance ~ abs(coef)
        coefs = getattr(mdl, "coef_", None)
        if coefs is not None and len(info["dummies"]) == len(coefs):
            pairs = sorted(
                zip(info["dummies"], map(abs, coefs)), key=lambda t: t[1], reverse=True
            )
            info["feature_importance"] = [
                {"feature": k, "weight": float(v)} for k, v in pairs[:TOPK]
            ]
        info["model_name"] = "ridge"
        print(f"[{cat}] ridge:n={n}|p={X.shape[1]} -> {model_path}")
    else:
        med = float(np.median(y_arr)) if n > 0 else 30.0
        joblib.dump({"model": "dummy", "median": med}, model_path)
        info["model_name"] = "dummy"
        info["median"] = med
        print(f"[{cat}] dummy:low_n={n} -> {model_path}")

    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)

print("[ok] done")
