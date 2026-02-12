#!/usr/bin/env python3
import argparse
import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact-prefix", required=True)  # s3://bucket/artifacts/price
    ap.add_argument("--version", required=True)
    ap.add_argument("--region", default=os.getenv("AWS_REGION", "eu-north-1"))
    a = ap.parse_args()
    assert a.artifact_prefix.startswith("s3://")
    bkt, key = a.artifact_prefix[5:].split("/", 1)
    s3 = boto3.client("s3", region_name=a.region)
    body = json.dumps({"version": a.version}).encode()
    s3.put_object(Bucket=bkt, Key=f"{key.rstrip('/')}/ACTIVE.json", Body=body)
    logger.info(json.dumps({"ok": True, "active": a.version}))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
