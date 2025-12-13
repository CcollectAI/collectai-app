from __future__ import annotations

import os

import redis

_pool = None


def r():
    global _pool
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    if _pool is None:
        _pool = redis.from_url(url, decode_responses=True)
    return _pool
