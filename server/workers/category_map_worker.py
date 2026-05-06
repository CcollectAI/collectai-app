#!/usr/bin/env python3
import os, asyncio, logging
import asyncpg

from app.worker_registry import record_run

logging.basicConfig(level=logging.INFO, format="%(asctime)s [category_map] %(levelname)s: %(message)s")

DSN = os.environ.get("DB_DSN")

LABEL_TO_SLUG = {
    "funko pop": "funko_pop",
    "pokemon card": "pokemon_card",
    "diecast car": "diecast_car",
}

async def run_once():
    if not DSN:
        logging.error("DB_DSN not set")
        record_run("category_map_worker", "error")
        return

    # Tagged via application_name for the ExecStop cancel hook.
    conn = await asyncpg.connect(
        DSN,
        server_settings={"application_name": "collectai-bake-category_map_worker"},
    )

    try:
        rows = await conn.fetch("""
            SELECT v.item_ref, v.predicted_label
            FROM public.v_vision_latest v
            WHERE v.predicted_label IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM public.collectai_item_categories c
                  WHERE c.item_ref = v.item_ref
              )
            ORDER BY v.created_at DESC
            LIMIT 50;
        """)

        if not rows:
            logging.info("No unmapped items")
            return

        logging.info("Found %d unmapped items", len(rows))

        for r in rows:
            ref = r["item_ref"]
            label = (r["predicted_label"] or "").strip().lower()
            slug = LABEL_TO_SLUG.get(label)
            if not slug:
                logging.info("No slug mapping for label=%r (item_ref=%r)", label, ref)
                continue

            cat = await conn.fetchrow(
                "SELECT id FROM public.collectai_category_taxonomy WHERE slug = $1",
                slug,
            )
            if not cat:
                logging.info("No taxonomy row for slug=%r", slug)
                continue

            cat_id = cat["id"]

            await conn.execute(
                """
                INSERT INTO public.collectai_item_categories (item_ref, category_id)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
                """,
                ref,
                cat_id,
            )
            logging.info("Mapped %r -> %s (category_id=%s)", ref, slug, cat_id)

        logging.info("category_map cycle done")
    finally:
        await conn.close()
        record_run("category_map_worker", "ok")

async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("category_map_worker", "error")
        logging.exception("category_map crashed: %r", e)

if __name__ == "__main__":
    asyncio.run(main())
