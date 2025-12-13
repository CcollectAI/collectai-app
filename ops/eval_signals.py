#!/usr/bin/env python3
import os, asyncio
import asyncpg

DSN = os.environ.get("DB_DSN")

async def main():
    if not DSN:
        print("DB_DSN not set")
        return

    conn = await asyncpg.connect(DSN)

    print("== Latest items (vision + valuation + category) ==")
    rows = await conn.fetch("""
        SELECT item_ref,
               vision_label,
               vision_score,
               q10, q50, q90,
               category_slug,
               category_name,
               vision_at,
               valuation_at
        FROM public.v_item_signal_with_category
        ORDER BY vision_at DESC
        LIMIT 20;
    """)
    for r in rows:
        print(f"- {r['item_ref']!r}")
        print(f"    label={r['vision_label']}, score={r['vision_score']}")
        print(f"    q10={r['q10']} q50={r['q50']} q90={r['q90']}")
        print(f"    category={r['category_slug']} ({r['category_name']})")
        print(f"    vision_at={r['vision_at']} valuation_at={r['valuation_at']}")
        print()

    print("\n== Category-level aggregates ==")
    agg_rows = await conn.fetch("""
        SELECT category_slug,
               category_name,
               item_count,
               avg_mid_price,
               min_mid_price,
               max_mid_price
        FROM public.v_category_valuation
        ORDER BY category_name NULLS LAST;
    """)
    for a in agg_rows:
        print(f"- {a['category_name']} ({a['category_slug']})")
        print(f"    items={a['item_count']}, avg={a['avg_mid_price']},"
              f" min={a['min_mid_price']}, max={a['max_mid_price']}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
