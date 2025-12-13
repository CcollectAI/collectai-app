import os, time, glob
from datetime import datetime, timedelta
SPOOL = os.getenv("INGEST_SPOOL_DIR", "ops/spool")
KEEP_DAYS = int(os.getenv("SPOOL_KEEP_DAYS", "2"))
cutoff = time.time() - KEEP_DAYS*86400
deleted = 0
for p in glob.glob(f"{SPOOL}/agent_ingest_*.jsonl"):
    try:
        if os.path.getmtime(p) < cutoff:
            os.remove(p)
            deleted += 1
    except FileNotFoundError:
        pass
print(f"Deleted {deleted} old files from {SPOOL}")
