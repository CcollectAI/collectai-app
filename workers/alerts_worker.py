#!/usr/bin/env python3
import os, asyncio, logging
import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [alerts_worker] %(levelname)s: %(message)s")
DSN = os.getenv("DB_DSN")

async def run_once():
    if not DSN:
        logging.error("No DB_DSN env")
        return

    conn = await asyncpg.connect(DSN)

    rows = await conn.fetch("""
        SELECT item_ref, q10, q50, q90
        FROM public.price_predictions
        ORDER BY generated_at DESC
        LIMIT 50
    """)

    for r in rows:
        ref = r["item_ref"]
        mid = r["q50"]

        if mid is None:
            continue

        if mid < 10:
            msg = f"Low valuation alert: {ref} at {mid}"
            await conn.execute("""
                INSERT INTO public.alerts (item_ref, alert_type, message)
                VALUES ($1, 'low_value', $2)
            """, ref, msg)
            logging.info(msg)

    await conn.close()

async def main():
    try:
        await run_once()
    except Exception as e:
        logging.exception("alerts_worker crashed: %r", e)

if __name__ == "__main__":
    asyncio.run(main())
