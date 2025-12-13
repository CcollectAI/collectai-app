from __future__ import annotations

import json
import os

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ["DATABASE_URL"]


def db():
    return psycopg2.connect(DATABASE_URL)


def med(conn, nk: str, days: int):
    cur = conn.cursor()
    cur.execute(
        """
        with vals as (
          select (mh.price + coalesce(mh.shipping,0))::numeric as v
          from public.market_hits mh
          where mh.normalized_key=%s and mh.ended_at >= now() - (%s || ' days')::interval
        )
        select percentile_disc(0.5) within group (order by v) from vals
    """,
        (nk, days),
    )
    r = cur.fetchone()
    cur.close()
    return float(r[0]) if r and r[0] is not None else None


def run():
    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # evaluate for all watchlist NKs (user_id ignored for events)
    cur.execute(
        """
      select distinct normalized_key
      from public.watchlist
    """
    )
    wrows = cur.fetchall()
    created = 0
    for r in wrows:
        nk = r["normalized_key"]
        p30 = med(conn, nk, 30)
        p7 = med(conn, nk, 7)
        if not p30 or not p7:
            continue
        up = p7 >= p30 * 1.15
        dn = p7 <= p30 * 0.85
        if up or dn:
            kind = "alert:spike" if up else "alert:drop"
            payload = {"p7": p7, "p30": p30, "nk": nk, "rule": "p7_vs_p30@±15%"}
            cur2 = conn.cursor()
            cur2.execute(
                """insert into public.events (kind, payload) values (%s,%s::jsonb)""",
                (kind, json.dumps(payload)),
            )
            cur2.close()
            created += 1
    conn.commit()
    cur.close()
    conn.close()
    print(f"alerts created: {created}")


if __name__ == "__main__":
    run()
