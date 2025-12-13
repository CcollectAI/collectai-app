#!/usr/bin/env python3
import argparse
import io
import json
import os

import boto3
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("category")
    ap.add_argument("version")
    ap.add_argument("dataset_csv")
    ap.add_argument("--alphas", default="0.1,0.3,1.0,3.0,10.0")
    a = ap.parse_args()
    region = os.getenv("AWS_REGION", "eu-north-1")
    art_bucket = os.getenv("ARTIFACT_BUCKET")
    txt = s3_get(a.dataset_csv, region)
    df = pd.read_csv(io.StringIO(txt))
    if "price" not in df.columns and "label_value_eur" in df.columns:
        df = df.rename(columns={"label_value_eur": "price"})
    X = (
        df.drop(columns=["price"])
        .select_dtypes(include=[np.number])
        .fillna(0.0)
        .to_numpy()
    )
    y = df["price"].astype(float).to_numpy()
    alphas = [float(x) for x in a.alphas.split(",") if x]
    best = None
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    for alpha in alphas:
        maes = []
        for tr, te in kf.split(X):
            m = Ridge(alpha=alpha).fit(X[tr], y[tr])
            yhat = m.predict(X[te])
            maes.append(np.mean(np.abs(yhat - y[te])))
        m_mae = float(np.mean(maes))
        if best is None or m_mae < best[0]:
            best = (m_mae, alpha)
    alpha = best[1]
    # train final
    m = Ridge(alpha=alpha).fit(X, y)
    meta = {
        "category": a.category,
        "version": a.version,
        "features": [
            c
            for c in df.drop(columns=["price"])
            .select_dtypes(include=[np.number])
            .columns
        ],
        "ridge": {
            "coef": m.coef_.tolist(),
            "intercept": float(m.intercept_),
            "alpha": alpha,
        },
    }
    base = f"s3://{art_bucket}/artifacts/price/{a.category}/{a.version}"
    s3_put(f"{base}/model.json", json.dumps(meta).encode(), region)
    print(
        json.dumps(
            {
                "ok": True,
                "alpha": alpha,
                "mae_cv": best[0],
                "version": a.version,
                "artifact": f"{base}/model.json",
            }
        )
    )


if __name__ == "__main__":
    main()
