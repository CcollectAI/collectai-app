#!/usr/bin/env python3
import os, glob, time, threading, boto3
from prometheus_client import start_http_server, Gauge

BUCKET = os.environ.get("BUCKET", "collectai-datasets")
CATEGORIES = os.environ.get("CATEGORIES","pokemon_cards,funko_pops,diecast_cars").split(",")

g_curated = Gauge("collectors_curated_images_total", "Curated image count per category", ["category"])
g_preds   = Gauge("collectors_prediction_files_total", "Local predictions-*.jsonl files")

s3 = boto3.client("s3")

def count_curated():
    for cat in CATEGORIES:
        prefix = f"curated/{cat.strip()}/"
        n=0
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                if not obj["Key"].endswith("/") and obj["Size"]>0:
                    n+=1
        g_curated.labels(category=cat.strip()).set(n)

def count_preds_local():
    n = len(glob.glob("ops/vision/predictions-*.jsonl*"))
    g_preds.set(n)

def loop(interval=60):
    while True:
        try:
            count_curated()
            count_preds_local()
        except Exception as e:
            # Keep the exporter alive even if S3 hiccups
            pass
        time.sleep(interval)

if __name__ == "__main__":
    start_http_server(9001)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    t.join()
