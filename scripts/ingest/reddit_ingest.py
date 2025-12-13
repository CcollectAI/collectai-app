#!/usr/bin/env python3
import datetime
import json
import os
import re
import time

import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SUBS = (os.environ.get("REDDIT_SUBS") or "pokemoncards").split(",")
CLIENT_ID = os.environ["REDDIT_CLIENT_ID"]
SECRET = os.environ["REDDIT_SECRET"]
UA = "collectai/1.0 by your_username"

PRICE_RE = re.compile(r"(€|\$|£)\s?([0-9]+(?:\.[0-9]{1,2})?)")


def auth():
    r = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=(CLIENT_ID, SECRET),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": UA},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def supa_upsert(rows):
    if not rows:
        return
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/market_observations",
        headers={
            "apikey": SERVICE_KEY,
            "Authorization": f"Bearer {SERVICE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        },
        data=json.dumps(rows),
        timeout=60,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"Upsert failed: {r.status_code} {r.text}")


def run():
    token = auth()
    hdrs = {"Authorization": f"bearer {token}", "User-Agent": UA}
    rows = []
    for sub in SUBS:
        url = f"https://oauth.reddit.com/r/{sub}/new?limit=50"
        j = requests.get(url, headers=hdrs, timeout=30).json()
        for child in j.get("data", {}).get("children", []):
            d = child.get("data", {})
            title = d.get("title", "")
            m = PRICE_RE.search(title)
            if not m:
                continue
            symbol, amount = m.groups()
            amount = float(amount)
            currency = {"€": "EUR", "$": "USD", "£": "GBP"}.get(symbol, "USD")
            ts = (
                datetime.datetime.utcfromtimestamp(
                    d.get("created_utc", time.time())
                ).isoformat()
                + "Z"
            )
            rows.append(
                {
                    "provider": "reddit",
                    "source_id": d.get("id"),
                    "url": "https://reddit.com" + d.get("permalink", ""),
                    "title": title,
                    "category": sub,
                    "condition": None,
                    "currency": currency,
                    "price": amount,
                    "price_eur": (
                        amount if currency == "EUR" else None
                    ),  # normalize via fx later
                    "is_sold": False,
                    "observed_at": ts,
                    "image_url": None,
                    "raw": d,
                }
            )
        time.sleep(0.7)
    supa_upsert(rows)
    print(f"Upserted {len(rows)} reddit observations.")


if __name__ == "__main__":
    run()
