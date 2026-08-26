#!/usr/bin/env python3
"""Load the Lorcana catalogue + prices over the DIRECT DSN.

WHY THIS EXISTS
---------------
`pipelines/import_lorcana.py` writes through `SupabaseIngest`, i.e. PostgREST
over HTTP, which inherits the pooler's 30s statement timeout. On a Micro
instance whose cache (224MB) is a twentieth of the database, a 200-row upsert
into `category_items` (253MB, 128MB of indexes) exceeds that and every batch
dies with 57014 — 11 batches attempted, 0 written.

Nothing about the DATA is large: 2,847 catalogue rows and ~5,400 price rows.
This bypasses the HTTP layer and writes with asyncpg on DB_DSN_DIRECT, which
allows a longer statement_timeout, in small transactions.

It imports the pipeline's OWN fetch and mappers — no second copy of the
Lorcast transform, so the two cannot drift.

Usage:  python3 server/scripts/load_lorcana_direct.py [--batch 200]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

import asyncpg

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [load_lorcana] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=200)
    args = ap.parse_args()

    dsn = os.getenv("DB_DSN_DIRECT") or os.getenv("DB_DSN")
    if not dsn:
        logger.error("DB_DSN_DIRECT not set")
        return 2

    from pipelines.import_lorcana import (
        fetch_all_cards, card_to_catalog_item, card_to_market_hits, CATEGORY,
    )

    cards = fetch_all_cards()
    items, seen = [], set()
    for c in cards:
        it = card_to_catalog_item(c)
        if it.item_key not in seen:
            seen.add(it.item_key)
            items.append(it)
    hits = [h for c in cards for h in card_to_market_hits(c)]
    logger.info("fetched %d cards -> %d catalogue rows, %d price rows",
                len(cards), len(items), len(hits))

    conn = await asyncpg.connect(dsn)
    try:
        # Generous, but bounded. The point is to survive a cold-cache index
        # probe, not to let a runaway statement sit on the instance forever.
        await conn.execute("SET statement_timeout = '180s'")

        cat_written = 0
        for i in range(0, len(items), args.batch):
            chunk = items[i:i + args.batch]
            await conn.executemany(
                """
                INSERT INTO public.category_items
                    (category, item_key, title, brand, set_code, rarity, notes,
                     image_url, source, verified)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'lorcast',false)
                ON CONFLICT (category, item_key) DO UPDATE SET
                    title = EXCLUDED.title,
                    image_url = COALESCE(NULLIF(EXCLUDED.image_url,''), category_items.image_url),
                    rarity = EXCLUDED.rarity,
                    updated_at = now()
                """,
                [(CATEGORY, it.item_key, it.title, it.brand, it.set_code,
                  it.rarity, it.notes, it.image_url) for it in chunk],
            )
            cat_written += len(chunk)
            logger.info("  catalogue %d/%d", cat_written, len(items))

        # IDEMPOTENT BY CONSTRUCTION, because ON CONFLICT cannot be.
        #
        # market_hits' primary key is (id, seen_at) with a GENERATED id, so
        # `ON CONFLICT DO NOTHING` never fires — re-running simply inserts a
        # second copy of every row. That is exactly what happened when the
        # first load was interrupted by a compute resize: 8,420 rows where
        # 5,420 were expected, and 3,000 had to be deleted by hand afterwards.
        #
        # Clearing this provider's rows for today first makes a re-run
        # converge instead of accumulate. Scoped to provider + day so it can
        # never touch eBay/tcgplayer hits or any earlier day's history.
        cleared = await conn.execute(
            """
            DELETE FROM public.market_hits
            WHERE provider = 'lorcast' AND seen_at::date = current_date
            """
        )
        logger.info("cleared today's lorcast rows before reload: %s", cleared)

        hit_written = 0
        for i in range(0, len(hits), args.batch):
            chunk = hits[i:i + args.batch]
            await conn.executemany(
                """
                -- NO sold_at column on this table: `is_listing` is set directly
                -- by the writer. FALSE is the whole point — valuation_worker
                -- excludes is_listing, so a price guide filed as a listing is
                -- collected and then thrown away, which is exactly why lorcana
                -- had 17k eBay rows and zero predictions.
                --
                -- BOTH price columns, and they are not one column written
                -- twice. `price` is the price in its ORIGINAL currency and
                -- `price_eur` the EUR normalisation — marketplace_agent.py:887
                -- binds raw_price / raw_currency / price_eur in exactly that
                -- order, and 1,958 USD rows in the last 30 days really do have
                -- price <> price_eur. They coincide here only because the
                -- Lorcast mapper already converts, so `currency` is always EUR.
                --
                -- Filling ONLY price_eur is what the 2026-08-15 run did, and it
                -- lost all 5,420 rows: valuation_worker's queue filter is
                -- `price IS NOT NULL` (mirroring the partial index
                -- idx_market_hits_valuation_queue) while its SELECT list is
                -- `COALESCE(price_eur, price)`. A row with only price_eur is
                -- perfectly usable and permanently invisible — lorcana sat at
                -- processed=false with ZERO price_predictions for 11 days,
                -- which the watchdog reported as a crosswalk fault. Same shape
                -- as the is_listing bug this comment already warns about, one
                -- column to the left. docs/DATA_SCALING_PLAN.md §10 "Writer
                -- bugs hide in INSERT column lists" is the standing rule.
                INSERT INTO public.market_hits
                    (provider, listing_id, title, price, price_eur, currency,
                     condition, item_ref, normalized_key, category, seen_at,
                     is_listing)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10, now(), false)
                ON CONFLICT DO NOTHING
                """,
                [(h.provider, h.listing_id, h.title, h.price, h.price, h.currency,
                  h.condition, f"{CATEGORY}:{h.normalized_key}", h.normalized_key,
                  CATEGORY) for h in chunk],
            )
            hit_written += len(chunk)
            logger.info("  prices %d/%d", hit_written, len(hits))

        logger.info("DONE: %d catalogue rows, %d price rows", cat_written, hit_written)
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
