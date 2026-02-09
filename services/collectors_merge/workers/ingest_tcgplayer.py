from __future__ import annotations

import json
import logging
import os

import psycopg2

from services.collectors_merge.core.market_models import MarketHit
from services.collectors_merge.providers.tcgplayer.sales import recent_sales

logger = logging.getLogger(__name__)


def db():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def upsert_market_hits(conn, hits: list[MarketHit]):
    cur = conn.cursor()
    for h in hits:
        cur.execute(
            """
            insert into public.market_hits(provider, listing_id, title, price, currency, shipping, condition, graded, ended_at, url, seller_score, features_json, normalized_key)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
            on conflict do nothing;
        """,
            (
                h.provider,
                h.listing_id,
                h.title,
                h.price,
                h.currency,
                h.shipping,
                h.condition,
                h.graded,
                h.ended_at,
                h.url,
                h.seller_score,
                json.dumps(h.features_json),
                h.normalized_key,
            ),
        )
    conn.commit()


def main(product_id: int = 0):
    rows = recent_sales(product_id, days=30)
    logger.info("tcg fetched %d", len(rows))
    # parse rows -> MarketHit...
    # upsert_market_hits(db(), hits)
    logger.info("tcg ingest scaffold complete")


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [tcgplayer] %(levelname)s: %(message)s")
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    main(pid)
