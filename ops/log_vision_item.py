#!/usr/bin/env python3
import asyncio
import logging
import os
import sys

import asyncpg

logger = logging.getLogger(__name__)


async def main():
    if len(sys.argv) < 2:
        logger.error("Usage: log_vision_item.py \"item description\"")
        return

    item_ref = sys.argv[1]
    dsn = os.environ.get("DB_DSN")
    if not dsn:
        logger.error("DB_DSN not set")
        return

    conn = await asyncpg.connect(dsn)
    await conn.execute(
        "INSERT INTO public.vision_predict_log (item_ref) VALUES ($1)",
        item_ref,
    )
    await conn.close()
    logger.info("logged vision item_ref=%s", item_ref)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
