#!/usr/bin/env python3
"""
Seed scrape — fetch live marketplace prices for categories that have
catalog items but zero market_hits.

Uses eBay Browse API as primary (free, structured JSON, no crawling credits).
Falls back to Firecrawl/other adapters only when eBay has weak coverage.

Usage:
    python3 scripts/seed_scrape.py                          # Tier 1 (10 categories)
    python3 scripts/seed_scrape.py --all                    # all categories with 0 hits
    python3 scripts/seed_scrape.py --category taylor_swift  # single category
    python3 scripts/seed_scrape.py --items-per-category 5   # fewer items (faster)
    python3 scripts/seed_scrape.py --dry-run                # show what would be scraped

After running, the valuation_worker will pick up the new market_hits on its
next cycle and compute fresh q10/q50/q90 predictions.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# Add server/ to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "server"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [seed_scrape] %(levelname)s: %(message)s")
logger = logging.getLogger("seed_scrape")

# Tier 1: high-value categories likely to be scanned by early users
TIER_1 = [
    "funko", "lego", "sneakers", "watches", "taylor_swift",
    "kpop_merch", "sportscards", "anime_figures", "hot_toys", "vintage_toys",
]

# Tier 2: additional categories worth seeding
TIER_2 = [
    "designer_toys", "vinyl_records", "warhammer", "retro_games", "manga",
    "fragrances", "keycaps", "disney", "gunpla", "bluray_steelbook",
    "kpop_lightsticks", "blind_box", "diecast", "scale_models", "loungefly",
    "action_figures", "comic_books", "digimon", "marvel_legends", "one_piece_tcg",
    "pens", "plush_collectibles", "retro_handhelds", "vintage_cameras", "whiskey",
]

# Categories that already have market_hits from API imports — skip these
ALREADY_SEEDED = {"pokemon", "yugioh", "mtg", "lorcana"}


async def get_categories_needing_scrape(conn, specific: str | None, do_all: bool) -> list[str]:
    """Return list of categories to scrape."""
    if specific:
        return [specific]

    # Find categories with catalog_items but few/no market_hits
    rows = await conn.fetch("""
        SELECT ci.category, count(DISTINCT ci.id) AS catalog_count,
               (SELECT count(*) FROM public.market_hits mh WHERE mh.category = ci.category) AS hit_count
        FROM public.category_items ci
        GROUP BY ci.category
        ORDER BY ci.category
    """)

    candidates = []
    for row in rows:
        cat = row["category"]
        if cat in ALREADY_SEEDED:
            continue
        if row["hit_count"] < 50:  # fewer than 50 hits = needs seeding
            candidates.append(cat)

    if do_all:
        return candidates

    # Default: Tier 1 only, filtered to what actually needs it
    return [c for c in TIER_1 if c in candidates]


async def get_sample_items(conn, category: str, limit: int) -> list[dict]:
    """Pick a diverse sample of items from category_items for scraping.

    Prefers items with images and higher estimated value (more likely to have
    marketplace listings). Returns dicts with title + item_key.
    """
    rows = await conn.fetch("""
        SELECT title, item_key, image_url,
               COALESCE((attributes_json->>'estimated_price')::numeric, 0) AS est_price
        FROM public.category_items
        WHERE category = $1
          AND title IS NOT NULL
          AND length(title) > 3
        ORDER BY
            CASE WHEN image_url IS NOT NULL THEN 0 ELSE 1 END,
            COALESCE((attributes_json->>'estimated_price')::numeric, 0) DESC
        LIMIT $2
    """, category, limit)

    return [{"title": r["title"], "item_key": r["item_key"]} for r in rows]


def simplify_query(title: str, category: str) -> str:
    """Simplify a catalog title into a better marketplace search query.

    Catalog titles are often hyper-specific ("Folklore Running Like Water Vinyl
    (Green)") which return 0 results on eBay. Simplify to the essence:
    "Taylor Swift Folklore Vinyl" or "LeBron James Topps Chrome".
    """
    import re
    # Strip parentheticals like (Refractor), (Green), (Target Exclusive)
    q = re.sub(r"\([^)]*\)", "", title).strip()
    # Strip common suffixes that hurt search
    for suffix in ["Limited Edition", "Exclusive", "Deluxe", "Special Edition"]:
        q = q.replace(suffix, "").strip()
    # For specific categories, prepend the category context
    CATEGORY_PREFIX = {
        "taylor_swift": "Taylor Swift",
        "kpop_merch": "",  # BTS/Blackpink already in title
        "kpop_lightsticks": "",
        "sportscards": "",
        "fragrances": "",
    }
    prefix = CATEGORY_PREFIX.get(category, "")
    if prefix and prefix.lower() not in q.lower():
        q = f"{prefix} {q}"
    # Limit to ~8 words max (long queries confuse eBay search)
    words = q.split()
    if len(words) > 8:
        q = " ".join(words[:8])
    return q.strip()


async def scrape_item(agent, title: str, category: str, item_key: str) -> list[dict]:
    """Call MarketplaceAgent for a single item, return market_hit dicts."""
    query = simplify_query(title, category)
    try:
        result = await asyncio.wait_for(
            agent.aggregate_search(query=query, category=category, limit=10),
            timeout=30,
        )
        hits = []
        for scored_hit in result.hits:
            h = scored_hit.hit
            hits.append({
                "provider": h.get("source", "unknown"),
                "listing_id": h.get("listing_id") or h.get("url", "")[:200],
                "title": (h.get("title") or "")[:500],
                "price": h.get("price") or h.get("price_eur") or 0,
                "currency": h.get("currency", "EUR"),
                "condition": h.get("condition", ""),
                "normalized_key": item_key,
                "category": category,
            })
        return hits
    except asyncio.TimeoutError:
        logger.warning("  timeout for '%s'", title[:50])
        return []
    except Exception as e:
        logger.warning("  error for '%s': %s", title[:50], e)
        return []


async def write_hits_to_db(conn, hits: list[dict]) -> int:
    """Batch-insert market_hits via direct asyncpg (not PostgREST)."""
    if not hits:
        return 0
    count = 0
    for h in hits:
        try:
            await conn.execute("""
                INSERT INTO public.market_hits
                    (provider, listing_id, title, price, currency, condition,
                     normalized_key, category, item_ref)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $7)
            """,
                h["provider"], h["listing_id"], h["title"],
                float(h["price"]) if h["price"] else 0,
                h["currency"], h["condition"],
                h["normalized_key"], h["category"],
            )
            count += 1
        except Exception as e:
            logger.debug("  hit insert failed: %s", e)
    return count


async def main_async(args):
    import asyncpg
    from app.agents.marketplace_agent import MarketplaceAgent

    dsn = os.environ.get("DB_DSN")
    if not dsn:
        logger.error("DB_DSN not set")
        return

    conn = await asyncpg.connect(dsn, timeout=10)
    logger.info("Connected to DB")

    categories = await get_categories_needing_scrape(conn, args.category, args.all)
    if not categories:
        logger.info("No categories need seeding")
        await conn.close()
        return

    logger.info("Categories to scrape (%d): %s", len(categories), ", ".join(categories))

    if args.dry_run:
        for cat in categories:
            items = await get_sample_items(conn, cat, args.items_per_category)
            logger.info("  %s: %d items to scrape", cat, len(items))
            for item in items[:3]:
                logger.info("    • %s", item["title"][:60])
        await conn.close()
        return

    agent = MarketplaceAgent()
    total_hits = 0
    total_items_scraped = 0

    try:
        for cat_idx, cat in enumerate(categories, 1):
            items = await get_sample_items(conn, cat, args.items_per_category)
            if not items:
                logger.info("[%d/%d] %s: no catalog items to scrape", cat_idx, len(categories), cat)
                continue

            logger.info("[%d/%d] %s: scraping %d items...", cat_idx, len(categories), cat, len(items))
            cat_hits = 0

            for i, item in enumerate(items, 1):
                hits = await scrape_item(agent, item["title"], cat, item["item_key"])
                if hits:
                    written = await write_hits_to_db(conn, hits)
                    cat_hits += written
                    total_hits += written
                    logger.info("  [%d/%d] %s → %d hits", i, len(items), item["title"][:40], written)
                else:
                    logger.info("  [%d/%d] %s → 0 hits", i, len(items), item["title"][:40])

                total_items_scraped += 1

                # Brief pause to avoid hammering APIs
                if i < len(items):
                    await asyncio.sleep(1)

            logger.info("  %s complete: %d market_hits written", cat, cat_hits)

    finally:
        await agent.close()

    await conn.close()

    logger.info("")
    logger.info("=== Seed scrape complete ===")
    logger.info("  Categories scraped: %d", len(categories))
    logger.info("  Items queried:      %d", total_items_scraped)
    logger.info("  Market hits written: %d", total_hits)
    logger.info("")
    logger.info("Next: the valuation_worker will pick up these hits on its next cycle")
    logger.info("and compute fresh q10/q50/q90 predictions.")


def main():
    parser = argparse.ArgumentParser(description="Seed scrape — fetch live marketplace prices")
    parser.add_argument("--all", action="store_true", help="scrape ALL categories (not just Tier 1)")
    parser.add_argument("--category", type=str, help="scrape a single category")
    parser.add_argument("--items-per-category", type=int, default=15, help="items to scrape per category (default: 15)")
    parser.add_argument("--dry-run", action="store_true", help="show what would be scraped without actually scraping")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
