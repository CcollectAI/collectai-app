from __future__ import annotations

import json
from collections.abc import Callable

from .client import r


def redis_cache(key: str, ttl: int, fn: Callable[[], dict]) -> dict:
    rv = r().get(key)
    if rv:
        return json.loads(rv)
    data = fn()
    r().setex(key, ttl, json.dumps(data))
    return data
