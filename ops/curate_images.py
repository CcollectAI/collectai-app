#!/usr/bin/env python3
import argparse, json, io, os, hashlib
from datetime import datetime, timezone
import boto3, botocore

s3 = boto3.client("s3")

def list_objs(bucket, prefix):
    p = s3.get_paginator("list_objects_v2")
    for page in p.paginate(Bucket=bucket, Prefix=prefix):
        for o in page.get("Contents", []):
            if not o["Key"].endswith("/"):
                yield o

def head_ok(bucket, key, min_bytes):
    h = s3.head_object(Bucket=bucket, Key=key)
    ct = h.get("ContentType","")
    sz = h["ContentLength"]
    if sz < min_bytes: return False, f"too_small({sz})"
    if not ct.startswith("image/"): return False, f"not_image({ct})"
    return True, {"ct":ct, "size":sz}

def sha256_s3(bucket, key):
    bio = io.BytesIO(); s3.download_fileobj(bucket, key, bio); bio.seek(0)
    return hashlib.sha256(bio.read()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--min-bytes", type=int, default=4096)
    ap.add_argument("--categories", nargs="+", required=True)
    args = ap.parse_args()

    kept=skipped=0
    for cat in args.categories:
        raw = f"raw/{cat}/"
        dstp = f"curated/{cat}/"
        print(f"== {cat} ==")
        for obj in list_objs(args.bucket, raw):
            key = obj["Key"]
            ok, meta = head_ok(args.bucket, key, args.min_bytes)
            if not ok:
                print("skip", key, "->", meta); skipped+=1; continue
            checksum = sha256_s3(args.bucket, key)
            filename = os.path.basename(key)
            dst = dstp + filename
            # write sidecar, then copy image
            side = {
                "source_key": key, "curated_key": dst, "checksum": checksum,
                "content_type": meta["ct"], "size": meta["size"],
                "curated_at": datetime.now(timezone.utc).isoformat()
            }
            s3.copy_object(Bucket=args.bucket, CopySource={"Bucket":args.bucket,"Key":key}, Key=dst)
            s3.put_object(Bucket=args.bucket, Key=dst+".json", Body=json.dumps(side).encode("utf-8"), ContentType="application/json")
            kept+=1
            print("curated", key, "->", dst)
    print(json.dumps({"kept":kept,"skipped":skipped}, indent=2))

if __name__=="__main__":
    main()
