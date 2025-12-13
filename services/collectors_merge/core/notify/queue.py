from __future__ import annotations

import json
import pathlib
from typing import Any

QPATH = pathlib.Path("notify_queue.jsonl")


def enqueue(msg: dict[str, Any]):
    QPATH.parent.mkdir(exist_ok=True, parents=True)
    with QPATH.open("a") as f:
        f.write(json.dumps(msg) + "\n")


def drain():
    if not QPATH.exists():
        return []
    lines = QPATH.read_text().splitlines()
    QPATH.unlink(missing_ok=True)
    return [json.loads(x) for x in lines]
