from __future__ import annotations

import datetime as dt
import json
import logging
import os
import sys
from typing import Any

import psycopg2

logger = logging.getLogger(__name__)


def db():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def load_raw(path: str) -> list[dict[str, Any]]:
    if os.path.exists(path):
        with open(path) as f:
            return [json.loads(line) for line in f]
    # Fallback stub dataset
    logger.warning("%s not found; using stub dataset", path)
    now = dt.datetime.now(dt.timezone.utc)
    return [
        {
            "provider": "ebay",
            "listing_id": "stub-1",
            "title": "LEGO 10240 X-Wing Starfighter (NEW, SEALED)",
            "price": 255.0,
            "currency": "EUR",
            "shipping": 10.0,
            "condition": "new",
            "graded": False,
            "ended_at": (now - dt.timedelta(days=2)).isoformat() + "Z",
            "url": "https://example.com/a",
            "seller_score": 0.99,
            "features_json": {},
            "normalized_key": "lego|10240|pcs:1559|ret:1|s:1",
        },
        {
            "provider": "ebay",
            "listing_id": "stub-2",
            "title": "LEGO 10240 X-Wing - Complete w/ Box",
            "price": 210.0,
            "currency": "EUR",
            "shipping": 12.0,
            "condition": "used",
            "graded": False,
            "ended_at": (now - dt.timedelta(days=9)).isoformat() + "Z",
            "url": "https://example.com/b",
            "seller_score": 0.98,
            "features_json": {},
            "normalized_key": "lego|10240|pcs:1559|ret:1|s:1",
        },
    ]


def upsert_rows(rows: list[dict[str, Any]]):
    conn = db()
    try:
        cur = conn.cursor()
        for r in rows:
            cur.execute(
                """
                insert into public.market_hits
                  (provider, listing_id, title, price, currency, shipping, condition, graded, ended_at, url, seller_score, features_json, normalized_key)
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                on conflict do nothing
            """,
                (
                    r.get("provider"),
                    r.get("listing_id"),
                    r.get("title"),
                    r.get("price"),
                    r.get("currency"),
                    r.get("shipping"),
                    r.get("condition"),
                    r.get("graded"),
                    r.get("ended_at"),
                    r.get("url"),
                    r.get("seller_score"),
                    json.dumps(r.get("features_json") or {}),
                    r.get("normalized_key"),
                ),
            )
        conn.commit()
        cur.close()
    except Exception as e:
        logger.exception("upsert_rows failed: %s", e)
        raise
    finally:
        conn.close()


def main(path="ebay_sold.jsonl"):
    rows = load_raw(path)
    upsert_rows(rows)
    logger.info("ingested %d rows", len(rows))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [ingest_ebay] %(levelname)s: %(message)s")
    main(sys.argv[1] if len(sys.argv) > 1 else "ebay_sold.jsonl")
