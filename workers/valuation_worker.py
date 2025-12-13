#!/usr/bin/env python3
import os, asyncio, datetime, logging

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [valuation_worker] %(levelname)s: %(message)s")

DSN = os.getenv("DB_DSN")

async def run_once():
    if not DSN:
        logging.error("DB_DSN not set in environment")
        return

    conn = await asyncpg.connect(DSN)
    logging.info("Connected to DB")

    # Fetch unprocessed market hits grouped by item_ref
    rows = await conn.fetch("""
        SELECT item_ref, array_agg(price::numeric ORDER BY observed_at) AS prices
        FROM public.market_hits
        WHERE processed = false
        GROUP BY item_ref
    """)

    if not rows:
        logging.info("No unprocessed market_hits found")
        await conn.close()
        return

    logging.info("Found %d item_ref groups to process", len(rows))

    for r in rows:
        item_ref = r["item_ref"]
        prices = [float(p) for p in r["prices"] if p is not None]
        if not prices:
            logging.warning("No valid prices for item_ref=%s, skipping", item_ref)
            continue

        prices.sort()
        n = len(prices)

        def q(p: float) -> float:
            """simple quantile helper: p in [0,1]"""
            idx = max(0, min(n-1, int(round(p * (n - 1)))))
            return prices[idx]

        q10 = q(0.10)
        q50 = q(0.50)
        q90 = q(0.90)

        now = datetime.datetime.utcnow()

        logging.info(
            "item_ref=%s n=%d q10=%.2f q50=%.2f q90=%.2f",
            item_ref, n, q10, q50, q90
        )

        await conn.execute("""
            INSERT INTO public.price_predictions (item_ref, q10, q50, q90, generated_at)
            VALUES ($1, $2, $3, $4, $5)
        """, item_ref, q10, q50, q90, now)

        await conn.execute(
            "UPDATE public.market_hits SET processed = true WHERE item_ref = $1",
            item_ref
        )

    await conn.close()
    logging.info("Done valuation cycle")

async def main():
    try:
        await run_once()
    except Exception as e:
        logging.exception("valuation_worker crashed: %r", e)

if __name__ == "__main__":
    asyncio.run(main())
