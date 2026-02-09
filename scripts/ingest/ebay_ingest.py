#!/usr/bin/env python3
import datetime
import json
import os
import time

import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
EUR_RATE = float(os.environ.get("EUR_RATE", "1.0"))  # optionally set daily via ECB
LIMIT = int(os.environ.get("EBAY_LIMIT", "50"))
CATEGORY = os.environ.get("INGEST_CATEGORY", "Pokemon")

# Choose one path:
EBAY_RAPID_KEY = os.environ.get("RAPIDAPI_KEY")  # if using RapidAPI wrapper
EBAY_APP_OAUTH = os.environ.get(
    "EBAY_OAUTH_TOKEN"
)  # if using official eBay API (Browse/Buy API)


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


def to_eur(price, currency):
    if not price:
        return None
    if (currency or "").upper() == "EUR":
        return round(float(price), 2)
    # naive single-rate conversion; for production, query live FX and store fx_rate_used
    return round(float(price) * EUR_RATE, 2)


def items_from_rapid(query):
    # Example RapidAPI: ebay-data-scraper find sold items
    url = "https://ebay-data-scraper.p.rapidapi.com/find/items"
    params = {"q": query, "sold": "true", "limit": str(LIMIT)}
    hdrs = {
        "X-RapidAPI-Key": EBAY_RAPID_KEY,
        "X-RapidAPI-Host": "ebay-data-scraper.p.rapidapi.com",
    }
    r = requests.get(url, headers=hdrs, params=params, timeout=60)
    r.raise_for_status()
    return r.json().get("items", [])


def items_from_official(query):
    # eBay Browse API: /buy/browse/v1/item_summary/search ? q=... & filter=buyingOptions:{FIXED_PRICE}|AUCTION & fieldgroups=ASPECTS
    # Sold data often needs the "Marketing" or "Finding" / "Browse" variants—adjust per your app creds.
    url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    params = {"q": query, "limit": str(LIMIT)}
    hdrs = {"Authorization": f"Bearer {EBAY_APP_OAUTH}"}
    r = requests.get(url, headers=hdrs, params=params, timeout=60)
    r.raise_for_status()
    return r.json().get("itemSummaries", [])


def normalize(item, provider, query):
    if provider == "ebay_rapid":
        price = (item.get("price") or {}).get("value")
        currency = (item.get("price") or {}).get("currency")
        sold = bool(item.get("sold"))
        ts = (
            item.get("endTime")
            or item.get("date")
            or datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
        )
        return {
            "provider": "ebay",
            "source_id": item.get("itemId")
            or item.get("legacyItemId")
            or item.get("id")
            or f"unknown-{hash(str(item))}",
            "url": item.get("itemWebUrl") or item.get("url"),
            "title": item.get("title"),
            "category": CATEGORY or query,
            "condition": (item.get("condition") or {}).get("conditionDisplayName")
            or item.get("condition"),
            "currency": currency,
            "price": float(price) if price else None,
            "price_eur": to_eur(price, currency),
            "is_sold": sold,
            "observed_at": ts,
            "image_url": (item.get("image") or {}).get("imageUrl")
            or (item.get("image") or {}).get("url"),
            "raw": item,
        }
    else:
        price = (
            (item.get("price") or {}).get("value")
            if isinstance(item.get("price"), dict)
            else None
        )
        currency = (
            (item.get("price") or {}).get("currency")
            if isinstance(item.get("price"), dict)
            else "EUR"
        )
        ts = (
            item.get("itemEndDate")
            or item.get("itemCreationDate")
            or datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
        )
        return {
            "provider": "ebay",
            "source_id": item.get("itemId")
            or item.get("legacyItemId")
            or item.get("itemGroupId")
            or f"unknown-{hash(str(item))}",
            "url": item.get("itemWebUrl") or item.get("itemAffiliateWebUrl"),
            "title": item.get("title"),
            "category": CATEGORY or query,
            "condition": (
                (item.get("condition") or {}).get("conditionDisplayName")
                if isinstance(item.get("condition"), dict)
                else item.get("condition")
            ),
            "currency": currency,
            "price": float(price) if price else None,
            "price_eur": to_eur(price, currency),
            "is_sold": False,  # official search sample; wire sold endpoint if available to your app
            "observed_at": ts,
            "image_url": (item.get("image") or {}).get("imageUrl"),
            "raw": item,
        }


def run(query):
    if EBAY_RAPID_KEY:
        items = items_from_rapid(query)
        normalized = [normalize(i, "ebay_rapid", query) for i in items]
    elif EBAY_APP_OAUTH:
        items = items_from_official(query)
        normalized = [normalize(i, "ebay_official", query) for i in items]
    else:
        print("Set RAPIDAPI_KEY or EBAY_OAUTH_TOKEN")
        return
    # keep only with price + title
    rows = [r for r in normalized if r["title"] and r["price_eur"]]
    # upsert in chunks
    B = 100
    for i in range(0, len(rows), B):
        supa_upsert(rows[i : i + B])
        time.sleep(0.5)
    print(f"Upserted {len(rows)} observations for query='{query}'")


if __name__ == "__main__":
    q = os.environ.get("EBAY_QUERY") or "Pikachu VMAX"
    run(q)
