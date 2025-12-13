#!/usr/bin/env python3
import os, asyncio, sys
import asyncpg

async def main():
    if len(sys.argv) < 2:
        print("Usage: log_vision_item.py \"item description\"")
        return

    item_ref = sys.argv[1]
    dsn = os.environ.get("DB_DSN")
    if not dsn:
        print("DB_DSN not set")
        return

    conn = await asyncpg.connect(dsn)
    await conn.execute(
        "INSERT INTO public.vision_predict_log (item_ref) VALUES ($1)",
        item_ref,
    )
    await conn.close()
    print(f"logged vision item_ref={item_ref}")

if __name__ == "__main__":
    asyncio.run(main())
