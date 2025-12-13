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
    # Charizard PSA10 demo comps
    {
        "provider": "ebay",
        "listing_id": "tcg-1",
        "title": "Charizard Base Set PSA 10",
        "price": 9800.0,
        "currency": "USD",
        "shipping": 25.0,
        "condition": "graded",
        "graded": True,
        "ended_at": (dt.datetime.utcnow() - dt.timedelta(days=3)).isoformat() + "Z",
        "url": "https://example.com/char1",
        "seller_score": 0.99,
        "features_json": {},
        "normalized_key": "tcg|psa:000000001|g:PSA10",
    },
    {
        "provider": "ebay",
        "listing_id": "tcg-2",
        "title": "Charizard PSA 10 Holo",
        "price": 10200.0,
        "currency": "USD",
        "shipping": 0.0,
        "condition": "graded",
        "graded": True,
        "ended_at": (dt.datetime.utcnow() - dt.timedelta(days=10)).isoformat() + "Z",
        "url": "https://example.com/char2",
        "seller_score": 1.00,
        "features_json": {},
        "normalized_key": "tcg|psa:000000001|g:PSA10",
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
    print(f"seeded {len(ROWS)} TCG rows")


if __name__ == "__main__":
    run()
