#!/usr/bin/env python3
import datetime as dt
import io
import json
import logging
import os

import boto3
import pandas as pd
from dotenv import load_dotenv

from supabase import create_client

logger = logging.getLogger(__name__)


def main():
    load_dotenv(os.path.join("env", ".env"))
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE")
    assert url and key, "supabase creds missing"
    sb = create_client(url, key)
    rows = sb.table("feedback").select("*").execute().data or []
    if not rows:
        logger.info("No feedback rows found")
        return
    # group by category; numeric features only
    out = []
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bucket = os.getenv("DATASET_BUCKET")
    region = os.getenv("AWS_REGION", "eu-north-1")
    assert bucket, "DATASET_BUCKET missing"
    s3 = boto3.client("s3", region_name=region)
    cats = {}
    for r in rows:
        cat = (r.get("category") or "unknown").strip().lower()
        feats = r.get("features") or {}
        rec = {"price": float(r.get("label_value_eur") or r.get("price") or 0)}
        for k, v in feats.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                rec[k] = float(v)
        cats.setdefault(cat, []).append(rec)
    for cat, recs in cats.items():
        df = pd.DataFrame(recs).dropna(subset=["price"])
        if df.empty:
            continue
        key = f"datasets/{cat}/feedback_{now}.csv"
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue().encode("utf-8"))
        out.append({"category": cat, "s3": f"s3://{bucket}/{key}", "rows": len(df)})
    logger.info(json.dumps(out))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
