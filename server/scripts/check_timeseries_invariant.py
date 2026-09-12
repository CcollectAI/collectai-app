#!/usr/bin/env python3
"""The last point of /portfolio/timeseries must equal /portfolio/overview.

Home derives its headline "COLLECTION VALUE", the chart and the change % from
the timeseries, while the stats strip directly below it and the Items tab sum
the collection. If the two disagree, one screen contradicts the other in the
same viewport — which is exactly what a collector reads as "the app is wrong".

WHY THIS SCRIPT EXISTS (2026-09-12): it regressed, and only for SOME ranges, so
every check anyone had been doing missed it. Measured on prod, one account, one
moment:

    range=30d  last=1347.68  overview=1347.68   agree
    range=7d   last=1288.00  overview=1347.68   off by 59.68
    range=1d   last=1323.29  overview=1347.68   off by 24.39

**7D is the default range**, so Home opened on the wrong number. The cause was
the `per_day` CTE holding only predictions generated INSIDE the window: an item
last priced before the window start fell through to its stored value on every
day drawn, including the last one. The arithmetic was exact — two items priced
8 days ago account for precisely 59.68.

The lesson worth keeping: the invariant was DOCUMENTED in the query's own
comment and still broke, because nothing executed it. A promise in a comment is
not a test.

    python3 server/scripts/check_timeseries_invariant.py     # 0 ok, 1 drift, 2 could not run

Exit 2 (could not run) is distinct from exit 0 on purpose — a check that cannot
reach the database must never look like a passing one.
"""
from __future__ import annotations

import asyncio
import datetime
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # server/
RANGES = {"1d": 1, "7d": 7, "30d": 30, "90d": 90, "1y": 365}
TOLERANCE = 0.01


def timeseries_sql() -> str:
    """The route's OWN query text, read from source.

    Retyping it here would let the check drift from the thing it checks — the
    failure mode `docs/WATCHDOG.md` records for the coverage canary.
    """
    import ast

    src = (ROOT / "app/routes/portfolio_router.py").read_text()
    found = [
        node.value
        for node in ast.walk(ast.parse(src))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and "per_day AS" in node.value
    ]
    if not found:
        raise RuntimeError("timeseries query not found in portfolio_router.py")
    return found[-1]


# THE canonical valuation, not a retyped copy of it. `public.item_value_v1(i)`
# is the one definition (docs/ARCHITECTURE.md, "One valuation expression, or the
# screen contradicts itself"); /portfolio/overview and the Items tab both resolve
# through it. The first draft of this script retyped a COALESCE chain instead and
# promptly reported a 5.76 "drift" that was its own reference being wrong — the
# exact mistake its docstring warns about, made in the same file.
OVERVIEW_SQL = """
    SELECT COALESCE(SUM(iv.value_eur), 0)
    FROM items i
    LEFT JOIN LATERAL public.item_value_v1(i) iv ON TRUE
    WHERE i.user_id = $1 AND NOT i.archived
"""


async def main() -> int:
    dsn = os.getenv("DB_DSN_DIRECT") or os.getenv("DB_DSN")
    if not dsn:
        print("COULD NOT RUN — DB_DSN_DIRECT/DB_DSN not set")
        return 2
    try:
        import asyncpg
    except ImportError:
        print("COULD NOT RUN — asyncpg not installed")
        return 2

    try:
        sql = timeseries_sql()
    except Exception as exc:
        print(f"COULD NOT RUN — {exc}")
        return 2

    conn = await asyncpg.connect(dsn)
    drift = []
    try:
        users = await conn.fetch(
            """
            SELECT user_id, count(*) AS n FROM items
             WHERE NOT archived AND user_id IS NOT NULL
             GROUP BY user_id ORDER BY n DESC LIMIT 20
            """
        )
        if not users:
            print("COULD NOT RUN — no accounts with items to check")
            return 2

        for row in users:
            uid = row["user_id"]
            expected = float(await conn.fetchval(OVERVIEW_SQL, uid) or 0)
            if expected <= 0:
                continue  # nothing priced; the curve is legitimately empty
            for label, days in RANGES.items():
                since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
                points = await conn.fetch(sql, uid, since)
                if not points:
                    continue
                last = float(points[-1]["total_value"])
                if abs(last - expected) > TOLERANCE:
                    drift.append((str(uid)[:8], label, last, expected))
    finally:
        await conn.close()

    if not drift:
        print(f"[timeseries-invariant] PASS — last point equals the collection "
              f"total for every range, {len(users)} account(s) checked.")
        return 0

    print(f"[timeseries-invariant] FAIL — {len(drift)} range(s) whose last point "
          "disagrees with the collection total.")
    print("Home's headline and the stats strip below it would show different "
          "numbers on the same screen.\n")
    for uid, label, last, expected in drift:
        print(f"  user {uid}  range={label:4s} last={last:10.2f}  total={expected:10.2f}"
              f"  off by {expected - last:+.2f}")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
