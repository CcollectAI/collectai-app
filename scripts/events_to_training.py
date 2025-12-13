#!/usr/bin/env python3
import json
import os
import sys

src = "data/training/events.jsonl"
dst = "data/training/training.jsonl"
if len(sys.argv) > 1:
    src = sys.argv[1]
if len(sys.argv) > 2:
    dst = sys.argv[2]

n_in = n_out = 0
os.makedirs(os.path.dirname(dst), exist_ok=True)
with open(dst, "w", encoding="utf-8") as fo:
    with open(src, encoding="utf-8") as fi:
        for line in fi:
            line = line.strip()
            if not line:
                continue
            n_in += 1
            try:
                e = json.loads(line)
                row = {
                    "category": e["category"],
                    "y": float(e["y"]) if e.get("y") is not None else None,
                    "features": e.get("features", {}),
                    "source": e.get("source", "ui"),
                }
                # only write rows that have a target y
                if row["y"] is not None:
                    fo.write(json.dumps(row) + "\n")
                    n_out += 1
            except Exception:
                pass
print(f"[ok] read={n_in} wrote={n_out} -> {dst}")
