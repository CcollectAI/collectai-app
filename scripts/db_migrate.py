import asyncio
import glob
import os

import asyncpg

DB_ENABLED = os.getenv("DB_ENABLED", "false").lower() == "true"
DATABASE_URL = os.getenv("DATABASE_URL", "")


async def run():
    if not DB_ENABLED or not DATABASE_URL:
        print("[db] skipped (DB_ENABLED=false or DATABASE_URL empty)")
        return
    conn = await asyncpg.connect(DATABASE_URL, timeout=8)
    try:
        files = sorted(glob.glob("migrations/*.sql"))
        for f in files:
            sql = open(f, encoding="utf-8").read()
            print(f"[db] applying {f} ...")
            await conn.execute(sql)
        print("[db] migrations applied")
    finally:
        await conn.close()


asyncio.run(run())
