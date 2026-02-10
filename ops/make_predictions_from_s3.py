#!/usr/bin/env python3
import argparse
import json
import logging
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone

import boto3
import requests

logger = logging.getLogger(__name__)

def list_good_images(s3, bucket, prefix, max_items=200, min_bytes=4096):
    paginator = s3.get_paginator("list_objects_v2")
    n = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Size"] >= min_bytes and not obj["Key"].endswith("/"):
                yield obj["Key"], obj["Size"]
                n += 1
                if n >= max_items:
                    return

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--prefix", default="spool/vision/raw/")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--min-bytes", type=int, default=4096)
    ap.add_argument("--api", default="http://127.0.0.1:8081/vision/predict")
    ap.add_argument("--out", default="ops/vision/predictions-%Y%m%dT%H%M%S.jsonl")
    ap.add_argument("--s3-out", default="s3://{bucket}/spool/vision/predictions/")
    ap.add_argument("--model-version", default="clip-v1.0.0")
    args = ap.parse_args()

    s3 = boto3.client("s3")
    ts = time.strftime(args.out)
    os.makedirs(os.path.dirname(ts), exist_ok=True)

    tmpdir = tempfile.mkdtemp(prefix="pred_s3_")
    written = 0
    with open(ts, "w", encoding="utf-8") as w:
        for key, size in list_good_images(s3, args.bucket, args.prefix, args.limit, args.min_bytes):
            # Download to tmp
            local = os.path.join(tmpdir, key.split("/")[-1])
            s3.download_file(args.bucket, key, local)
            with open(local, "rb") as fh:
                files = {"file": fh}
                try:
                    resp = requests.post(args.api, files=files, timeout=60)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    data = {"error": str(e)}

            rec = {
                "s3_key": key,
                "size": size,
                "model_version": args.model_version,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "prediction": data
            }
            w.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1

    # Optional upload to S3
    if args.s3_out:
        m = re.match(r"s3://([^/]+)/(.+)", args.s3_out.format(bucket=args.bucket))
        if m:
            out_bucket, out_prefix = m.groups()
            dest = f"{out_prefix.rstrip('/')}/{os.path.basename(ts)}"
            s3.upload_file(ts, out_bucket, dest)
            logger.info("Uploaded -> s3://%s/%s", out_bucket, dest)
    logger.info("ok=True written=%d out=%s", written, ts)

if __name__ == "__main__":
    sys.exit(main())
