import csv
import json
import logging
import sys

logger = logging.getLogger(__name__)

GOLD = {}
with open("ops/eval/gold_labels.csv", newline="") as f:
    for row in csv.DictReader(f):
        GOLD[row["sha256"]] = row["label_id"]

K = int(sys.argv[1]) if len(sys.argv) > 1 else 3
hits = total = 0

try:
    f = open("ops/spool/vision_predictions.jsonl", "r", encoding="utf-8")
except FileNotFoundError:
    logger.warning("predictions file missing: ops/spool/vision_predictions.jsonl")
    raise SystemExit(2)

with f:
    for line in f:
        j = json.loads(line)
        sha = j.get("sha256")
        cats = j.get("categories") or []
        if sha in GOLD:
            total += 1
            topk = [c["id"] for c in cats[:K]]
            if GOLD[sha] in topk:
                hits += 1

logger.info("k=%d total=%d hits=%d precision_at_k=%.4f", K, total, hits, (hits/total if total else 0.0))
