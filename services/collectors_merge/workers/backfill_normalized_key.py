from __future__ import annotations

import os

import psycopg2
import psycopg2.extras

from services.collectors_merge.core.normalize.normalizer import normalized_key


def db():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def main(limit=10000):
    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """select id, category, attributes_json from public.items where (normalized_key is null or normalized_key='') limit %s""",
        (limit,),
    )
    rows = cur.fetchall()
    upd = conn.cursor()
    n = 0
    for r in rows:
        attrs = r.get("attributes_json") or {}
        nk = normalized_key(r["category"], attrs)
        upd.execute(
            "update public.items set normalized_key=%s where id=%s", (nk, r["id"])
        )
        n += 1
    conn.commit()
    upd.close()
    cur.close()
    conn.close()
    print(f"updated {n} items")


if __name__ == "__main__":
    main()
