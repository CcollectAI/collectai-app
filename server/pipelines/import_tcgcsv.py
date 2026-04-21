#!/usr/bin/env python3
"""
tcgcsv.com pipeline — free daily TCGPlayer public-price dump.

Fills the TCG data gap created by TCGPlayer closing registrations and
Cardmarket restricting scraping. tcgcsv.com is a community service that
republishes TCGPlayer's public price pages as clean JSON daily.

What this writes:
  market_hits rows with provider='tcgcsv'. Unique key (provider, listing_id)
  where listing_id = TCGPlayer productId. Upserts so re-runs update prices.

Covers: MTG, Pokemon, YuGiOh, Lorcana, One Piece TCG, Digimon. Other
games that tcgcsv indexes (Flesh and Blood, Star Wars Unlimited, etc.)
are skipped unless we add them to CATEGORY_MAP.

Schedule: run_once() daily.

Usage:
  python pipelines/import_tcgcsv.py             # all supported games
  python pipelines/import_tcgcsv.py --game mtg  # single game
  python pipelines/import_tcgcsv.py --dry-run   # fetch but don't upsert
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from typing import Optional

import httpx

# Add server/ so imports work both as script and as module
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
    format="%(asctime)s [import_tcgcsv] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer"

# Map tcgcsv "name" field → our internal category name.
# Discovered via GET /tcgplayer/categories. Names on tcgcsv are canonical
# ("Magic" not "Magic: The Gathering") so we match by name, case-sensitive.
CATEGORY_MAP: dict[str, str] = {
    "Magic": "mtg",
    "YuGiOh": "yugioh",
    "Pokemon": "pokemon",
    "Disney Lorcana TCG": "lorcana",
    "Lorcana TCG": "lorcana",          # in case they rename
    "One Piece Card Game": "one_piece_tcg",
    "Digimon Card Game": "digimon",
}

# Upstream requests — conservative timeouts. Some group payloads are large.
HTTP_TIMEOUT = 60.0
PER_REQUEST_SLEEP = 0.25  # be polite to tcgcsv.com


# ---------------------------------------------------------------------------
# tcgcsv fetch helpers
# ---------------------------------------------------------------------------


def _get_json(client: httpx.Client, url: str):
    """GET a tcgcsv endpoint. Returns None on failure (non-fatal)."""
    try:
        r = client.get(url, timeout=HTTP_TIMEOUT)
    except httpx.HTTPError as e:
        logger.warning("GET %s failed: %s", url, e)
        return None
    if r.status_code != 200:
        logger.warning("GET %s -> HTTP %d", url, r.status_code)
        return None
    try:
        body = r.json()
    except Exception as e:
        logger.warning("GET %s -> non-JSON body: %s", url, e)
        return None
    # tcgcsv wraps lists in {"results": [...]} but occasionally returns the
    # raw list — handle both.
    if isinstance(body, dict) and "results" in body:
        return body["results"]
    return body


def list_supported_categories(client: httpx.Client) -> list[dict]:
    """Return [{categoryId, name, our_category}] for games we care about."""
    cats = _get_json(client, f"{TCGCSV_BASE}/categories") or []
    out: list[dict] = []
    for c in cats:
        name = c.get("name")
        if name in CATEGORY_MAP:
            out.append({
                "categoryId": c["categoryId"],
                "name": name,
                "our_category": CATEGORY_MAP[name],
            })
    return out


def list_groups(client: httpx.Client, category_id: int) -> list[dict]:
    return _get_json(client, f"{TCGCSV_BASE}/{category_id}/groups") or []


def list_products(client: httpx.Client, category_id: int, group_id: int) -> list[dict]:
    return _get_json(
        client, f"{TCGCSV_BASE}/{category_id}/{group_id}/products",
    ) or []


def list_prices(client: httpx.Client, category_id: int, group_id: int) -> list[dict]:
    return _get_json(
        client, f"{TCGCSV_BASE}/{category_id}/{group_id}/prices",
    ) or []


# ---------------------------------------------------------------------------
# Transform tcgcsv rows → MarketHit
# ---------------------------------------------------------------------------


def build_hits(
    products: list[dict],
    prices: list[dict],
    our_category: str,
    group_abbreviation: Optional[str] = None,
) -> list[MarketHit]:
    """Join products + prices on productId and materialise MarketHit rows.

    We keep only rows with a non-null marketPrice (real signal). Variants
    with distinct subTypeName (e.g. Normal vs Holofoil) are separate hits
    because their prices diverge.
    """
    # Index products for O(1) join
    by_pid: dict[int, dict] = {p["productId"]: p for p in products if p.get("productId")}

    hits: list[MarketHit] = []
    for price in prices:
        pid = price.get("productId")
        if pid is None:
            continue
        market = price.get("marketPrice")
        if market is None or float(market) <= 0:
            continue  # skip cards with no market signal
        prod = by_pid.get(pid)
        if not prod:
            continue

        subtype = (price.get("subTypeName") or "").strip()
        listing_id = f"{pid}:{subtype}" if subtype else str(pid)
        title = prod.get("name") or prod.get("cleanName") or f"tcgplayer:{pid}"
        if group_abbreviation:
            title = f"{title} [{group_abbreviation}]"
        if subtype:
            title = f"{title} ({subtype})"

        normalized_key = f"{our_category}:tcgplayer:{pid}"
        if subtype:
            normalized_key += f":{subtype.lower().replace(' ', '_')}"

        hits.append(MarketHit(
            provider="tcgcsv",
            listing_id=listing_id,
            title=title[:500],
            price=float(market),
            currency="USD",
            condition="NM",  # tcgplayer market prices are NM baseline
            normalized_key=normalized_key,
            category=our_category,
            url=prod.get("url") or "",
            image_url=prod.get("imageUrl") or "",
        ))
    return hits


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


def upsert_hits_batched(
    hits: list[MarketHit],
    stats: IngestStats,
    batch_size: int = 200,
) -> int:
    """POST hits to market_hits with on_conflict=provider,listing_id so
    daily re-runs update prices instead of 409'ing."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.warning("SUPABASE env not set — skipping upsert")
        return 0
    if not hits:
        return 0

    client = get_http_client()
    url = f"{SUPABASE_URL}/rest/v1/market_hits?on_conflict=provider,listing_id"
    headers = {**_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"}

    total = 0
    # R50l: FX conversion — all tcgcsv prices are USD. Mixed-currency rows in
    # market_hits corrupt training (learning #23). Convert USD → EUR via the
    # fx_service; fall back to storing price unchanged if FX lookup fails.
    try:
        from app.lib.fx_service import convert_to_eur_sync
    except Exception:
        convert_to_eur_sync = None

    for i in range(0, len(hits), batch_size):
        batch = hits[i:i + batch_size]
        rows = []
        for h in batch:
            if convert_to_eur_sync and h.currency and h.currency != "EUR":
                try:
                    price_eur = convert_to_eur_sync(float(h.price), h.currency)
                except Exception:
                    price_eur = h.price
            else:
                price_eur = h.price
            # item_ref must be canonical `{category}:{normalized_key}` so
            # valuation joins (learnings.md §22, §64, §957). The R50l fix
            # that originally added item_ref used bare normalized_key, then
            # R50m's backfill re-prefixed all rows. Updated 2026-04-21 to
            # emit the prefixed form at the writer so re-enabling this
            # pipeline doesn't reintroduce the bug.
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
            })
        try:
            resp = client.post(url, headers=headers, json=rows)
        except Exception as e:
            stats.market_hits_errors += 1
            logger.error("Batch %d-%d upsert failed: %s", i, i + len(batch), e)
            continue
        if resp.status_code in (200, 201, 204):
            total += len(batch)
        else:
            stats.market_hits_errors += 1
            logger.error(
                "Batch %d-%d HTTP %d: %s",
                i, i + len(batch), resp.status_code, resp.text[:300],
            )
    stats.market_hits_upserted += total
    return total


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_game(
    client: httpx.Client,
    category_id: int,
    category_name: str,
    our_category: str,
    dry_run: bool,
    stats: IngestStats,
) -> dict:
    """Import all groups for a single tcgcsv category. Returns per-game stats."""
    groups = list_groups(client, category_id)
    logger.info("%s (our=%s): %d groups", category_name, our_category, len(groups))

    total_hits = 0
    total_upserted = 0
    groups_processed = 0

    for g in groups:
        gid = g.get("groupId")
        if gid is None:
            continue
        group_name = g.get("name") or f"group:{gid}"
        group_abbr = g.get("abbreviation") or None
        time.sleep(PER_REQUEST_SLEEP)
        products = list_products(client, category_id, gid)
        time.sleep(PER_REQUEST_SLEEP)
        prices = list_prices(client, category_id, gid)
        if not products or not prices:
            logger.debug("  skip empty: %s (products=%d prices=%d)",
                         group_name, len(products), len(prices))
            continue
        hits = build_hits(products, prices, our_category, group_abbr)
        if not hits:
            continue
        total_hits += len(hits)
        groups_processed += 1
        if dry_run:
            logger.info("  [dry] %s: %d hits (sample: %s @ $%.2f)",
                        group_name[:40], len(hits),
                        hits[0].title[:40], hits[0].price)
            continue
        upserted = upsert_hits_batched(hits, stats)
        total_upserted += upserted
        logger.info("  %s: %d hits, %d upserted", group_name[:40], len(hits), upserted)

    return {
        "category": our_category,
        "groups_processed": groups_processed,
        "total_groups": len(groups),
        "total_hits": total_hits,
        "total_upserted": total_upserted,
    }


def run_pipeline(only_game: Optional[str] = None, dry_run: bool = False) -> dict:
    """Top-level entry point — orchestrates fetch + upsert for all games."""
    stats = IngestStats()
    results: list[dict] = []
    started = time.monotonic()

    with httpx.Client(
        headers={"User-Agent": "CollectAI-tcgcsv-importer/1.0"},
        timeout=HTTP_TIMEOUT,
    ) as client:
        supported = list_supported_categories(client)
        if not supported:
            logger.error("No supported categories returned by tcgcsv")
            return {"ok": False, "reason": "no categories"}

        if only_game:
            supported = [s for s in supported if s["our_category"] == only_game]
            if not supported:
                logger.error("Unknown game '%s' — valid: %s",
                             only_game, sorted(set(CATEGORY_MAP.values())))
                return {"ok": False, "reason": "unknown game"}

        for cat in supported:
            logger.info("─" * 60)
            r = run_game(
                client,
                cat["categoryId"],
                cat["name"],
                cat["our_category"],
                dry_run,
                stats,
            )
            results.append(r)

    elapsed = time.monotonic() - started
    summary = {
        "ok": stats.market_hits_errors == 0,
        "elapsed_s": round(elapsed, 1),
        "dry_run": dry_run,
        "per_game": results,
        "total_hits": sum(r["total_hits"] for r in results),
        "total_upserted": sum(r["total_upserted"] for r in results),
        "errors": stats.market_hits_errors,
    }
    logger.info("─" * 60)
    logger.info(
        "DONE: %d hits, %d upserted, %d errors in %.0fs",
        summary["total_hits"], summary["total_upserted"],
        summary["errors"], elapsed,
    )
    return summary


# ---------------------------------------------------------------------------
# Worker entry point (for bake_orchestrator)
# ---------------------------------------------------------------------------


async def run_once() -> None:
    """Async wrapper so bake_orchestrator can call this like a worker."""
    import asyncio
    # run_pipeline is sync + uses httpx.Client; delegate to a thread so we
    # don't block the orchestrator's event loop.
    try:
        from app.worker_registry import record_run
    except Exception:
        def record_run(*_a, **_kw):  # fallback if registry missing
            pass

    loop = asyncio.get_running_loop()
    t0 = time.monotonic()
    try:
        summary = await loop.run_in_executor(None, run_pipeline)
        duration = time.monotonic() - t0
        status = "ok" if summary.get("ok") else "error"
        record_run("tcgcsv_worker", status, duration_s=duration)
    except Exception as e:
        logger.exception("tcgcsv run_once failed: %s", e)
        record_run("tcgcsv_worker", "error")
        raise


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser(description="tcgcsv.com import pipeline")
    p.add_argument("--game", type=str, default=None,
                   help="only run one game (mtg, pokemon, yugioh, lorcana, one_piece_tcg, digimon)")
    p.add_argument("--dry-run", action="store_true",
                   help="fetch but do not upsert")
    args = p.parse_args()
    summary = run_pipeline(only_game=args.game, dry_run=args.dry_run)
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
