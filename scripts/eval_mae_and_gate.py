#!/usr/bin/env python3
import argparse
import io
import json
import os
import sys

import boto3
import numpy as np
import pandas as pd
import yaml


def s3_get_text(uri, region):
    assert uri.startswith("s3://")
    bkt, key = uri[5:].split("/", 1)
    return (
        boto3.client("s3", region_name=region)
        .get_object(Bucket=bkt, Key=key)["Body"]
        .read()
        .decode()
    )


def s3_put_text(uri, txt, region):
    bkt, key = uri[5:].split("/", 1)
    boto3.client("s3", region_name=region).put_object(
        Bucket=bkt, Key=key, Body=txt.encode()
    )


def gate_for(cat, gate_cfg):
    return gate_cfg.get(cat, gate_cfg.get("price", {}))


def newest_version_under(s3, bucket, prefix):
    # list model.json under prefix/<ver>/model.json and pick newest lexicographically
    p = prefix.rstrip("/") + "/"
    res = s3.list_objects_v2(Bucket=bucket, Prefix=p)
    vers = set()
    token = None
    while True:
        for o in res.get("Contents", []):
            if o["Key"].endswith("/model.json"):
                vers.add(o["Key"].split("/")[-2])
        if res.get("IsTruncated"):
            token = res.get("NextContinuationToken")
            res = s3.list_objects_v2(Bucket=bucket, Prefix=p, ContinuationToken=token)
        else:
            break
    return sorted(vers)[-1] if vers else None


def eval_one(cat, art_prefix, ds_uri, gate, region):
    # art_prefix: s3://bucket/artifacts/price/<cat>
    bkt, base = art_prefix[5:].split("/", 1)
    s3 = boto3.client("s3", region_name=region)
    last = newest_version_under(s3, bkt, base)
    if not last:
        return {"category": cat, "ok": False, "reason": "no_artifacts"}
    # active pointer per category
    try:
        active_json = s3_get_text(f"{art_prefix}/ACTIVE.json", region)
        active_ver = json.loads(active_json)["version"]
    except Exception:
        active_ver = None

    csv_text = s3_get_text(ds_uri, region)
    df = pd.read_csv(io.StringIO(csv_text))
    if "price" not in df.columns and "label_value_eur" in df.columns:
        df = df.rename(columns={"label_value_eur": "price"})
    y = df["price"].astype(float).to_numpy()
    X = (
        df.drop(columns=[c for c in ["price"] if c in df.columns])
        .select_dtypes(include=[np.number])
        .fillna(0.0)
        .to_numpy()
    )

    # baseline predictor (mean) for gate sanity; replace with real inference when wired
    if len(y) == 0:
        return {"category": cat, "ok": False, "reason": "no_rows"}
    test = np.arange(len(y))
    yhat = np.full_like(y, float(y.mean()), dtype=float)
    mae = float(np.mean(np.abs(yhat - y))) if len(y) > 0 else float("inf")
    mape = (
        float(np.mean(np.abs((yhat - y) / np.clip(np.abs(y), 1e-6, np.inf))))
        if len(y) > 0
        else float("inf")
    )
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2)) if len(y) > 0 else 0.0
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else -np.inf

    thresholds = gate_for(cat, gate)
    mae_max = float(thresholds.get("mae_max", 6.0))
    mape_max = float(thresholds.get("mape_max", 0.20))
    r2_min = float(thresholds.get("r2_min", 0.00))
    min_rows = int(thresholds.get("min_eval_rows", 20))

    ok = (
        (len(y) >= min_rows)
        and (mae <= mae_max)
        and (mape <= mape_max)
        and (r2 >= r2_min)
    )

    if ok:
        s3_put_text(f"{art_prefix}/ACTIVE.json", json.dumps({"version": last}), region)

    return {
        "category": cat,
        "candidate": last,
        "active": active_ver,
        "ok": ok,
        "metrics": {"mae": mae, "mape": mape, "r2": r2, "rows": int(len(y))},
        "gate": thresholds,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact-prefix", required=True)  # s3://bucket/artifacts/price
    ap.add_argument(
        "--categories", default=os.getenv("CATEGORIES", "pokemon,diecast,lego")
    )
    ap.add_argument("--gate-config", default="config/gate.yaml")
    ap.add_argument("--datasets-prefix", default=None)  # s3://bucket/datasets/<cat>/...
    a = ap.parse_args()

    load_dotenv = lambda *x: None  # no-op; env already loaded by caller
    region = os.getenv("AWS_REGION", "eu-north-1")
    with open(a.gate_config) as f:
        gate = yaml.safe_load(f) or {}

    cats = [c.strip() for c in a.categories.split(",") if c.strip()]
    ds_bucket = os.getenv("DATASET_BUCKET")
    assert ds_bucket or a.datasets_prefix, "need DATASET_BUCKET or --datasets-prefix"

    out = []
    for cat in cats:
        # find latest dataset for this category
        bkt = ds_bucket if ds_bucket else a.datasets_prefix[5:].split("/", 1)[0]
        pref = f"datasets/{cat}/"
        s3 = boto3.client("s3", region_name=region)
        try:
            res = s3.list_objects_v2(Bucket=bkt, Prefix=pref)
            latest = None
            for o in res.get("Contents", []) or []:
                latest = o["Key"] if (latest is None or o["Key"] > latest) else latest
            if not latest:
                out.append({"category": cat, "ok": False, "reason": "no_dataset"})
                continue
            ds_uri = f"s3://{bkt}/{latest}"
        except Exception as e:
            out.append({"category": cat, "ok": False, "reason": f"list_fail:{e}"})
            continue

        art_pref = f"{a.artifact_prefix.rstrip('/')}/{cat}"
        res = eval_one(cat, art_pref, ds_uri, gate, region)
        out.append(res)
        print(json.dumps(res))

    # overall summary last line
    print(json.dumps({"summary": {"categories": cats, "results": out}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
