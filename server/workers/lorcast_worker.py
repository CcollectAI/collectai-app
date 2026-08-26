"""Lorcast → lorcana catalogue + prices, on the DIRECT DSN.

WHY THIS IS A WORKER AND NOT A SCRIPT (2026-08-26)
--------------------------------------------------
It was a script, run by hand exactly once — 2026-08-15 12:09:26 to 12:09:28.
Nothing refreshed it afterwards, and lorcana therefore had two dated deaths
queued up:

  2026-09-14  the comps leave the watchdog canary's 30-day sold-comp window
              and lorcana flips to "sold-comp source DIED" — a true sentence
              about a source that was never alive
  ~2026-10-01 `market_hits_y2026m08` is dropped (retention is ONE MONTH:
              PARTITION_RETENTION_MONTHS_MARKET_HITS=1, PARTITION_DROP_ENABLED
              =true), taking every lorcana comp with it and returning the
              category to 0% priceable

Recovering the 5,420 stranded comps on 2026-08-26 fixed the plumbing. It did
not make lorcana a SOURCED category. This worker does.

WHY THE DIRECT DSN, NOT THE PIPELINE'S PostgREST PATH
-----------------------------------------------------
`pipelines/import_lorcana.py::main()` writes through `SupabaseIngest`, i.e.
PostgREST over HTTP, which inherits the pooler's 30s statement timeout — 11
batches attempted, 0 written. That was blamed on a Micro instance and the DB
has since moved to Small, so the excuse may well have expired; it does not
matter. `docs/DATA_SCALING_PLAN.md` §6 rule 6 is the standing rule and it
points the other way:

    "Worker processes doing bulk inserts use a separate direct-connection DSN
     (port 5432 session mode) so they can't get guillotined mid-upsert."

So the direct DSN is not a workaround here, it is the documented pattern.

The transform is NOT duplicated: `fetch_all_cards` and the two mappers are
imported from the pipeline, so this module and the pipeline cannot drift.
`scripts/load_lorcana_direct.py` is a thin CLI over this same `run_once`.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Matches the batch the hand-run loader used and wrote 2,847 + 5,420 rows with.
_BATCH = 200

# Generous, but bounded. The point is to survive a cold-cache index probe, not
# to let a runaway statement sit on the instance forever.
_STATEMENT_TIMEOUT = "180s"


async def run_once(batch: int = _BATCH) -> dict[str, Any]:
    """Refresh the lorcana catalogue and its Lorcast price rows.

    Raises rather than returning a falsy summary. `bake_orchestrator` records
    `metadata.error_repr` from the exception, and docs/WATCHDOG.md's rule is
    that a failing worker must say WHY — a swallowed failure here would read as
    a category that simply stopped having prices.
    """
    dsn = os.getenv("DB_DSN_DIRECT") or os.getenv("DB_DSN")
    if not dsn:
        raise RuntimeError("lorcast: DB_DSN_DIRECT/DB_DSN not set")

    from pipelines.import_lorcana import (
        fetch_all_cards, card_to_catalog_item, card_to_market_hits, CATEGORY,
    )

    # `fetch_all_cards` is SYNCHRONOUS (urllib inside `fetch_json`), one HTTP
    # round trip per set. Calling it directly would block the bake's event loop
    # for the whole fetch, stalling every other worker and the API this process
    # also serves. It raises on an empty set list rather than falling back to
    # curated data, which is the behaviour that hid this importer being broken
    # for weeks — keep it.
    cards = await asyncio.to_thread(fetch_all_cards)

    items, seen = [], set()
    for c in cards:
        it = card_to_catalog_item(c)
        if it.item_key not in seen:
            seen.add(it.item_key)
            items.append(it)
    hits = [h for c in cards for h in card_to_market_hits(c)]
    logger.info("[lorcast] fetched %d cards -> %d catalogue rows, %d price rows",
                len(cards), len(items), len(hits))

    if not items:
        raise RuntimeError(
            "lorcast: fetch returned %d cards but 0 catalogue rows — the "
            "mapper dropped everything" % len(cards)
        )

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SET statement_timeout = '%s'" % _STATEMENT_TIMEOUT)

        cat_written = 0
        for i in range(0, len(items), batch):
            chunk = items[i:i + batch]
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

        # IDEMPOTENT BY CONSTRUCTION, because ON CONFLICT cannot be.
        #
        # market_hits' primary key is (id, seen_at) with a GENERATED id, so
        # `ON CONFLICT DO NOTHING` never fires — re-running simply inserts a
        # second copy of every row. That is exactly what happened when the
        # first load was interrupted by a compute resize: 8,420 rows where
        # 5,420 were expected, and 3,000 had to be deleted by hand.
        #
        # Clearing this provider's rows for today first makes a re-run converge
        # instead of accumulate. Scoped to provider + day so it can never touch
        # eBay/tcgplayer hits or any earlier day's history — which matters more
        # now that this runs daily than it did for a one-shot.
        await conn.execute(
            """
            DELETE FROM public.market_hits
            WHERE provider = 'lorcast' AND seen_at::date = current_date
            """
        )

        hit_written = 0
        for i in range(0, len(hits), batch):
            chunk = hits[i:i + batch]
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
                -- `price_eur` the EUR normalisation (marketplace_agent.py:887
                -- binds raw_price / raw_currency / price_eur in that order);
                -- 1,958 USD rows in the last 30 days genuinely differ. They
                -- coincide here only because the Lorcast mapper already
                -- converts, so `currency` is always EUR.
                --
                -- Filling ONLY price_eur is what the 2026-08-15 hand-run did,
                -- and it lost all 5,420 rows: valuation_worker's queue filter
                -- is `price IS NOT NULL` (mirroring the partial index
                -- idx_market_hits_valuation_queue) while its SELECT list is
                -- COALESCE(price_eur, price). A row with only price_eur is
                -- usable and permanently invisible.
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

        # POST-WRITE ASSERTION, at the writer. docs/DATA_SCALING_PLAN.md §10:
        # "every kwarg a writer accepts should have a CI test asserting the
        # resulting row has that column populated". The defect this worker
        # exists to stop leaves NO error behind — the rows land, and valuation
        # silently never sees them — so the only place to catch it is here,
        # against what was actually written.
        invisible = await conn.fetchval(
            """
            SELECT count(*) FROM public.market_hits
             WHERE provider = 'lorcast'
               AND seen_at::date = current_date
               AND price IS NULL
               AND price_eur IS NOT NULL
            """
        )
        if invisible:
            raise RuntimeError(
                "lorcast wrote %d rows this cycle that valuation_worker cannot "
                "see (price NULL, price_eur set) — the INSERT column list has "
                "regressed" % invisible
            )

        logger.info("[lorcast] DONE: %d catalogue rows, %d price rows",
                    cat_written, hit_written)
        return {"ok": True, "catalog_rows": cat_written, "price_rows": hit_written,
                "cards": len(cards)}
    finally:
        await conn.close()
