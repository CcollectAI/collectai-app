#!/usr/bin/env python3
import asyncio
import logging
import os
import sys
from decimal import Decimal

import asyncpg

logger = logging.getLogger(__name__)


async def main():
    if len(sys.argv) < 3:
        logger.error("Usage: log_market_hit.py \"item_ref\" price_in_eur")
        return

    item_ref = sys.argv[1]
    price = Decimal(sys.argv[2])

    dsn = os.environ.get("DB_DSN")
    if not dsn:
        logger.error("DB_DSN not set")
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
    logger.info("logged market hit item_ref=%s price=%s", item_ref, price)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
