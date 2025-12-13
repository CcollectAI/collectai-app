#!/usr/bin/env python3
import os, asyncio, sys, csv
from decimal import Decimal
import asyncpg

DSN = os.environ.get("DB_DSN")

async def main():
    if len(sys.argv) < 2:
        print("Usage: bulk_seed_from_csv.py path/to/file.csv")
        return

    if not DSN:
        print("DB_DSN not set")
        return

    path = sys.argv[1]
    conn = await asyncpg.connect(DSN)

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item_ref = row["item_ref"].strip()
            price_eur = Decimal(row["price_eur"])
            category_slug = (row.get("category_slug") or "").strip() or None

            # 1) vision log
            await conn.execute(
                """
                INSERT INTO public.vision_predict_log (item_ref)
                VALUES ($1)
                ON CONFLICT DO NOTHING
                """,
                item_ref,
            )

            # 2) market hit
            await conn.execute(
                """
                INSERT INTO public.market_hits (item_ref, source, price, currency, observed_at, processed)
                VALUES ($1, 'bulk_seed', $2, 'EUR', now(), false)
                """,
                item_ref,
                price_eur,
            )

            # 3) optional category assignment if slug provided
            if category_slug:
                cat = await conn.fetchrow(
                    "SELECT id FROM public.collectai_category_taxonomy WHERE slug = $1",
                    category_slug,
                )
                if cat:
                    await conn.execute(
                        """
                        INSERT INTO public.collectai_item_categories (item_ref, category_id)
                        VALUES ($1, $2)
                        ON CONFLICT DO NOTHING
                        """,
                        item_ref,
                        cat["id"],
                    )

            print(f"seeded item_ref={item_ref}, price={price_eur}, category={category_slug}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
