from __future__ import annotations

import datetime as dt
import json
import logging
import sys

logger = logging.getLogger(__name__)


# Append a row every time we have a prediction and later see an "actual"
# payload example:
# {"item_id":"...","actual":123.45,"q10":90,"q50":120,"q90":150,"category":"tcg","asof":"2025-10-01T10:20:00Z"}
def append_row(row: dict, path="calibration.jsonl"):
    with open(path, "a") as f:
        f.write(json.dumps(row) + "\n")


if __name__ == "__main__":
    row = (
        json.loads(sys.argv[1])
        if len(sys.argv) > 1
        else {
            "item_id": "TEST",
            "actual": 100,
            "q10": 80,
            "q50": 100,
            "q90": 120,
            "category": "test",
            "asof": dt.datetime.now(dt.timezone.utc).isoformat() + "Z",
        }
    )
    logging.basicConfig(level=logging.INFO)
    append_row(row)
    logger.info("ok")
