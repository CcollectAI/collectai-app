import asyncio
import glob
import logging
import os

import asyncpg

logger = logging.getLogger(__name__)

DB_ENABLED = os.getenv("DB_ENABLED", "false").lower() == "true"
DATABASE_URL = os.getenv("DATABASE_URL", "")


async def run():
    if not DB_ENABLED or not DATABASE_URL:
        logger.info("skipped (DB_ENABLED=false or DATABASE_URL empty)")
        return
    conn = await asyncpg.connect(DATABASE_URL, timeout=8)
    try:
        files = sorted(glob.glob("migrations/*.sql"))
        for f in files:
            with open(f, encoding="utf-8") as fh:
                sql = fh.read()
            logger.info("applying %s ...", f)
            await conn.execute(sql)
        logger.info("migrations applied")
    finally:
        await conn.close()


asyncio.run(run())
