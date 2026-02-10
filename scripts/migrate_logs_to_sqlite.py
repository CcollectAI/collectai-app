#!/usr/bin/env python3
import json
import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

DB = "data/training/logs.db"
os.makedirs("data/training", exist_ok=True)
con = sqlite3.connect(DB)
cur = con.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS preds(ts INT, category TEXT, payload TEXT)")
cur.execute(
    "CREATE TABLE IF NOT EXISTS events(ts INT, category TEXT, y REAL, features TEXT)"
)
# migrate preds.jsonl
for path, tbl, cols in [
    ("data/training/preds.jsonl", "preds", ("ts", "category", "payload")),
    ("data/training/events.jsonl", "events", ("ts", "category", "y", "features")),
]:
    if not os.path.exists(path):
        continue
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if tbl == "preds":
                cur.execute(
                    "INSERT INTO preds VALUES (?,?,?)",
                    (int(j.get("ts", 0)), j.get("category", "?"), json.dumps(j)),
                )
            else:
                cur.execute(
                    "INSERT INTO events VALUES (?,?,?,?)",
                    (
                        int(j.get("ts", 0)),
                        j.get("category", "?"),
                        float(j.get("y", 0)),
                        json.dumps(j),
                    ),
                )
con.commit()
con.close()
logger.info("migrated to %s", DB)
