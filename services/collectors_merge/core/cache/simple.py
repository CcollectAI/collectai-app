from __future__ import annotations

import time
from functools import wraps


def ttl_cache(ttl_sec: int = 30):
    store = {}

    def deco(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            k = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            if k in store:
                v, exp = store[k]
                if now < exp:
                    return v
            v = fn(*args, **kwargs)
            store[k] = (v, now + ttl_sec)
            return v

        return wrapped

    return deco
