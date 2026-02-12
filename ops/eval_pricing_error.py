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

    logger.info("== Per-item pricing error (latest sales) ==")
    rows = await conn.fetch("""
        SELECT owner_tag,
               item_ref,
               actual_sale_price_eur,
               q50,
               abs_error_eur,
               rel_error,
               sold_at,
               prediction_at
        FROM public.v_eval_item_error
        ORDER BY sold_at DESC
        LIMIT 50;
    """)
    if not rows:
        logger.info("  (no ground truth sales yet)")
    for r in rows:
        rel_pct = "%.1f%%" % (float(r['rel_error']) * 100) if r["rel_error"] is not None else "n/a"
        logger.info("- %r", r['item_ref'])
        logger.info("    actual=%s q50=%s", r['actual_sale_price_eur'], r['q50'])
        logger.info("    abs_err=%s rel_err=%s", r['abs_error_eur'], rel_pct)
        logger.info("    sold_at=%s prediction_at=%s", r['sold_at'], r['prediction_at'])

    logger.info("")
    logger.info("== Per-category error ==")
    cats = await conn.fetch("""
        SELECT category_name,
               category_slug,
               n_items,
               avg_abs_error_eur,
               avg_abs_rel_error,
               min_rel_error,
               max_rel_error
        FROM public.v_eval_category_error
        ORDER BY category_name NULLS LAST;
    """)
    if not cats:
        logger.info("  (no category eval yet)")
    for c in cats:
        avg_rel = "%.1f%%" % (float(c['avg_abs_rel_error']) * 100) if c["avg_abs_rel_error"] is not None else "n/a"
        logger.info("- %s (%s)", c['category_name'], c['category_slug'])
        logger.info("    n_items=%s", c['n_items'])
        logger.info("    avg_abs_err=%s", c['avg_abs_error_eur'])
        logger.info("    avg_abs_rel_err=%s", avg_rel)

    await conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
