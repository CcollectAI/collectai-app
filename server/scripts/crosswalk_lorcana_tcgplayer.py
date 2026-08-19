#!/usr/bin/env python3
"""Point the tcgcsv-derived Lorcana catalogue at the Lorcast price source.

THE PROBLEM
-----------
`lorcana` holds three keyspaces:

    tcgcsv   6,172 rows   item_key = 'tcgplayer:<product_id>:<variant>'
    lorcast  2,847 rows   item_key = '<set>-<number>'        (has prices)
    seed       795 rows   item_key = '<set>-<name-slug>'

Only the lorcast rows are priceable, because they were derived from the same
source that produces the prices. The tcgcsv rows are the ones users actually
hold — 3 of the 5 real lorcana items in the app sit on tcgcsv keys — so leaving
them unpriceable means those members see nothing.

WHY THIS IS NOT THE MATCHER THAT WAS REJECTED
---------------------------------------------
docs/DATA_SCALING_PLAN.md records that name-based crosswalking was measured for
lorcana and rejected: 224 of 226 ambiguous, 0/795 with a set tiebreak, because
the two side's set vocabularies barely overlap. **This is not that.** The tcgcsv
key literally contains the TCGplayer product id, and Lorcast publishes
`tcgplayer_id` per card. It is an exact integer join with nothing to score and
no tie to break. A row either has a matching id or it is skipped.

VARIANTS ARE RESPECTED
----------------------
`tcgplayer:<id>:cold_foil` maps to the card's FOIL ref, not its base ref. On
Lorcana that difference is not cosmetic — P1 promos run to $1,250 foil against
no base price at all — and collapsing them was the "per card, not per printing"
error the yugioh passcode crosswalk was retired for.

Usage:  python3 server/scripts/crosswalk_lorcana_tcgplayer.py [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys

import asyncpg

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [xwalk_lorcana] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

CATEGORY = "lorcana"
# tcgplayer:<product_id>:<variant>
_KEY = re.compile(r"^tcgplayer:(\d+):(.+)$")
# Which tcgcsv variants mean "foil" on Lorcana.
_FOIL_VARIANTS = {"cold_foil", "holofoil", "foil", "rainbow_foil", "enchanted"}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    dsn = os.getenv("DB_DSN_DIRECT") or os.getenv("DB_DSN")
    if not dsn:
        logger.error("DB_DSN_DIRECT not set")
        return 2

    from pipelines.import_lorcana import fetch_all_cards, card_to_catalog_item

    # id -> (base_ref, has_foil_price)
    by_tcg: dict[int, tuple[str, bool]] = {}
    for c in fetch_all_cards():
        tid = c.get("tcgplayer_id")
        if not tid:
            continue
        base = card_to_catalog_item(c).item_key
        by_tcg[int(tid)] = (base, bool(c.get("price_eur_foil")))
    logger.info("Lorcast cards carrying a tcgplayer_id: %d", len(by_tcg))

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SET statement_timeout = '240s'")
        rows = await conn.fetch(
            """
            SELECT item_key FROM public.category_items
            WHERE category = $1 AND source = 'tcgcsv'
            """, CATEGORY)
        logger.info("tcgcsv rows to map: %d", len(rows))

        mapped, unmatched, unparsed = [], 0, 0
        for r in rows:
            key = r["item_key"]
            m = _KEY.match(key)
            if not m:
                unparsed += 1
                continue
            tid, variant = int(m.group(1)), m.group(2)
            hit = by_tcg.get(tid)
            if not hit:
                unmatched += 1
                continue
            base, has_foil = hit
            want_foil = variant in _FOIL_VARIANTS
            ref = f"{CATEGORY}:{base}-foil" if (want_foil and has_foil) else f"{CATEGORY}:{base}"
            mapped.append((CATEGORY, key, ref,
                           "tcgplayer_id_foil" if (want_foil and has_foil) else "tcgplayer_id",
                           1.0))

        logger.info("matched %d / %d  (unmatched id %d, unparsable key %d)",
                    len(mapped), len(rows), unmatched, unparsed)
        if args.dry_run:
            for row in mapped[:5]:
                logger.info("  would map %s -> %s (%s)", row[1], row[2], row[3])
            return 0

        for i in range(0, len(mapped), 500):
            await conn.executemany(
                """
                INSERT INTO public.catalog_price_refs
                    (category, item_key, price_ref, method, confidence, updated_at)
                VALUES ($1,$2,$3,$4,$5, now())
                ON CONFLICT (category, item_key) DO UPDATE SET
                    price_ref = EXCLUDED.price_ref,
                    method    = EXCLUDED.method,
                    confidence= EXCLUDED.confidence,
                    updated_at= now()
                """, mapped[i:i + 500])
            logger.info("  written %d/%d", min(i + 500, len(mapped)), len(mapped))

        logger.info("DONE: %d crosswalk rows", len(mapped))
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
