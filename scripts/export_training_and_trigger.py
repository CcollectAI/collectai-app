#!/usr/bin/env python3
import csv
import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timedelta, timezone

import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
S3_BUCKET = os.environ["S3_DATA_BUCKET"]  # e.g., s3://collectai-datasets
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")
LAMBDA_TRAIN = os.environ.get("TRAIN_LAMBDA_URL")  # optional
MODEL_NAME = os.environ.get("MODEL_NAME", "price")
MODEL_VER = datetime.now(timezone.utc).strftime("%Y%m%d")


def supa_get(path, params=None, headers=None):

    import requests

    url = f"{SUPABASE_URL}{path}"
    h = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
    if headers:
        h.update(headers)
    last = None
    for attempt in range(6):
        try:
            r = requests.get(url, params=params, headers=h, timeout=60)
            if r.status_code in (429, 500, 502, 503, 504, 522):
                raise requests.HTTPError(f"{r.status_code}", response=r)
            r.raise_for_status()
            return r
        except Exception as e:
            last = e
            time.sleep(min(5 * (attempt + 1), 15))
    raise last
    url = f"{SUPABASE_URL}{path}"
    h = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
    if headers:
        h.update(headers)
    r = requests.get(url, params=params, headers=h, timeout=60)
    r.raise_for_status()
    return r


def supa_post(table, rows):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    h = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    r = requests.post(url, headers=h, data=json.dumps(rows), timeout=60)
    r.raise_for_status()
    return r.json()


def fetch_dataset(days=90, limit=20000):
    from datetime import datetime, timezone

    since = (
        (datetime.now(timezone.utc) - timedelta(days=days))
        .isoformat()
        .replace("+00:00", "Z")
    )
    base_params = {
        "select": "sample_id,title,category,condition,label_value_eur,image_url,source,version,created_at",
        "created_at": "gte." + since,
        "order": "created_at.desc",
    }
    rows = []
    page = 0
    page_size = 2000
    while True:
        rng_start = page * page_size
        rng_end = rng_start + page_size - 1
        r = supa_get(
            "/rest/v1/v_training_dataset_union",
            params=base_params,
            headers={
                "Accept": "application/json",
                "Range": f"{rng_start}-{rng_end}",
                "Prefer": "count=none",
            },
        )
        chunk = r.json()
        rows.extend(chunk)
        if len(chunk) < page_size or len(rows) >= limit:
            break
        page += 1
    return rows[:limit]

    params = {
        "select": "sample_id,title,category,condition,label_value_eur,image_url,source,version,created_at",
        "created_at": "gte."
        + (datetime.now(timezone.utc) - timedelta(days=days))
        .isoformat()
        .replace("+00:00", "Z"),
        "order": "created_at.desc",
        "limit": str(limit),
    }
    r = supa_get(
        "/rest/v1/v_training_dataset_union",
        params=params,
        headers={"Accept": "application/json"},
    )
    return r.json()


def write_csv(rows, path):
    fieldnames = [
        "sample_id",
        "title",
        "category",
        "condition",
        "label_value_eur",
        "image_url",
        "source",
        "version",
        "created_at",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(
                {k: (row.get(k) if row.get(k) is not None else "") for k in fieldnames}
            )


def s3_upload(local_path, s3_uri):
    # Prefer awscli if available, otherwise fallback to boto3
    if shutil.which("aws"):
        import subprocess

        subprocess.check_call(
            ["aws", "s3", "cp", local_path, s3_uri, "--region", AWS_REGION]
        )
        return
    # boto3 fallback

    import boto3

    assert s3_uri.startswith("s3://"), "S3_DATA_BUCKET must start with s3://"
    stripped = s3_uri[len("s3://") :]
    bucket, key = stripped.split("/", 1)
    s3 = boto3.client("s3", region_name=AWS_REGION)
    s3.upload_file(local_path, bucket, key)


def call_lambda_train(payload):
    import json
    import os

    arn = os.environ.get("TRAIN_LAMBDA_ARN")
    url = os.environ.get("TRAIN_LAMBDA_URL")
    if arn:
        import boto3

        lam = boto3.client(
            "lambda", region_name=os.environ.get("AWS_REGION", "eu-west-1")
        )
        resp = lam.invoke(FunctionName=arn, Payload=json.dumps(payload).encode("utf-8"))
        body = resp.get("Payload").read().decode("utf-8") if "Payload" in resp else "{}"
        try:
            return json.loads(body)
        except Exception:
            return {"status": resp.get("StatusCode"), "text": body}
    if url:
        import requests

        r = requests.post(url, json=payload, timeout=300)
        try:
            return r.json()
        except:
            return {"status": r.status_code, "text": r.text}
    return {"ok": True, "skipped": True}

    if not LAMBDA_TRAIN:
        return {"ok": True, "skipped": True}
    r = requests.post(LAMBDA_TRAIN, json=payload, timeout=300)
    try:
        return r.json()
    except:
        return {"status": r.status_code, "text": r.text}


def write_registry(uri):
    try:
        supa_post(
            "model_registry", [{"name": MODEL_NAME, "version": MODEL_VER, "uri": uri}]
        )
    except requests.HTTPError as e:
        if not (e.response is not None and e.response.status_code == 409):
            raise


def main():
    rows = fetch_dataset()
    if not rows:
        print("No dataset rows; exiting")
        return
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key_csv = f"datasets/{MODEL_NAME}/{MODEL_VER}/training_{ts}.csv"
    key_meta = f"datasets/{MODEL_NAME}/{MODEL_VER}/meta_{ts}.json"
    s3_csv = f"{S3_BUCKET.rstrip('/')}/{key_csv}"
    s3_meta = f"{S3_BUCKET.rstrip('/')}/{key_meta}"

    with tempfile.TemporaryDirectory() as d:
        csv_path = os.path.join(d, "dataset.csv")
        write_csv(rows, csv_path)
        meta = {
            "model": MODEL_NAME,
            "version": MODEL_VER,
            "rows": len(rows),
            "generated_at": ts,
        }
        meta_path = os.path.join(d, "meta.json")
        open(meta_path, "w").write(json.dumps(meta))

        s3_upload(csv_path, s3_csv)
        s3_upload(meta_path, s3_meta)
        print("Uploaded:", s3_csv, s3_meta)

    train_payload = {
        "model": MODEL_NAME,
        "version": MODEL_VER,
        "dataset_csv": s3_csv,
        "meta": meta,
    }
    train_resp = call_lambda_train(train_payload)
    print("Training trigger resp:", train_resp)

    artifact_uri = (
        train_resp.get("artifact_uri") if isinstance(train_resp, dict) else None
    ) or s3_csv
    write_registry(artifact_uri)
    print("Registry updated:", artifact_uri)


if __name__ == "__main__":
    main()
