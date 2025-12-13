import os, glob, pathlib, shutil, boto3, botocore

SPOOL_DIR = os.environ.get("INGEST_SPOOL_DIR", "ops/spool")
DLQ_DIR   = os.environ.get("S3_DLQ_DIR", "ops/s3_failed")
BUCKET    = os.environ["SPOOL_S3_BUCKET"]
PREFIX    = os.environ.get("SPOOL_S3_PREFIX", "spool/")
REGION    = os.environ.get("AWS_DEFAULT_REGION", "eu-north-1")
ACL       = os.environ.get("SPOOL_S3_ACL", "")
SSE       = os.environ.get("S3_SSE", "")
KMS       = os.environ.get("S3_SSE_KMS_KEY_ID", "")

def extra_args():
    args = {}
    if ACL: args["ACL"] = ACL
    if SSE: args["ServerSideEncryption"] = SSE
    if KMS: args["SSEKMSKeyId"] = KMS
    return args

def main():
    os.makedirs(DLQ_DIR, exist_ok=True)
    paths = sorted(glob.glob(os.path.join(SPOOL_DIR, "agent_ingest_*.jsonl")))
    if not paths:
        print("No spool files to upload."); return
    s3 = boto3.client("s3", region_name=REGION)
    X = extra_args() or None
    for p in paths:
        key = PREFIX + pathlib.Path(p).name
        print(f"Uploading {p} -> s3://{BUCKET}/{key}")
        try:
            s3.upload_file(p, BUCKET, key, ExtraArgs=X)
        except botocore.exceptions.ClientError as e:
            print("ERROR:", e)
            shutil.move(p, os.path.join(DLQ_DIR, pathlib.Path(p).name))
            print(f"Moved to DLQ: {DLQ_DIR}")
        else:
            os.remove(p)
            print("Uploaded and removed local file.")
    print("Done.")
if __name__ == "__main__":
    main()
