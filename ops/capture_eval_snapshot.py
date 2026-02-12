#!/usr/bin/env python3
import os, asyncio, json, logging
from decimal import Decimal
from datetime import datetime, date
import asyncpg

logger = logging.getLogger(__name__)

DSN = os.environ.get("DB_DSN")

def to_jsonable_row(row: dict):
    out = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out

async def main():
    if not DSN:
        logger.error("DB_DSN not set")
        return

    conn = await asyncpg.connect(DSN)

    # 1) global stats
    global_row = await conn.fetchrow("""
        SELECT
            COUNT(*) AS n_items,
            AVG(abs_error_eur) AS avg_abs_error_eur,
            AVG(ABS(rel_error)) AS avg_abs_rel_error
        FROM public.v_eval_item_error;
    """)

    # 2) per-category stats
    cat_rows = await conn.fetch("""
        SELECT
            category_name,
            category_slug,
            n_items,
            avg_abs_error_eur,
            avg_abs_rel_error,
            min_rel_error,
            max_rel_error
        FROM public.v_eval_category_error
        ORDER BY category_name NULLS LAST;
    """)
    per_category = [to_jsonable_row(dict(r)) for r in cat_rows]

    # 3) sample of per-item errors (for debugging)
    item_rows = await conn.fetch("""
        SELECT
            owner_tag,
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
    per_item_sample = [to_jsonable_row(dict(r)) for r in item_rows]

    # 4) insert snapshot
    await conn.execute(
        """
        INSERT INTO public.collectai_eval_snapshots (
            notes,
            n_items,
            avg_abs_error_eur,
            avg_abs_rel_error,
            per_category,
            per_item_sample
        )
        VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
        """,
        "auto snapshot",
        global_row["n_items"],
        global_row["avg_abs_error_eur"],
        global_row["avg_abs_rel_error"],
        json.dumps(per_category),
        json.dumps(per_item_sample),
    )

    await conn.close()
    logger.info("Eval snapshot inserted.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
