from __future__ import annotations

import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(".env")
DATABASE_URL = os.environ["DATABASE_URL"]


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    # keep newest ended_at per (normalized_key, provider, listing_id)
    cur.execute(
        """
      with ranked as (
        select id,
               row_number() over (
                 partition by normalized_key, provider, listing_id
                 order by coalesce(ended_at, now()) desc, id desc
               ) as rn
        from public.market_hits
      )
      delete from public.market_hits mh
      using ranked r
      where mh.id = r.id and r.rn > 1
    """
    )
    print(f"deduped, deleted={cur.rowcount}")
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
