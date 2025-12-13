from __future__ import annotations

import statistics as stats
from datetime import datetime, timezone
from typing import Any


def iqr_filter(prices: list[float], k: float = 1.5) -> list[bool]:
    if not prices or len(prices) < 5:
        return [True] * len(prices)
    q1 = stats.quantiles(prices, n=4)[0]
    q3 = stats.quantiles(prices, n=4)[2]
    iqr = max(1e-9, q3 - q1)
    lo, hi = q1 - k * iqr, q3 + k * iqr
    return [(lo <= p <= hi) for p in prices]


def depth_and_recency(rows: list[dict[str, Any]]):
    """Return (# rows, days since latest sale)"""
    if not rows:
        return 0, None
    dates = []
    for r in rows:
        t = r.get("ended_at")
        if not t:
            continue
        try:
            dates.append(datetime.fromisoformat(t.replace("Z", "+00:00")))
        except Exception:
            continue
    if not dates:
        return len(rows), None
    last = max(dates)
    delta = (datetime.now(timezone.utc) - last).days
    return len(rows), delta
