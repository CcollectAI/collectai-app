import io
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import boto3
from PIL import Image

logger = logging.getLogger(__name__)
import numpy as np
from app.vision_embed import get_image_embed, get_text_matrix, topk_cosine

BUCKET = os.environ.get("SPOOL_S3_BUCKET","collectai-datasets")
REGION = os.environ.get("AWS_DEFAULT_REGION","eu-north-1")
PREFIX = os.environ.get("VISION_PREFIX","spool/vision/")
OUT = "ops/spool/vision_predictions.jsonl"

s3 = boto3.client("s3", region_name=REGION)

def zs_predict(img, k=5):
    q = get_image_embed(img)
    T, labels = get_text_matrix()
    sims = (T @ q) / (np.linalg.norm(T,axis=1)*np.linalg.norm(q)+1e-9)
    idxs = np.argsort(-sims)[:k]
    cats = [{"id":labels[i]["id"], "name":labels[i]["name"], "score":float(sims[i])} for i in idxs]
    nns = topk_cosine(q, topk=k)
    return cats, nns, int(q.shape[0])

def main():
    reg_path = "ops/spool/vision_registry.jsonl"
    if not os.path.exists(reg_path):
        logger.warning("no registry"); return
    seen=set()
    with open(OUT,"a") as out, open(reg_path) as f:
        for line in f:
            o = json.loads(line)
            key=o["key"]; sha=o["sha256"]
            if sha in seen: continue
            seen.add(sha)
            try:
                obj = s3.get_object(Bucket=BUCKET, Key=key)
                data = obj["Body"].read()
                img = Image.open(io.BytesIO(data)).convert("RGB")
                cats, nns, d = zs_predict(img)
                out.write(json.dumps({"ts":int(time.time()),
                                      "sha256":sha,"key":key,
                                      "categories":cats,"neighbors":nns,"dim":d})+"\n")
            except Exception as e:
                logger.warning("skip %s %s", key, e)
    logger.info("done -> %s", OUT)

if __name__ == "__main__":
    main()
