from __future__ import annotations

import datetime as dt
import json
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv(".env")


def db():
    return psycopg2.connect(os.environ["DATABASE_URL"])


ROWS = [
    {
        "provider": "ebay",
        "listing_id": "gunpla-1",
        "title": "Bandai MG RX-78-2 Ver.Ka (SEALED)",
        "price": 72.0,
        "currency": "EUR",
        "shipping": 8.0,
        "condition": "new",
        "graded": False,
        "ended_at": (dt.datetime.utcnow() - dt.timedelta(days=4)).isoformat() + "Z",
        "url": "https://example.com/g1",
        "seller_score": 0.99,
        "features_json": {},
        "normalized_key": "gunpla|sku:MG-RX-78-2|s:1",
    },
    {
        "provider": "ebay",
        "listing_id": "gunpla-2",
        "title": "MG RX-78-2 (Built, Complete)",
        "price": 48.0,
        "currency": "EUR",
        "shipping": 7.0,
        "condition": "used",
        "graded": False,
        "ended_at": (dt.datetime.utcnow() - dt.timedelta(days=11)).isoformat() + "Z",
        "url": "https://example.com/g2",
        "seller_score": 1.00,
        "features_json": {},
        "normalized_key": "gunpla|sku:MG-RX-78-2|s:0",
    },
]


def run():
    conn = db()
    cur = conn.cursor()
    for r in ROWS:
        cur.execute(
            """
         insert into public.market_hits
         (provider, listing_id, title, price, currency, shipping, condition, graded, ended_at, url, seller_score, features_json, normalized_key)
         values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
         on conflict do nothing
        """,
            (
                r["provider"],
                r["listing_id"],
                r["title"],
                r["price"],
                r["currency"],
                r["shipping"],
                r["condition"],
                r["graded"],
                r["ended_at"],
                r["url"],
                r["seller_score"],
                json.dumps(r["features_json"]),
                r["normalized_key"],
            ),
        )
    conn.commit()
    cur.close()
    conn.close()
    print(f"seeded {len(ROWS)} Gunpla rows")


if __name__ == "__main__":
    run()
