#!/usr/bin/env python3
import os, asyncio
import asyncpg

DSN = os.environ.get("DB_DSN")

async def main():
    if not DSN:
        print("DB_DSN not set")
        return

    conn = await asyncpg.connect(DSN)

    print("== Per-item pricing error (latest sales) ==")
    rows = await conn.fetch("""
        SELECT owner_tag,
               item_ref,
               actual_sale_price_eur,
               q50,
               abs_error_eur,
               rel_error,
               sold_at,
               prediction_at
        FROM public.v_eval_item_error
        ORDER BY sold_at DESC
        LIMIT 50;
    """)
    if not rows:
        print("  (no ground truth sales yet)")
    for r in rows:
        rel_pct = f"{float(r['rel_error'])*100:.1f}%" if r["rel_error"] is not None else "n/a"
        print(f"- {r['item_ref']!r}")
        print(f"    actual={r['actual_sale_price_eur']} q50={r['q50']}")
        print(f"    abs_err={r['abs_error_eur']} rel_err={rel_pct}")
        print(f"    sold_at={r['sold_at']} prediction_at={r['prediction_at']}")
        print()

    print("\n== Per-category error ==")
    cats = await conn.fetch("""
        SELECT category_name,
               category_slug,
               n_items,
               avg_abs_error_eur,
               avg_abs_rel_error,
               min_rel_error,
               max_rel_error
        FROM public.v_eval_category_error
        ORDER BY category_name NULLS LAST;
    """)
    if not cats:
        print("  (no category eval yet)")
    for c in cats:
        avg_rel = f"{float(c['avg_abs_rel_error'])*100:.1f}%" if c["avg_abs_rel_error"] is not None else "n/a"
        print(f"- {c['category_name']} ({c['category_slug']})")
        print(f"    n_items={c['n_items']}")
        print(f"    avg_abs_err={c['avg_abs_error_eur']}")
        print(f"    avg_abs_rel_err={avg_rel}")
        print()

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
