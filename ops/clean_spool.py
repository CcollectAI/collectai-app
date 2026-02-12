import glob
import logging
import os
import time

logger = logging.getLogger(__name__)

SPOOL = os.getenv("INGEST_SPOOL_DIR", "ops/spool")
KEEP_DAYS = int(os.getenv("SPOOL_KEEP_DAYS", "2"))
cutoff = time.time() - KEEP_DAYS * 86400
deleted = 0
for p in glob.glob(f"{SPOOL}/agent_ingest_*.jsonl"):
    try:
        if os.path.getmtime(p) < cutoff:
            os.remove(p)
            deleted += 1
    except FileNotFoundError:
        pass
logger.info("Deleted %d old files from %s", deleted, SPOOL)
