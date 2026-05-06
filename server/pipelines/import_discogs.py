#!/usr/bin/env python3
"""
Discogs pipeline — "minimum asking price" per release via Discogs API.

IMPORTANT: Discogs does NOT expose sold prices via API. The /marketplace
endpoints only surface CURRENTLY LISTED prices. We store these clearly
tagged as listings (not sold comps) so valuation downstream can weight
them appropriately.

Data produced per catalog item:
  - price        = release.lowest_price (USD)
  - condition    = "listing"  (distinguishes from NM/sold grades)
  - provider     = "discogs_listing"
  - features_json.is_sold = false
  - features_json.listing_type = "min_asking"
  - features_json.num_for_sale = current stock count

Target categories (all currently at 0% market-hit coverage):
  vinyl_records, anime_ost_vinyl, anime_soundtrack, anime_bluray,
  city_pop_vinyl.

Rate limit: Discogs allows ~60 authenticated requests / minute. We pace
ourselves at ~1.1s per request (safe margin) and honor Retry-After when
it fires. Full pass over ~4.5K items with 2 API calls each ≈ 3 hours.

Schedule: daily (24h). Prices move slowly on Discogs.

Usage:
  python pipelines/import_discogs.py
  python pipelines/import_discogs.py --category vinyl_records
  python pipelines/import_discogs.py --dry-run --limit 20
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from typing import Optional

import httpx

REPO_SERVER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_SERVER not in sys.path:
    sys.path.insert(0, REPO_SERVER)

from pipelines.import_common import (
    MarketHit,
    IngestStats,
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY,
    _headers,
    get_http_client,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [import_discogs] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DISCOGS_API = "https://api.discogs.com"
USER_AGENT = "CollectAI-DiscogsImporter/1.0 +https://collectai.app"

# Categories to pull. These are the 0% coverage ones where even a listing
# price is a meaningful anchor vs the current absence of any signal.
TARGET_CATEGORIES: list[str] = [
    "vinyl_records",
    "anime_ost_vinyl",
    "anime_soundtrack",
    "anime_bluray",
    "city_pop_vinyl",
]

# Pacing — Discogs authenticated limit is 60 req/min per token. We do
# 2 requests per item (search + release), so a single worker can safely
# process ~25 items/min. Leave headroom for bursts/retries.
REQUEST_INTERVAL_S = 1.1


def _discogs_token() -> Optional[str]:
    # Personal token is the simplest auth flow Discogs supports. OAuth is
    # also valid but we don't need per-user scoping.
    return os.environ.get("DISCOGS_PERSONAL_TOKEN") or os.environ.get("DISCOGS_TOKEN")


def _discogs_headers() -> dict[str, str]:
    tok = _discogs_token()
    if not tok:
        raise RuntimeError("DISCOGS_PERSONAL_TOKEN not set")
    return {
        "Authorization": f"Discogs token={tok}",
        "User-Agent": USER_AGENT,
    }


def _get(
    client: httpx.Client,
    path: str,
    params: Optional[dict] = None,
) -> Optional[dict]:
    """GET a Discogs endpoint, respecting rate-limit headers."""
    url = f"{DISCOGS_API}{path}"
    try:
        r = client.get(url, params=params, headers=_discogs_headers(), timeout=30)
    except httpx.HTTPError as e:
        logger.warning("GET %s failed: %s", path, e)
        return None

    # Respect rate limit
    remaining = r.headers.get("X-Discogs-Ratelimit-Remaining")
    if remaining and remaining.isdigit() and int(remaining) < 3:
        logger.info("Discogs rate-limit low (%s left); pausing 10s", remaining)
        time.sleep(10)

    if r.status_code == 429:
        retry_after = int(r.headers.get("Retry-After", "30"))
        logger.warning("Discogs 429, sleeping %ds", retry_after)
        time.sleep(retry_after)
        return None
    if r.status_code != 200:
        logger.warning("GET %s -> HTTP %d: %s", path, r.status_code, r.text[:200])
        return None
    try:
        return r.json()
    except Exception as e:
        logger.warning("GET %s non-JSON: %s", path, e)
        return None


# ---------------------------------------------------------------------------
# Catalog reader
# ---------------------------------------------------------------------------


def get_catalog_items(
    conn, category: str, limit: Optional[int] = None,
) -> list[dict]:
    """Return category_items that don't have fresh Discogs listings yet."""
    sql = """
      SELECT ci.category, ci.item_key, ci.title
      FROM public.category_items ci
      WHERE ci.category = %s
        AND ci.title IS NOT NULL
        AND NOT EXISTS (
          SELECT 1 FROM public.market_hits mh
          WHERE mh.provider = 'discogs_listing'
            AND mh.normalized_key = ci.category || ':' || ci.item_key
            AND mh.seen_at > now() - INTERVAL '7 days'
        )
      ORDER BY RANDOM()
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql, (category,)).fetchall()
    return [dict(r) for r in rows]


def _get_stale_items_pg(dsn: str, category: str, limit: Optional[int]) -> list[dict]:
    """Query catalog items using asyncpg via sync wrapper. Kept separate from
    the rest of pipelines because we want a lightweight DB query, not an
    orchestrated import pass."""
    import asyncio
    import asyncpg

    async def _run():
        # Tagged via application_name for the ExecStop cancel hook.
        c = await asyncpg.connect(
            dsn,
            server_settings={"application_name": "collectai-bake-discogs_worker"},
        )
        try:
            q = """
              SELECT ci.category, ci.item_key, ci.title
              FROM public.category_items ci
              WHERE ci.category = $1
                AND ci.title IS NOT NULL
                AND NOT EXISTS (
                  SELECT 1 FROM public.market_hits mh
                  WHERE mh.provider = 'discogs_listing'
                    AND mh.normalized_key = ci.category || ':' || ci.item_key
                    AND mh.seen_at > now() - INTERVAL '7 days'
                )
              ORDER BY RANDOM()
            """
            args: list = [category]
            if limit:
                q += " LIMIT $2"
                args.append(int(limit))
            return [dict(r) for r in await c.fetch(q, *args)]
        finally:
            await c.close()

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Discogs lookup — title → best release → price stats
# ---------------------------------------------------------------------------


import re

# Strip colorway/variant/edition parentheticals our catalog adds to titles
# (e.g. "Cowboy Bebop OST (1998) (Black)" → "Cowboy Bebop OST 1998").
# Discogs catalog tracks base releases, not individual colorway pressings,
# so leaving these in tanks the match rate on anime_ost_vinyl/city_pop_vinyl.
_VARIANT_RX = re.compile(r"\s*\([^)]{1,40}\)\s*$")


def _clean_title(title: str) -> str:
    t = title
    for _ in range(4):  # titles often have 1-3 trailing parentheticals
        new = _VARIANT_RX.sub(" ", t).strip()
        if new == t:
            break
        t = new
    # Drop trailing bracket annotations too
    t = re.sub(r"\s*\[[^\]]{1,40}\]\s*$", " ", t).strip()
    return t or title  # never return empty


def _best_release_match(
    client: httpx.Client, title: str, category: str,
) -> Optional[dict]:
    """Search Discogs for the title; return the top release match, or None."""
    # Narrow to releases only; broader search drags in "master" entries.
    # For vinyl-family categories, prefer Vinyl format; for anime_bluray
    # we omit the format filter so DVDs/BDs surface.
    clean = _clean_title(title)
    params: dict[str, str | int] = {
        "q": clean[:200],
        "type": "release",
        "per_page": 5,
    }
    if "vinyl" in category:
        params["format"] = "Vinyl"
    elif category == "anime_bluray":
        params["format"] = "Blu-ray"

    body = _get(client, "/database/search", params=params)
    if not body:
        return None
    results = body.get("results") or []
    return results[0] if results else None


def _release_stats(client: httpx.Client, release_id: int) -> Optional[dict]:
    """Fetch release stats: lowest_price + num_for_sale + main image."""
    body = _get(client, f"/releases/{release_id}")
    if not body:
        return None
    return {
        "lowest_price": body.get("lowest_price"),
        "num_for_sale": body.get("num_for_sale", 0),
        "year": body.get("year"),
        "image_url": ((body.get("images") or [{}])[0]).get("uri", "") or "",
        "url": body.get("uri") or f"https://www.discogs.com/release/{release_id}",
        "title": body.get("title") or "",
    }


# ---------------------------------------------------------------------------
# Build + upsert
# ---------------------------------------------------------------------------


def _upsert(hits: list[MarketHit], stats: IngestStats) -> int:
    """POST hits via the upsert_market_hits_batch RPC.

    Replaces the broken `?on_conflict=provider,listing_id` route which
    stopped working after market_hits was partitioned (2026-04-19). See
    supabase/migrations/20260426_upsert_market_hits_batch_rpc.sql.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return 0
    if not hits:
        return 0
    client = get_http_client()
    url = f"{SUPABASE_URL}/rest/v1/rpc/upsert_market_hits_batch"
    headers = {**_headers(), "Content-Type": "application/json"}

    # R50l: FX conversion — discogs price comes back in the user's configured
    # currency, usually USD. Training on mixed currency corrupts the model
    # (learning #23). Convert to EUR at upsert time.
    try:
        from app.lib.fx_service import convert_to_eur_sync
    except Exception:
        convert_to_eur_sync = None

    rows = []
    for h in hits:
        features = {
            "is_sold": False,
            "listing_type": "min_asking",
            "source_note": "discogs_api_lowest_price",
        }
        if convert_to_eur_sync and h.currency and h.currency != "EUR":
            try:
                price_eur = convert_to_eur_sync(float(h.price), h.currency)
            except Exception:
                price_eur = h.price
        else:
            price_eur = h.price
        # item_ref must be the canonical `{category}:{normalized_key}` form
        # (learnings.md §22, §64, R50m backfill). Prior code wrote bare
        # normalized_key producing rows invisible to valuation joins.
        if h.normalized_key and ":" in h.normalized_key:
            item_ref = h.normalized_key
        elif h.category and h.normalized_key:
            item_ref = f"{h.category}:{h.normalized_key}"
        else:
            item_ref = None
        rows.append({
            "provider": h.provider,
            "listing_id": h.listing_id,
            "title": h.title,
            "price": h.price,
            "currency": h.currency,
            "price_eur": price_eur,
            "condition": h.condition,
            "normalized_key": h.normalized_key,
            "item_ref": item_ref,
            "category": h.category,
            "url": h.url,
            "image_url": h.image_url,
            "features_json": features,
            "is_listing": True,  # asking-price data, not sold comp
        })

    total = 0
    for i in range(0, len(rows), 100):
        batch = rows[i:i + 100]
        try:
            r = client.post(url, headers=headers, json={"rows": batch})
        except Exception as e:
            stats.market_hits_errors += 1
            logger.error("upsert RPC failed: %s", e)
            continue
        if r.status_code in (200, 201, 204):
            try:
                inserted = int(r.text or "0")
            except (TypeError, ValueError):
                inserted = len(batch)
            total += inserted
        else:
            stats.market_hits_errors += 1
            logger.error("upsert HTTP %d: %s", r.status_code, r.text[:300])
    stats.market_hits_upserted += total
    return total


def process_category(
    client: httpx.Client,
    category: str,
    items: list[dict],
    dry_run: bool,
    stats: IngestStats,
) -> dict:
    total_found = 0
    total_listed = 0  # had lowest_price > 0
    total_upserted = 0
    hits_buffer: list[MarketHit] = []

    for idx, it in enumerate(items):
        title = it["title"]
        item_key = it["item_key"]
        t0 = time.monotonic()
        try:
            match = _best_release_match(client, title, category)
            if not match:
                continue
            total_found += 1
            rid = match.get("id")
            if not rid:
                continue
            rstats = _release_stats(client, rid)
            if not rstats:
                continue
            price = rstats.get("lowest_price")
            if not price or float(price) <= 0:
                continue
            total_listed += 1

            hit = MarketHit(
                provider="discogs_listing",
                listing_id=f"discogs:{rid}",
                title=(rstats["title"] or title)[:500],
                price=float(price),
                currency="USD",
                condition="listing",
                normalized_key=f"{category}:{item_key}",
                category=category,
                url=rstats["url"],
                image_url=rstats["image_url"],
            )
            hits_buffer.append(hit)
        except Exception as e:
            logger.warning("item %s failed: %s", title[:40], e)

        # Pace requests (2 calls per item ≈ REQUEST_INTERVAL_S per call)
        elapsed = time.monotonic() - t0
        if elapsed < REQUEST_INTERVAL_S * 2:
            time.sleep(REQUEST_INTERVAL_S * 2 - elapsed)

        # Flush every 50 to bound memory and surface progress
        if len(hits_buffer) >= 50:
            upserted = 0 if dry_run else _upsert(hits_buffer, stats)
            total_upserted += upserted
            logger.info(
                "  %s progress: %d/%d processed, %d w/ listings, %d upserted",
                category, idx + 1, len(items), total_listed, total_upserted,
            )
            hits_buffer = []

    if hits_buffer:
        upserted = 0 if dry_run else _upsert(hits_buffer, stats)
        total_upserted += upserted

    return {
        "category": category,
        "items_processed": len(items),
        "releases_matched": total_found,
        "with_listings": total_listed,
        "upserted": total_upserted,
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_pipeline(
    only_category: Optional[str] = None,
    limit_per_cat: Optional[int] = None,
    dry_run: bool = False,
) -> dict:
    dsn = os.environ.get("DB_DSN", "")
    if not dsn:
        logger.error("DB_DSN not set")
        return {"ok": False, "reason": "no DB_DSN"}

    cats = [only_category] if only_category else TARGET_CATEGORIES
    stats = IngestStats()
    results = []
    started = time.monotonic()

    with httpx.Client(http2=False) as client:
        for cat in cats:
            items = _get_stale_items_pg(dsn, cat, limit_per_cat)
            logger.info("── %s: %d items to probe ──", cat, len(items))
            if not items:
                continue
            r = process_category(client, cat, items, dry_run, stats)
            results.append(r)
            logger.info(
                "%s done: %d matched, %d listed, %d upserted",
                cat, r["releases_matched"], r["with_listings"], r["upserted"],
            )

    elapsed = time.monotonic() - started
    summary = {
        "ok": stats.market_hits_errors == 0,
        "elapsed_s": round(elapsed, 1),
        "dry_run": dry_run,
        "per_category": results,
        "total_upserted": sum(r["upserted"] for r in results),
        "errors": stats.market_hits_errors,
    }
    logger.info(
        "DONE: %d upserted, %d errors, %.0fs",
        summary["total_upserted"], summary["errors"], elapsed,
    )
    return summary


async def run_once() -> None:
    import asyncio
    try:
        from app.worker_registry import record_run
    except Exception:
        def record_run(*_a, **_kw): pass

    loop = asyncio.get_running_loop()
    t0 = time.monotonic()
    try:
        summary = await loop.run_in_executor(None, run_pipeline)
        dur = time.monotonic() - t0
        status = "ok" if summary.get("ok") else "error"
        record_run("discogs_worker", status, duration_s=dur)
    except Exception as e:
        logger.exception("discogs run_once failed: %s", e)
        record_run("discogs_worker", "error")
        raise


def main() -> int:
    p = argparse.ArgumentParser(description="Discogs listing-price import")
    p.add_argument("--category", type=str, default=None,
                   help=f"one of {TARGET_CATEGORIES}")
    p.add_argument("--limit", type=int, default=None,
                   help="max items per category (for testing)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    summary = run_pipeline(
        only_category=args.category,
        limit_per_cat=args.limit,
        dry_run=args.dry_run,
    )
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
