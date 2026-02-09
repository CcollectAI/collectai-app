#!/usr/bin/env python3
import os, asyncio, logging
import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [signal_alerts] %(levelname)s: %(message)s")

DSN = os.environ.get("DB_DSN")

THRESH_LOW = 15.0  # EUR; tune later

async def run_once():
    if not DSN:
        logging.error("DB_DSN not set")
        return

    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch("""
            SELECT item_ref, vision_label, vision_score, q10, q50, q90, valuation_at
            FROM public.v_item_signal
            WHERE q50 IS NOT NULL
            ORDER BY valuation_at DESC
            LIMIT 50;
        """)

        if not rows:
            logging.info("No valuation signals to check")
            return

        for r in rows:
            ref = r["item_ref"]
            label = r["vision_label"]
            mid = r["q50"]

            if mid is None:
                continue

            if float(mid) < THRESH_LOW:
                msg = f"Low valuation: {ref} ({label}) at {mid} EUR"
                logging.info("ALERT low_value: %s", msg)

                # insert alerts only if at least one user exists
                await conn.execute("""
                    INSERT INTO public.alerts (
                        user_id,
                        query,
                        max_price,
                        marketplaces,
                        active,
                        item_ref,
                        alert_type,
                        message
                    )
                    SELECT
                        u.id,
                        'auto_low_value_signal',
                        NULL,
                        '{}'::text[],
                        true,
                        $1,
                        'low_value',
                        $2
                    FROM public.users u
                    ORDER BY u.id
                    LIMIT 1
                """, ref, msg)

        logging.info("signal_alerts cycle done")
    finally:
        await conn.close()

async def main():
    try:
        await run_once()
    except Exception as e:
        logging.exception("signal_alerts crashed: %r", e)

if __name__ == "__main__":
    asyncio.run(main())
