#!/usr/bin/env python3
import io
import json
import logging
import os
import sys

import boto3
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

logger = logging.getLogger(__name__)


def s3_get(uri, region):
    assert uri.startswith("s3://")
    bkt, key = uri[5:].split("/", 1)
    return (
        boto3.client("s3", region_name=region)
        .get_object(Bucket=bkt, Key=key)["Body"]
        .read()
        .decode()
    )


def s3_put(uri, data: bytes, region):
    bkt, key = uri[5:].split("/", 1)
    boto3.client("s3", region_name=region).put_object(Bucket=bkt, Key=key, Body=data)


def load_cat_cfg(cat: str, base: str) -> dict:
    p_json = os.path.join(base, f"{cat}.json")
    if os.path.isfile(p_json):
        with open(p_json) as f:
            return json.load(f)
    return {}


def coerce_numeric(df: pd.DataFrame, cols) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for c in cols:
        if c in df.columns:
            s = pd.to_numeric(df[c], errors="coerce")
            # treat booleans-like strings
            if s.isna().all() and df[c].dtype == object:
                out[c] = (
                    df[c]
                    .astype(str)
                    .str.lower()
                    .isin(["1", "true", "yes", "y", "t"])
                    .astype(float)
                )
            else:
                out[c] = s
    return out


def main(cat, ver, dataset_csv, alpha):
    region = os.getenv("AWS_REGION", "eu-north-1")
    art_bucket = os.getenv("ARTIFACT_BUCKET")
    assert art_bucket, "ARTIFACT_BUCKET missing"
    cfg_dir = os.getenv("CATEGORY_CONFIG_DIR", "config/categories")

    # load dataset
    txt = s3_get(dataset_csv, region)
    df = pd.read_csv(io.StringIO(txt))
    # normalize common label column
    if "price" not in df.columns and "label_value_eur" in df.columns:
        df = df.rename(columns={"label_value_eur": "price"})
    if "price" not in df.columns:
        raise SystemExit("dataset missing price/label_value_eur")

    # prefer category-config numeric list
    cfg = load_cat_cfg(cat, cfg_dir)
    cfg_numeric = list((cfg.get("numeric") or {}).keys())

    X = None
    feats = []

    if cfg_numeric:
        X = coerce_numeric(df, cfg_numeric)
        # drop non-varying all-NaN columns
        X = X.loc[:, X.notna().any(axis=0)]
        feats = list(X.columns)

    if not feats:
        # fallback: coerce everything numeric except price
        num_cols = [c for c in df.columns if c != "price"]
        X = coerce_numeric(df, num_cols)
        X = X.loc[:, X.notna().any(axis=0)]
        feats = [c for c in X.columns if c != "price"]

    # final cleanup
    X = X.fillna(0.0).astype(float)
    if "price" in X.columns:
        X = X.drop(columns=["price"])
    y = pd.to_numeric(df["price"], errors="coerce").fillna(0.0).astype(float)

    # last-resort bias feature if still empty
    if X.shape[1] == 0:
        X = pd.DataFrame({"bias": np.ones(len(df), dtype=float)})
        feats = ["bias"]

    # train
    model = Ridge(alpha=alpha).fit(X.values, y.values)

    # export
    payload = {
        "category": cat,
        "version": ver,
        "features": feats,
        "ridge": {
            "coef": model.coef_.tolist(),
            "intercept": float(model.intercept_),
            "alpha": float(alpha),
        },
    }

    base = f"s3://{art_bucket}/artifacts/price/{cat}/{ver}"
    s3_put(f"{base}/model.json", json.dumps(payload).encode(), region)
    buf = io.BytesIO()
    joblib.dump(
        {"features": feats, "coef": model.coef_, "intercept": model.intercept_}, buf
    )
    s3_put(f"{base}/model.joblib", buf.getvalue(), region)
    logger.info(
        json.dumps(
            {
                "ok": True,
                "artifact_uri": f"{base}/model.json",
                "features": feats,
                "rows": int(len(df)),
            }
        )
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cat = sys.argv[1]
    ver = sys.argv[2]
    ds = sys.argv[3]
    a = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
    main(cat, ver, ds, a)
