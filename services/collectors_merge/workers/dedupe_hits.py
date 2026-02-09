from __future__ import annotations

import logging
import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(".env")

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ["DATABASE_URL"]


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
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
        logger.info("deduped, deleted=%d", cur.rowcount)
        conn.commit()
        cur.close()
    except Exception as e:
        logger.exception("dedupe_hits failed: %s", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [dedupe] %(levelname)s: %(message)s")
    main()
