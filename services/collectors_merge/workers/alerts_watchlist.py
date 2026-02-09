from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from services.collectors_merge.core.currency.fx import to_eur
from services.collectors_merge.core.fees.fees import effective_price
from services.collectors_merge.core.notify.queue import enqueue

logger = logging.getLogger(__name__)


def db():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def recent_price_for(nk: str, days: int = 7):
    conn = db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            select provider, price, currency, shipping, ended_at
            from public.market_hits
            where normalized_key=%s and ended_at >= now() - (%s || ' days')::interval
            order by ended_at desc limit 20
        """,
            (nk, days),
        )
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()
    eff = []
    for r in rows:
        eur = (
            to_eur(float(r["price"]), r["currency"]) if r["price"] is not None else None
        )
        ep = (
            effective_price(r["provider"], eur, r.get("shipping"))
            if eur is not None
            else None
        )
        if ep is not None:
            eff.append(ep)
    if not eff:
        return None
    eff.sort()
    mid = len(eff) // 2
    med = eff[mid] if len(eff) % 2 == 1 else (eff[mid - 1] + eff[mid]) / 2
    return med


def last_month_price(nk: str):
    return recent_price_for(nk, days=30)


def main():
    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""select user_id, normalized_key from public.watchlist""")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    for r in rows:
        nk = r["normalized_key"]
        p7 = recent_price_for(nk, 7)
        p30 = recent_price_for(nk, 30)
        if p7 is None or p30 is None:
            continue
        # triggers
        spike = p7 >= 1.15 * p30
        drop = p7 <= 0.85 * p30
        if spike or drop:
            enqueue(
                {
                    "type": "watchlist.alert",
                    "user_id": r["user_id"],
                    "normalized_key": nk,
                    "trend": "spike" if spike else "drop",
                    "p7": round(p7, 2),
                    "p30": round(p30, 2),
                    "at": datetime.now(timezone.utc).isoformat() + "Z",
                }
            )
    logger.info("watchlist alerts queued")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [alerts_watchlist] %(levelname)s: %(message)s")
    main()
