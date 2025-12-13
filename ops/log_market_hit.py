#!/usr/bin/env python3
import os, asyncio, sys
import asyncpg
from decimal import Decimal
from datetime import datetime

async def main():
    if len(sys.argv) < 3:
        print("Usage: log_market_hit.py \"item_ref\" price_in_eur")
        return

    item_ref = sys.argv[1]
    price = Decimal(sys.argv[2])

    dsn = os.environ.get("DB_DSN")
    if not dsn:
        print("DB_DSN not set")
        return

    conn = await asyncpg.connect(dsn)
    await conn.execute(
        """
        INSERT INTO public.market_hits (item_ref, source, price, currency, observed_at, processed)
        VALUES ($1, 'manual_cli', $2, 'EUR', now(), false)
        """,
        item_ref,
        price,
    )
    await conn.close()
    print(f"logged market hit item_ref={item_ref} price={price}")

if __name__ == "__main__":
    asyncio.run(main())
