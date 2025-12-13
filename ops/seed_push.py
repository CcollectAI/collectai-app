import os, sys, json, hashlib, time, subprocess, glob, pathlib

BUCKET = os.getenv("SPOOL_S3_BUCKET","collectai-datasets")
PREFIX = os.getenv("VISION_PREFIX","spool/vision/raw/")  # keep trailing slash
REG    = "ops/spool/vision_registry.jsonl"

def sha256_path(b: bytes):
    h = hashlib.sha256(b).hexdigest()
    return f"{h[:2]}/{h}.jpg", h

def put_s3(local_path, key):
    cmd = ["aws","s3","cp", local_path, f"s3://{BUCKET}/{key}","--only-show-errors"]
    subprocess.check_call(cmd)

def main():
    os.makedirs(os.path.dirname(REG), exist_ok=True)
    cnt=0
    for label_dir in sorted(glob.glob("seed/*")):
        label = pathlib.Path(label_dir).name
        for jpg in sorted(glob.glob(f"{label_dir}/*.jpg")):
            with open(jpg,"rb") as f: b=f.read()
            rel, sha = sha256_path(b)
            key = f"{PREFIX}{rel}"
            put_s3(jpg, key)
            line = {"ts": int(time.time()), "sha256": sha, "key": key, "size": len(b), "label_hint": label}
            with open(REG,"a") as out: out.write(json.dumps(line)+"\n")
            cnt+=1
    print({"ok":True, "uploaded": cnt, "registry": REG})

if __name__ == "__main__":
    main()
