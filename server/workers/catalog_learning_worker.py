"""
Catalog Learning Worker.

Runs periodically to:
1. Aggregate pending suggestions by fuzzy name similarity
2. Auto-map items when 3+ unique users agree on name + existing category
3. Upsert category_candidates for free-text category suggestions
4. Promote candidates to 'candidate' status at 25+ unique users in 30 days

Uses FOR UPDATE SKIP LOCKED to prevent race conditions between cycles.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.config import CATALOG_AUTO_MAP_THRESHOLD, CATALOG_NEW_CATEGORY_THRESHOLD
from app.push import send_push_to_user
from app.worker_registry import record_run

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Convert a proposed category name to a slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s_-]", "", slug)
    slug = re.sub(r"[\s-]+", "_", slug).strip("_")
    return slug[:64]


async def run_once() -> dict[str, int]:
    """Execute one cycle of catalog learning aggregation.

    Returns a dict with counts of actions taken.
    """
    # Use a direct asyncpg connection (not the pool) so we can disable
    # the pooler's 30s statement_timeout — the consensus aggregation
    # query over catalog_suggestions hits the cap on busy days. This
    # mirrors marketplace_scrape_scheduler / persist_comps_to_db.
    import os
    import asyncpg

    dsn = os.getenv("DB_DSN_DIRECT") or os.getenv("DB_DSN")
    if not dsn:
        logger.warning("[catalog-learning-worker] DB_DSN not set, skipping")
        record_run("catalog_learning_worker", "error")
        return {"auto_mapped": 0, "candidates_updated": 0, "promoted": 0}

    # Tagged via application_name for the ExecStop cancel hook.
    conn = await asyncpg.connect(
        dsn,
        server_settings={"application_name": "collectai-bake-catalog_learning_worker"},
    )
    # Bounded 2026-05-04 (was 0/unbounded). Aggregations across catalog_suggestions.
    await conn.execute("SET statement_timeout = '600s'")
    # Make the existing `pool.X` call sites work unchanged by aliasing.
    pool = conn

    auto_mapped = 0
    candidates_updated = 0
    promoted = 0

    try:
        # -------------------------------------------------------------------
        # Step 1: Auto-map — group pending suggestions where 3+ unique users
        # agree on the same name + an existing category
        # -------------------------------------------------------------------
        consensus_rows = await pool.fetch(
            """
            SELECT lower(suggested_name) AS name,
                   suggested_category,
                   count(*) AS cnt,
                   count(DISTINCT user_id) AS unique_users,
                   array_agg(DISTINCT id) AS suggestion_ids
            FROM catalog_suggestions
            WHERE status = 'pending'
              AND suggested_category IS NOT NULL
            GROUP BY lower(suggested_name), suggested_category
            HAVING count(DISTINCT user_id) >= $1
            """,
            CATALOG_AUTO_MAP_THRESHOLD,
        )

        for row in consensus_rows:
            name = row["name"]
            category = row["suggested_category"]
            suggestion_ids = row["suggestion_ids"]
            mapped_count = 0

            # Check if this category exists in the taxonomy (category_items table or known slugs)
            existing_cat = await pool.fetchval(
                """
                SELECT DISTINCT category FROM category_items
                WHERE category = $1
                LIMIT 1
                """,
                category,
            )

            if existing_cat:
                # Auto-map: update all these suggestions to 'mapped'.
                # We're on a direct asyncpg.Connection (no pool), so use
                # its transaction() directly. The original `pool.acquire()`
                # block is unnecessary here.
                if True:
                    async with conn.transaction():
                        # Lock rows to prevent concurrent updates
                        locked = await conn.fetch(
                            """
                            SELECT id FROM catalog_suggestions
                            WHERE id = ANY($1::uuid[])
                              AND status = 'pending'
                            FOR UPDATE SKIP LOCKED
                            """,
                            suggestion_ids,
                        )
                        locked_ids = [r["id"] for r in locked]

                        skipped = len(suggestion_ids) - len(locked_ids)
                        if skipped > 0:
                            logger.info(
                                "[catalog-learning-worker] Lock contention: %d/%d rows skipped for '%s'",
                                skipped, len(suggestion_ids), name,
                            )

                        if locked_ids:
                            await conn.execute(
                                """
                                UPDATE catalog_suggestions
                                SET status = 'mapped',
                                    matched_category = $2,
                                    mapped_item_key = $3
                                WHERE id = ANY($1::uuid[])
                                """,
                                locked_ids,
                                category,
                                name,
                            )
                            mapped_count = len(locked_ids)
                            auto_mapped += mapped_count

                            # Notify each user whose suggestion was mapped
                            user_rows = await conn.fetch(
                                """
                                SELECT DISTINCT user_id, suggested_name
                                FROM catalog_suggestions
                                WHERE id = ANY($1::uuid[])
                                """,
                                locked_ids,
                            )
                            for ur in user_rows:
                                try:
                                    await send_push_to_user(
                                        conn,
                                        str(ur["user_id"]),
                                        "Suggestion accepted!",
                                        f"Your suggestion '{ur['suggested_name']}' has been added to the catalog!",
                                        data={"type": "catalog_mapped", "category": category, "item_key": name},
                                        notification_type="catalog_mapped",
                                        deep_link="/my-suggestions",
                                    )
                                except Exception as push_exc:
                                    logger.debug("[catalog-learning-worker] Push failed for user %s: %s", ur["user_id"], push_exc)

                logger.info(
                    "[catalog-learning-worker] Auto-mapped %d suggestions: '%s' -> %s",
                    mapped_count, name, category,
                )

        # -------------------------------------------------------------------
        # Step 2: Update category candidates — for suggestions where the
        # suggested_category doesn't match any existing category
        # -------------------------------------------------------------------
        free_text_rows = await pool.fetch(
            """
            SELECT suggested_category,
                   count(*) AS cnt,
                   count(DISTINCT user_id) AS unique_users,
                   min(created_at) AS first_seen,
                   max(created_at) AS last_seen
            FROM catalog_suggestions
            WHERE status IN ('pending', 'new_category')
              AND suggested_category IS NOT NULL
              AND suggested_category NOT IN (
                  SELECT DISTINCT category FROM category_items WHERE category IS NOT NULL
              )
            GROUP BY suggested_category
            HAVING count(*) >= 2
            """
        )

        _ADMIN_THRESHOLDS = (5, 10, 25)

        for row in free_text_rows:
            cat_name = row["suggested_category"]
            slug = _slugify(cat_name)
            if not slug:
                continue

            # Check if this is a NEW candidate (doesn't exist yet)
            existing_candidate = await pool.fetchrow(
                "SELECT signal_count FROM category_candidates WHERE proposed_slug = $1",
                slug,
            )
            old_signal_count = existing_candidate["signal_count"] if existing_candidate else 0
            new_signal_count = row["cnt"]

            await pool.execute(
                """
                INSERT INTO category_candidates (
                    id, proposed_name, proposed_slug, signal_count,
                    unique_users, first_seen, last_seen, status
                ) VALUES (
                    gen_random_uuid(), $1, $2, $3, $4, $5, $6, 'watching'
                )
                ON CONFLICT (proposed_slug) DO UPDATE SET
                    signal_count = EXCLUDED.signal_count,
                    unique_users = EXCLUDED.unique_users,
                    last_seen = EXCLUDED.last_seen
                """,
                cat_name,
                slug,
                new_signal_count,
                row["unique_users"],
                row["first_seen"],
                row["last_seen"],
            )
            candidates_updated += 1

            # Log NEW category demands
            if existing_candidate is None:
                logger.info(
                    "[catalog-learning] NEW category demand: %s (%d users)",
                    cat_name, row["unique_users"],
                )

            # Trigger admin notification when signal_count crosses thresholds
            for threshold in _ADMIN_THRESHOLDS:
                if old_signal_count < threshold <= new_signal_count:
                    logger.info(
                        "[catalog-learning] Category '%s' crossed %d-signal threshold (%d users)",
                        cat_name, threshold, row["unique_users"],
                    )
                    break

        # -------------------------------------------------------------------
        # Step 3: Promote candidates — if unique_users >= threshold in 30 days
        # -------------------------------------------------------------------
        promoted_rows = await pool.fetch(
            """
            UPDATE category_candidates
            SET status = 'candidate'
            WHERE status = 'watching'
              AND unique_users >= $1
              AND last_seen > now() - interval '30 days'
            RETURNING id, proposed_name
            """,
            CATALOG_NEW_CATEGORY_THRESHOLD,
        )
        promoted = len(promoted_rows)

        for row in promoted_rows:
            logger.info(
                "[catalog-learning-worker] Promoted candidate: %s (id=%s)",
                row["proposed_name"], row["id"],
            )

    except Exception as exc:
        logger.error("[catalog-learning-worker] Cycle failed: %s", exc, exc_info=True)
        record_run("catalog_learning_worker", "error")
        try:
            await conn.close()
        except Exception:
            pass
        raise

    try:
        await conn.close()
    except Exception:
        pass

    result = {
        "auto_mapped": auto_mapped,
        "candidates_updated": candidates_updated,
        "promoted": promoted,
    }
    logger.info("[catalog-learning-worker] Cycle complete: %s", result)
    record_run("catalog_learning_worker", "ok")
    return result
