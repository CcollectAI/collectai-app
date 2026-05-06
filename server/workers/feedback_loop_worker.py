#!/usr/bin/env python3
"""Feedback loop worker — label_events corrections flow back into catalog.

Reads user corrections from label_events (QuickScan corrections) and
predict_sessions (price prediction confirmations/corrections).

For each unprocessed correction:
  - Updates category_items.attributes_json under "user_confirmed" namespace
  - Tracks observation counts for confidence scoring
  - Uses jsonb_set (NOT || — see learnings about JSONB merge corruption)
  - Marks events as processed via processed_at timestamp

Registered in worker_registry SCHEDULES with 1h interval.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import asyncpg

from app.worker_registry import record_run
from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [feedback_loop] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")

# Maximum events to process per cycle to avoid long-running transactions
BATCH_SIZE = int(os.getenv("FEEDBACK_BATCH_SIZE", "200"))


async def _ensure_processed_at_column(conn) -> None:
    """Add processed_at column to label_events if it doesn't exist."""
    exists = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'label_events'
              AND column_name = 'processed_at'
        )
        """
    )
    if not exists:
        await conn.execute(
            "ALTER TABLE public.label_events ADD COLUMN IF NOT EXISTS processed_at timestamptz"
        )
        logger.info("Added processed_at column to label_events")


async def _process_label_corrections(conn) -> int:
    """Process unprocessed label_events where user corrected title/condition/price.

    Returns the number of events processed.
    """
    rows = await conn.fetch(
        """
        SELECT le.id, le.item_id, le.corrected_title, le.corrected_condition,
               le.corrected_price_eur, le.payload, le.action,
               i.canonical_key, i.category
        FROM public.label_events le
        LEFT JOIN public.items i ON i.id = le.item_id
        WHERE le.processed_at IS NULL
          AND (le.corrected_title IS NOT NULL
               OR le.corrected_condition IS NOT NULL
               OR le.corrected_price_eur IS NOT NULL
               OR le.action IN ('confirm', 'correction'))
        ORDER BY le.created_at ASC
        LIMIT $1
        """,
        BATCH_SIZE,
    )

    if not rows:
        return 0

    processed = 0
    for row in rows:
        event_id = row["id"]
        canonical_key = row["canonical_key"]
        category = row["category"]

        # Build the user_confirmed data from corrections
        confirmed = {}
        if row["corrected_title"]:
            confirmed["title"] = row["corrected_title"]
        if row["corrected_condition"]:
            confirmed["condition"] = row["corrected_condition"]
        if row["corrected_price_eur"] is not None:
            confirmed["price_eur"] = float(row["corrected_price_eur"])

        # Parse payload for additional corrections (category, item_key)
        payload = row["payload"]
        if payload:
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except (json.JSONDecodeError, TypeError):
                    payload = {}
            if isinstance(payload, dict):
                if payload.get("corrected_category"):
                    confirmed["category"] = payload["corrected_category"]
                if payload.get("corrected_item_key"):
                    confirmed["item_key"] = payload["corrected_item_key"]

        if not confirmed or not canonical_key:
            # Mark as processed even if no correction data (avoid reprocessing)
            await conn.execute(
                "UPDATE public.label_events SET processed_at = now() WHERE id = $1",
                event_id,
            )
            processed += 1
            continue

        # Update category_items.attributes_json under user_confirmed namespace
        # Use jsonb_set (NOT || to avoid JSONB merge corruption)
        try:
            # First, get current attributes_json
            cat_row = await conn.fetchrow(
                """
                SELECT id, attributes_json
                FROM public.category_items
                WHERE category = $1 AND item_key = $2
                LIMIT 1
                """,
                category,
                canonical_key,
            )

            if cat_row:
                attrs = cat_row["attributes_json"]
                if isinstance(attrs, str):
                    try:
                        attrs = json.loads(attrs)
                    except (json.JSONDecodeError, TypeError):
                        attrs = {}
                elif attrs is None:
                    attrs = {}

                # Get or create user_confirmed namespace
                user_conf = attrs.get("user_confirmed", {})

                # Update each confirmed field with observation count
                for field, value in confirmed.items():
                    existing = user_conf.get(field, {})
                    if isinstance(existing, dict) and existing.get("value") == value:
                        # Same value confirmed again — increment count
                        existing["n"] = existing.get("n", 1) + 1
                        existing["confidence"] = min(
                            0.99, 0.5 + (existing["n"] * 0.1)
                        )
                    else:
                        # New or different value
                        existing = {
                            "value": value,
                            "n": 1,
                            "confidence": 0.5,
                        }
                    user_conf[field] = existing

                # Write back using jsonb_set
                await conn.execute(
                    """
                    UPDATE public.category_items
                    SET attributes_json = jsonb_set(
                        COALESCE(attributes_json, '{}'::jsonb),
                        '{user_confirmed}',
                        $1::jsonb
                    )
                    WHERE id = $2
                    """,
                    json.dumps(user_conf),
                    cat_row["id"],
                )

        except Exception as e:
            logger.warning(
                "Failed to update catalog for event %s: %s", event_id, e
            )
            # Still mark as processed to avoid infinite retry
            pass

        # Mark event as processed
        await conn.execute(
            "UPDATE public.label_events SET processed_at = now() WHERE id = $1",
            event_id,
        )
        processed += 1

    return processed


async def _process_prediction_confirmations(conn) -> int:
    """Process predict_sessions where user confirmed/corrected predictions.

    When a user confirms a prediction is accurate, that strengthens the
    model's confidence for that item. When they correct, we note the delta.

    Returns number of sessions processed.
    """
    # Check if predict_sessions has processed_at column
    has_col = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'predict_sessions'
              AND column_name = 'processed_at'
        )
        """
    )
    if not has_col:
        await conn.execute(
            "ALTER TABLE public.predict_sessions ADD COLUMN IF NOT EXISTS processed_at timestamptz"
        )
        logger.info("Added processed_at column to predict_sessions")

    # predict_sessions.item_id is bigint, items.id is uuid — can't join directly.
    # canonical_key is unavailable via this path; we degrade gracefully to
    # "process without canonical_key" below (canonical_key=None skips the
    # category_items UPDATE but still marks the session as processed).
    rows = await conn.fetch(
        """
        SELECT ps.id, ps.category, ps.status, ps.confidence,
               ps.price_mid_eur, ps.output, ps.meta,
               NULL::text AS canonical_key
        FROM public.predict_sessions ps
        WHERE ps.processed_at IS NULL
          AND ps.status IN ('confirmed', 'corrected')
        ORDER BY ps.created_at ASC
        LIMIT $1
        """,
        BATCH_SIZE,
    )

    if not rows:
        return 0

    processed = 0
    for row in rows:
        session_id = row["id"]
        canonical_key = row["canonical_key"]
        category = row["category"]

        if canonical_key and category:
            try:
                # Parse output/meta for user-provided corrections
                meta = row["meta"]
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except (json.JSONDecodeError, TypeError):
                        meta = {}
                elif meta is None:
                    meta = {}

                status = row["status"]
                confirmed_data = {}
                if status == "confirmed" and row["price_mid_eur"]:
                    confirmed_data["price_eur"] = {
                        "value": float(row["price_mid_eur"]),
                        "n": 1,
                        "confidence": float(row["confidence"] or 0.5),
                        "source": "prediction_confirmed",
                    }

                if confirmed_data:
                    cat_row = await conn.fetchrow(
                        """
                        SELECT id FROM public.category_items
                        WHERE category = $1 AND item_key = $2
                        LIMIT 1
                        """,
                        category,
                        canonical_key,
                    )
                    if cat_row:
                        await conn.execute(
                            """
                            UPDATE public.category_items
                            SET attributes_json = jsonb_set(
                                COALESCE(attributes_json, '{}'::jsonb),
                                '{prediction_confirmed}',
                                $1::jsonb
                            )
                            WHERE id = $2
                            """,
                            json.dumps(confirmed_data),
                            cat_row["id"],
                        )

            except Exception as e:
                logger.warning(
                    "Failed to process prediction session %s: %s",
                    session_id, e,
                )

        await conn.execute(
            "UPDATE public.predict_sessions SET processed_at = now() WHERE id = $1",
            session_id,
        )
        processed += 1

    return processed


@with_async_retry(max_retries=3, base_delay=2.0, max_delay=120.0)
async def run_once():
    """Execute a single feedback loop cycle."""
    if not DSN:
        logger.error("DB_DSN not set in environment")
        record_run("feedback_loop_worker", "error")
        return

    # Tagged via application_name for the ExecStop cancel hook.
    conn = await asyncpg.connect(
        DSN,
        server_settings={"application_name": "collectai-bake-feedback_loop_worker"},
    )
    try:
        # Ensure schema is ready
        await _ensure_processed_at_column(conn)

        label_count = await _process_label_corrections(conn)
        prediction_count = await _process_prediction_confirmations(conn)

        logger.info(
            "Feedback loop complete: %d label corrections, %d prediction confirmations",
            label_count,
            prediction_count,
        )
    finally:
        await conn.close()
    record_run("feedback_loop_worker", "ok")


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("feedback_loop_worker", "error")
        log_dead_letter("feedback_loop_worker", {}, e)
        logger.exception("feedback_loop_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
