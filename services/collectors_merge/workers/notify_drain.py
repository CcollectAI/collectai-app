from __future__ import annotations

import os

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

load_dotenv(".env")
DATABASE_URL = os.environ["DATABASE_URL"]


def db():
    return psycopg2.connect(DATABASE_URL)


def has_column(conn, table: str, col: str) -> bool:
    with conn.cursor() as c:
        c.execute(
            """
          select count(*)>0 from information_schema.columns
          where table_schema='public' and table_name=%s and column_name=%s
        """,
            (table, col),
        )
        return bool(c.fetchone()[0])


def drain():
    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # detect schema
    has_user = has_column(conn, "events", "user_id")
    has_item = has_column(conn, "events", "item_id")
    has_processed = has_column(conn, "events", "processed")

    # base filter
    where_processed = " and coalesce(processed,false)=false" if has_processed else ""

    if has_user:
        cur.execute(
            f"""
          select id, user_id, kind, payload, created_at
          from public.events
          where kind like 'alert:%%'{where_processed}
          order by created_at asc limit 50
        """
        )
    elif has_item and has_column(conn, "items", "user_id"):
        cur.execute(
            f"""
          select e.id, i.user_id, e.kind, e.payload, e.created_at
          from public.events e
          left join public.items i on i.id = e.item_id
          where e.kind like 'alert:%%'{where_processed}
          order by e.created_at asc limit 50
        """
        )
    else:
        cur.execute(
            f"""
          select id, null::text as user_id, kind, payload, created_at
          from public.events
          where kind like 'alert:%%'{where_processed}
          order by created_at asc limit 50
        """
        )

    rows = cur.fetchall()
    hook = os.getenv("SLACK_WEBHOOK")
    processed = 0

    for r in rows:
        line = f"[notify] {r['created_at']} user={r.get('user_id')} kind={r['kind']} payload={r['payload']}"
        print(line)
        if hook:
            try:
                requests.post(hook, json={"text": line}, timeout=5)
            except Exception as e:
                print("[notify] slack error:", e)

        if has_processed:
            with conn.cursor() as c2:
                c2.execute(
                    "update public.events set processed=true where id=%s", (r["id"],)
                )
        processed += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"processed {processed} alerts")


if __name__ == "__main__":
    drain()
