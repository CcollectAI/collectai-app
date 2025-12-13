from __future__ import annotations

import time

from .client import r


def allow(key: str, rps: float = 1.0, burst: int = 30) -> bool:
    now = time.time()
    k = f"rl:{key}"
    pipe = r().pipeline()
    pipe.hgetall(k)
    data = pipe.execute()[0] or {}
    tokens = float(data.get("tokens", burst))
    ts = float(data.get("ts", now))
    tokens = min(burst, tokens + (now - ts) * rps)
    if tokens >= 1.0:
        tokens -= 1.0
        r().hset(k, mapping={"tokens": tokens, "ts": now})
        r().expire(k, 3600)
        return True
    r().hset(k, mapping={"tokens": tokens, "ts": now})
    r().expire(k, 3600)
    return False
