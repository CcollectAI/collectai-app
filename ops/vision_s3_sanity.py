import io
import json
import logging
import os
import sys

import boto3
from botocore.exceptions import ClientError
from PIL import Image, UnidentifiedImageError, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True
logger = logging.getLogger(__name__)

BUCKET=os.getenv("SPOOL_S3_BUCKET","collectai-datasets")
REG=os.getenv("AWS_DEFAULT_REGION","eu-north-1")
REGFILE=os.getenv("VISION_REGISTRY_FILE","ops/spool/vision_registry.jsonl")

s3=boto3.client("s3", region_name=REG)
bad=[]; good=[]; scanned=0
with open(REGFILE) as f:
    for line in f:
        line=line.strip()
        if not line: continue
        try: j=json.loads(line)
        except (json.JSONDecodeError, ValueError): bad.append({"type":"json-parse","line":line[:120]}); continue
        key=j.get("key"); sha=j.get("sha256")
        if not key: bad.append({"type":"no-key","raw":line[:120]}); continue
        scanned+=1
        try:
            h=s3.head_object(Bucket=BUCKET, Key=key)
        except ClientError as e:
            bad.append({"type":"head-fail","key":key,"err":str(e)[:160]}); continue
        ct=h.get("ContentType",""); sz=h.get("ContentLength",0)
        if not ct.startswith("image/") or sz < 1024:
            bad.append({"type":"not-image-or-tiny","key":key,"ct":ct,"size":sz}); continue
        try:
            r=s3.get_object(Bucket=BUCKET, Key=key, Range="bytes=0-65535")
            Image.open(io.BytesIO(r["Body"].read())).verify()
            good.append({"key":key,"sha256":sha})
        except UnidentifiedImageError:
            bad.append({"type":"PIL-sniff-fail","key":key,"ct":ct,"size":sz})
        except (ClientError, OSError, IOError) as e:
            logger.warning("get/open-fail for key=%s: %s", key, e)
            bad.append({"type":"get/open-fail","key":key,"err":str(e)[:160]})
logger.info(json.dumps({"scanned":scanned,"good":len(good),"bad":len(bad),"bad_items":bad}, indent=2))
