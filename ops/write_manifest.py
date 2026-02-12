import json
import logging
import os
import time

import boto3

logger = logging.getLogger(__name__)

BUCKET = os.environ["SPOOL_S3_BUCKET"]
PREFIX = os.environ.get("SPOOL_S3_PREFIX", "spool/")
REGION = os.environ.get("AWS_DEFAULT_REGION", "eu-north-1")
MANIFEST_PREFIX = os.environ.get("SPOOL_MANIFEST_PREFIX", "spool/_manifests/")


def main():
    s3 = boto3.client("s3", region_name=REGION)
    date = time.strftime("%Y/%m/%d")
    key = f"{MANIFEST_PREFIX}{date}/manifest-{int(time.time())}.json"
    # list current day objects under spool/
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{PREFIX}")
    files = [{"key": obj["Key"], "size": obj["Size"], "etag": obj["ETag"]} for obj in resp.get("Contents", [])]
    body = json.dumps({"generated_at": int(time.time()), "files": files}, ensure_ascii=False).encode()
    s3.put_object(Bucket=BUCKET, Key=key, Body=body, ContentType="application/json")
    logger.info("Wrote s3://%s/%s with %d entries", BUCKET, key, len(files))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
