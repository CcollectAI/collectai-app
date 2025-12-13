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
        "listing_id": "snk-1",
        "title": "Nike Air Jordan 1 Retro High OG (DS)",
        "price": 310.0,
        "currency": "EUR",
        "shipping": 0.0,
        "condition": "new",
        "graded": False,
        "ended_at": (dt.datetime.utcnow() - dt.timedelta(days=5)).isoformat() + "Z",
        "url": "https://example.com/s1",
        "seller_score": 0.97,
        "features_json": {},
        "normalized_key": "sneakers|sku:AJ1-RETRO-HIGH-OG|s:1",
    },
    {
        "provider": "ebay",
        "listing_id": "snk-2",
        "title": "Jordan 1 Retro High OG (Used, VNDS)",
        "price": 220.0,
        "currency": "EUR",
        "shipping": 10.0,
        "condition": "used",
        "graded": False,
        "ended_at": (dt.datetime.utcnow() - dt.timedelta(days=12)).isoformat() + "Z",
        "url": "https://example.com/s2",
        "seller_score": 0.99,
        "features_json": {},
        "normalized_key": "sneakers|sku:AJ1-RETRO-HIGH-OG|s:0",
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
    print(f"seeded {len(ROWS)} Sneaker rows")


if __name__ == "__main__":
    run()
