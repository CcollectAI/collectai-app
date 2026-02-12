#!/usr/bin/env python3
import json
import logging
import os
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

PREDS = "data/training/preds.jsonl"
OUT = "data/training/events.jsonl"
PER_CAT = int(os.environ.get("SEED_PER_CAT", "20"))
FACTOR = float(os.environ.get("SEED_Y_FACTOR", "1.0"))


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    preds = read_jsonl(PREDS)
    by_cat = defaultdict(list)
    for p in preds[::-1]:  # newest first
        cat = p.get("category") or p.get("cat") or "unknown"
        by_cat[cat].append(p)

    now = int(time.time())
    count = 0
    with open(OUT, "a", encoding="utf-8") as fout:
        for cat, lst in by_cat.items():
            take = lst[:PER_CAT]
            for p in take:
                feats = p.get("features_used") or p.get("features") or {}
                y = p.get("suggested_price")
                if y is None:
                    continue
                evt = {
                    "category": cat,
                    "features": feats,
                    "y": float(y) * FACTOR,
                    "source": "seed_from_preds",
                    "ts": now,
                }
                fout.write(json.dumps(evt) + "\n")
                count += 1

    logger.info("[ok] seeded %d events into %s", count, OUT)
