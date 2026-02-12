#!/usr/bin/env python3
import asyncio
import logging
import os

import asyncpg

logger = logging.getLogger(__name__)

DSN = os.environ.get("DB_DSN")


async def main():
    if not DSN:
        logger.error("DB_DSN not set")
        return

    conn = await asyncpg.connect(DSN)

    logger.info("== Latest items (vision + valuation + category) ==")
    rows = await conn.fetch("""
        SELECT item_ref,
               vision_label,
               vision_score,
               q10, q50, q90,
               category_slug,
               category_name,
               vision_at,
               valuation_at
        FROM public.v_item_signal_with_category
        ORDER BY vision_at DESC
        LIMIT 20;
    """)
    for r in rows:
        logger.info("- %r", r['item_ref'])
        logger.info("    label=%s, score=%s", r['vision_label'], r['vision_score'])
        logger.info("    q10=%s q50=%s q90=%s", r['q10'], r['q50'], r['q90'])
        logger.info("    category=%s (%s)", r['category_slug'], r['category_name'])
        logger.info("    vision_at=%s valuation_at=%s", r['vision_at'], r['valuation_at'])

    logger.info("")
    logger.info("== Category-level aggregates ==")
    agg_rows = await conn.fetch("""
        SELECT category_slug,
               category_name,
               item_count,
               avg_mid_price,
               min_mid_price,
               max_mid_price
        FROM public.v_category_valuation
        ORDER BY category_name NULLS LAST;
    """)
    for a in agg_rows:
        logger.info("- %s (%s)", a['category_name'], a['category_slug'])
        logger.info("    items=%s, avg=%s, min=%s, max=%s",
                     a['item_count'], a['avg_mid_price'],
                     a['min_mid_price'], a['max_mid_price'])

    await conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
