import csv
import datetime as dt
import hashlib
import json
import math
import os
import statistics
import tempfile

import boto3
import requests

S3 = boto3.client("s3")
REGION = os.environ.get("AWS_REGION", "eu-north-1")
ARTIFACT_BUCKET = os.environ.get("ARTIFACT_BUCKET")


def s3_get(s3_uri: str) -> str:
    assert s3_uri.startswith("s3://")
    bucket, key = s3_uri[5:].split("/", 1)
    with tempfile.TemporaryFile() as f:
        S3.download_fileobj(bucket, key, f)
        f.seek(0)
        return f.read().decode()


def s3_put_text(bucket: str, key: str, text: str) -> None:
    S3.put_object(
        Bucket=bucket, Key=key, Body=text.encode(), ContentType="application/json"
    )


def _pct(vals: list[float], p: float) -> float | None:
    if not vals:
        return None
    vals = sorted(vals)
    if len(vals) == 1:
        return float(vals[0])
    k = (len(vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(vals[int(k)])
    d0 = vals[int(f)] * (c - k)
    d1 = vals[int(c)] * (k - f)
    return float(d0 + d1)


def file_hash_s3(s3_uri: str) -> str:
    assert s3_uri.startswith("s3://")
    b, k = s3_uri[5:].split("/", 1)
    obj = S3.get_object(Bucket=b, Key=k)
    h = hashlib.sha256()
    body = obj["Body"]
    while True:
        chunk = body.read(8192)
        if not chunk:
            break
        h.update(chunk)
    return h.hexdigest()


def upsert_eval_to_supabase(
    category: str,
    version: str,
    metrics: dict,
    sample_size: int,
    model_name: str = "price",
) -> bool:
    SB = os.environ.get("SUPABASE_URL")
    KEY = os.environ.get("SUPABASE_SERVICE_KEY")
    if not (SB and KEY):
        print('{"lvl":"warn","at":"eval→supabase","msg":"missing envs"}')
        return False
    payload = {
        "model": model_name,
        "category": category,
        "version": version,
        "mae": metrics.get("mae"),
        "mape": metrics.get("mape"),
        "rmse": metrics.get("rmse"),
        "r2": metrics.get("r2"),
        "p50": metrics.get("p50"),
        "p90": metrics.get("p90"),
        "sample_size": int(sample_size),
        "evaluated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    try:
        r = requests.post(
            f"{SB}/rest/v1/model_evals",
            headers={
                "apikey": KEY,
                "Authorization": f"Bearer {KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        if r.status_code not in (200, 201, 204):
            print(
                f'{{"lvl":"error","at":"eval→supabase","status":{r.status_code},"body":{json.dumps(r.text)}}}'
            )
            return False
        print(
            f'{{"lvl":"info","at":"eval→supabase","status":{r.status_code},"cat":"{category}","ver":"{version}"}}'
        )
        return True
    except Exception as e:
        print(f'{{"lvl":"warn","at":"eval→supabase","err":"{e}"}}')
        return False


def log_training_run(
    category: str,
    version: str,
    dataset_uri: str,
    artifact_uri: str,
    params: dict,
    started_at: str | None,
    status: str = "succeeded",
    dataset_sha256: str | None = None,
    artifact_etag: str | None = None,
) -> None:
    SB = os.environ.get("SUPABASE_URL")
    KEY = os.environ.get("SUPABASE_SERVICE_KEY")
    if not (SB and KEY):
        print('{"lvl":"warn","at":"runlog→supabase","msg":"missing envs"}')
        return
    payload = {
        "category": category,
        "version": version,
        "dataset_uri": dataset_uri,
        "dataset_sha256": dataset_sha256,
        "params_json": params,
        "artifact_uri": artifact_uri,
        "artifact_etag": artifact_etag,
        "status": status,
        "started_at": started_at,
        "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    try:
        r = requests.post(
            f"{SB}/rest/v1/model_training_runs",
            headers={
                "apikey": KEY,
                "Authorization": f"Bearer {KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        if r.status_code not in (200, 201, 204):
            print("RUN_LOG_ERR", r.status_code, r.text)
    except Exception as e:
        print("RUN_LOG_ERR", e)


def handler(event, _):
    model = event.get("model", "price")
    version = event.get("version")
    csv_uri = event.get("dataset_csv")
    category = event.get("category") or "pokemon"
    params = event.get("params") or {}
    started_at = (event.get("meta") or {}).get("generated_at")

    if not (version and csv_uri and ARTIFACT_BUCKET):
        return {"ok": False, "error": "missing params or ARTIFACT_BUCKET"}

    # load dataset
    txt = s3_get(csv_uri)
    prices: list[float] = []
    for r in csv.DictReader(txt.splitlines()):
        try:
            v = float(r.get("label_value_eur") or 0)
            if v > 0:
                prices.append(v)
        except Exception:
            pass

    baseline = statistics.median(prices) if prices else 25.0

    # metrics vs baseline
    abs_err = [abs(v - baseline) for v in prices]
    mae = (sum(abs_err) / len(abs_err)) if abs_err else None
    mape = (
        (
            sum(abs(v - baseline) / v for v in prices if v > 0)
            / len([v for v in prices if v > 0])
        )
        if prices
        else None
    )
    rmse = (
        (math.sqrt(sum((v - baseline) ** 2 for v in prices) / len(prices)))
        if prices
        else None
    )
    if prices:
        mean_y = sum(prices) / len(prices)
        sse = sum((v - baseline) ** 2 for v in prices)
        sst = sum((v - mean_y) ** 2 for v in prices) or None
        r2 = (1 - sse / sst) if sst else None
    else:
        r2 = None

    metrics = {
        "mae": mae,
        "mape": mape,
        "rmse": rmse,
        "r2": r2,
        "p50": statistics.median(abs_err) if abs_err else None,
        "p90": _pct(abs_err, 90),
    }
    sample_size = len(prices)

    # write artifact
    artifact = {
        "model": model,
        "version": version,
        "region": REGION,
        "model_type": "baseline_only",
        "baseline_price_eur": round(float(baseline), 2),
        "created_at": started_at or dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    key = f"artifacts/{model}/{version}/model.json"
    s3_put_text(ARTIFACT_BUCKET, key, json.dumps(artifact))
    artifact_uri = f"s3://{ARTIFACT_BUCKET}/{key}"

    # HEAD to get ETag
    try:
        head = S3.head_object(Bucket=ARTIFACT_BUCKET, Key=key)
        artifact_etag = head.get("ETag")
    except Exception as e:
        print('{"lvl":"warn","at":"etag","err":"%s"}' % e)
        artifact_etag = None

    # log eval and training run
    ok_eval = upsert_eval_to_supabase(
        category=category,
        version=version,
        metrics=metrics,
        sample_size=sample_size,
        model_name=model,
    )
    try:
        dataset_sha256 = file_hash_s3(csv_uri)
    except Exception as e:
        print('{"lvl":"warn","at":"hash","err":"%s"}' % e)
        dataset_sha256 = None
    log_training_run(
        category,
        version,
        csv_uri,
        artifact_uri,
        params,
        started_at,
        status="succeeded",
        dataset_sha256=dataset_sha256,
        artifact_etag=artifact_etag,
    )

    resp = {
        "ok": True,
        "artifact_uri": artifact_uri,
        "metrics": metrics,
        "artifact_etag": artifact_etag,
    }
    if not ok_eval:
        resp["warn"] = "eval_not_logged"
    return resp
