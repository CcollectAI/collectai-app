#!/usr/bin/env python3
"""
Vision ingest worker for CollectAI.

Processes queued images from the vision_queue table and items lacking classification.
Uses the 3-tier vision classifier (CLIP / OpenAI Vision / heuristic) to classify
each item and stores results (category, confidence, embedding) back to the database.

Can also process legacy vision_predict_log entries that have no embedding yet.

Usage:
    python -m workers.vision_ingest_worker
    python -m workers.vision_ingest_worker --batch-size 20
    python -m workers.vision_ingest_worker --mode items  (classify unclassified items)
    python -m workers.vision_ingest_worker --mode queue  (process vision_queue)
    python -m workers.vision_ingest_worker --mode legacy (process vision_predict_log)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone

import asyncpg

from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [vision_ingest] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.environ.get("DB_DSN", "")
DEFAULT_BATCH_SIZE = int(os.getenv("VISION_BATCH_SIZE", "10"))


def _to_vector_literal(v: list[float]) -> str:
    """Turn [0.1, 0.2, ...] into '[0.1,0.2,...]' for pgvector."""
    return "[" + ",".join(f"{x:.8f}" for x in v) + "]"


# ---------------------------------------------------------------------------
# Mode: process vision_queue (new items awaiting classification)
# ---------------------------------------------------------------------------

@with_async_retry(max_retries=3, base_delay=2.0, max_delay=60.0)
async def _process_vision_queue(batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    """
    Pick up pending entries from vision_queue, classify each image,
    and write results back to vision_queue + items table.

    Returns the number of items processed.
    """
    if not DSN:
        logger.error("DB_DSN not set; cannot process vision queue")
        return 0

    conn = await asyncpg.connect(DSN)
    processed = 0
    try:
        # Fetch unprocessed queue entries
        rows = await conn.fetch(
            """
            SELECT id, item_id, image_url, image_data, filename, created_at
            FROM public.vision_queue
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT $1
            """,
            batch_size,
        )

        if not rows:
            logger.info("vision_queue: no pending entries")
            return 0

        logger.info("vision_queue: processing %d entries", len(rows))

        # Import classifier lazily to avoid circular imports at module level
        from app.ml.vision_classifier import classify_image

        for row in rows:
            queue_id = row["id"]
            item_id = row["item_id"]
            image_url = row.get("image_url") or ""
            image_data: bytes | None = row.get("image_data")
            filename = row.get("filename") or ""

            try:
                # Get image bytes: either from stored blob or fetch from URL
                image_bytes = image_data
                if not image_bytes and image_url:
                    image_bytes = await _fetch_image_url(image_url)

                if not image_bytes:
                    logger.warning(
                        "vision_queue id=%s: no image data available, skipping",
                        queue_id,
                    )
                    await conn.execute(
                        """
                        UPDATE public.vision_queue
                        SET status = 'error', error_message = $1, processed_at = $2
                        WHERE id = $3
                        """,
                        "No image data available",
                        datetime.now(timezone.utc),
                        queue_id,
                    )
                    continue

                # Classify the image
                result = await classify_image(image_bytes, filename)

                # Prepare embedding for pgvector if available
                embedding_literal = None
                if result.embedding_vector:
                    embedding_literal = _to_vector_literal(result.embedding_vector)

                # Update queue entry + item in a single transaction
                async with conn.transaction():
                    await conn.execute(
                        """
                        UPDATE public.vision_queue
                        SET status = 'completed',
                            predicted_category = $1,
                            category_confidence = $2,
                            predicted_condition = $3,
                            condition_confidence = $4,
                            suggested_name = $5,
                            classification_method = $6,
                            attributes_json = $7,
                            processed_at = $8
                        WHERE id = $9
                        """,
                        result.category_id,
                        result.category_confidence,
                        result.condition,
                        result.condition_confidence,
                        result.suggested_name,
                        result.classification_method,
                        json.dumps(result.attributes) if result.attributes else None,
                        datetime.now(timezone.utc),
                        queue_id,
                    )

                    # If we have an item_id, update the item's category and condition
                    if item_id:
                        await _update_item_classification(
                            conn, item_id, result.category_id,
                            result.category_confidence, result.condition,
                            result.classification_method, embedding_literal,
                        )

                processed += 1
                logger.info(
                    "vision_queue id=%s: classified as %s (%.2f%% confidence, method=%s)",
                    queue_id,
                    result.category_id,
                    result.category_confidence * 100,
                    result.classification_method,
                )

            except Exception as e:
                logger.warning("vision_queue id=%s: classification failed: %s", queue_id, e)
                await conn.execute(
                    """
                    UPDATE public.vision_queue
                    SET status = 'error', error_message = $1, processed_at = $2
                    WHERE id = $3
                    """,
                    str(e)[:500],
                    datetime.now(timezone.utc),
                    queue_id,
                )

        logger.info("vision_queue: completed processing %d / %d entries", processed, len(rows))

    finally:
        await conn.close()

    return processed


# ---------------------------------------------------------------------------
# Mode: classify items that have no category set
# ---------------------------------------------------------------------------

@with_async_retry(max_retries=3, base_delay=2.0, max_delay=60.0)
async def _process_unclassified_items(batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    """
    Find items without a category classification and attempt to classify them
    using their primary image or title-based heuristics.

    Returns the number of items processed.
    """
    if not DSN:
        logger.error("DB_DSN not set; cannot process items")
        return 0

    conn = await asyncpg.connect(DSN)
    processed = 0
    try:
        # Fetch items that have an image but no category
        rows = await conn.fetch(
            """
            SELECT i.id, i.title, i.image_url, i.category
            FROM public.items i
            WHERE (i.category IS NULL OR i.category = '')
              AND i.image_url IS NOT NULL
              AND i.image_url != ''
            ORDER BY i.created_at DESC
            LIMIT $1
            """,
            batch_size,
        )

        if not rows:
            logger.info("items: no unclassified items with images found")
            return 0

        logger.info("items: processing %d unclassified items", len(rows))

        from app.ml.vision_classifier import classify_image

        for row in rows:
            item_id = row["id"]
            title = row.get("title") or ""
            image_url = row.get("image_url") or ""

            try:
                # Fetch the image
                image_bytes = await _fetch_image_url(image_url) if image_url else None

                if not image_bytes:
                    # Fall back to title-based heuristic with empty image
                    image_bytes = b""

                filename = f"{title}.jpg" if title else ""
                result = await classify_image(image_bytes, filename)

                embedding_literal = None
                if result.embedding_vector:
                    embedding_literal = _to_vector_literal(result.embedding_vector)

                await _update_item_classification(
                    conn, item_id, result.category_id,
                    result.category_confidence, result.condition,
                    result.classification_method, embedding_literal,
                )

                processed += 1
                logger.info(
                    "item id=%s (%s): classified as %s (%.2f%%, method=%s)",
                    item_id, title[:50], result.category_id,
                    result.category_confidence * 100, result.classification_method,
                )

            except Exception as e:
                logger.warning("item id=%s: classification failed: %s", item_id, e)

        logger.info("items: classified %d / %d items", processed, len(rows))

    finally:
        await conn.close()

    return processed


# ---------------------------------------------------------------------------
# Mode: legacy — process vision_predict_log (backward compatibility)
# ---------------------------------------------------------------------------

@with_async_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
async def _process_legacy_log(batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    """
    Process legacy vision_predict_log entries that lack embeddings.
    Uses the classifier to generate category predictions from item_ref text.

    Returns the number of entries processed.
    """
    if not DSN:
        logger.error("DB_DSN not set; cannot process legacy log")
        return 0

    conn = await asyncpg.connect(DSN)
    processed = 0
    try:
        rows = await conn.fetch(
            """
            SELECT id, item_ref, image_url
            FROM public.vision_predict_log
            WHERE embedding IS NULL
            ORDER BY created_at ASC
            LIMIT $1
            """,
            batch_size,
        )

        if not rows:
            logger.info("vision_predict_log: no pending entries")
            return 0

        logger.info("vision_predict_log: processing %d entries", len(rows))

        from app.ml.vision_classifier import classify_image

        for row in rows:
            vid = row["id"]
            item_ref = row.get("item_ref") or ""
            image_url = row.get("image_url") or ""

            try:
                # Try to fetch image if URL is available
                image_bytes = b""
                if image_url:
                    fetched = await _fetch_image_url(image_url)
                    if fetched:
                        image_bytes = fetched

                # Use item_ref as filename hint for heuristic
                result = await classify_image(image_bytes, item_ref)

                # Prepare embedding if available
                embedding_literal = None
                if result.embedding_vector:
                    embedding_literal = _to_vector_literal(result.embedding_vector)

                # Update the legacy log entry
                if embedding_literal:
                    await conn.execute(
                        """
                        UPDATE public.vision_predict_log
                        SET embedding = $1::vector,
                            predicted_label = $2,
                            score = $3
                        WHERE id = $4
                        """,
                        embedding_literal,
                        result.category_id,
                        float(result.category_confidence),
                        vid,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE public.vision_predict_log
                        SET predicted_label = $1,
                            score = $2
                        WHERE id = $3
                        """,
                        result.category_id,
                        float(result.category_confidence),
                        vid,
                    )

                processed += 1
                logger.info(
                    "vision_predict_log id=%s ref=%s: label=%s score=%.4f method=%s",
                    vid, item_ref[:50], result.category_id,
                    result.category_confidence, result.classification_method,
                )

            except Exception as e:
                logger.warning("vision_predict_log id=%s: failed: %s", vid, e)

        logger.info("vision_predict_log: processed %d / %d entries", processed, len(rows))

    finally:
        await conn.close()

    return processed


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def _update_item_classification(
    conn: asyncpg.Connection,
    item_id: str,
    category_id: str,
    confidence: float,
    condition: str | None,
    method: str,
    embedding_literal: str | None,
) -> None:
    """Update an item's classification fields in the items table."""
    try:
        if condition:
            await conn.execute(
                """
                UPDATE public.items
                SET category = $1,
                    condition = $2,
                    attributes_json = COALESCE(attributes_json, '{}')::jsonb
                        || jsonb_build_object(
                            'vision_category_confidence', $3,
                            'vision_classification_method', $4,
                            'vision_classified_at', $5
                        )
                WHERE id = $6
                """,
                category_id,
                condition,
                confidence,
                method,
                datetime.now(timezone.utc).isoformat(),
                item_id,
            )
        else:
            await conn.execute(
                """
                UPDATE public.items
                SET category = $1,
                    attributes_json = COALESCE(attributes_json, '{}')::jsonb
                        || jsonb_build_object(
                            'vision_category_confidence', $2,
                            'vision_classification_method', $3,
                            'vision_classified_at', $4
                        )
                WHERE id = $5
                """,
                category_id,
                confidence,
                method,
                datetime.now(timezone.utc).isoformat(),
                item_id,
            )
    except Exception as e:
        logger.warning("Failed to update item %s classification: %s", item_id, e)


async def _fetch_image_url(url: str, timeout: float = 15.0) -> bytes | None:
    """Fetch image bytes from a URL with timeout and size limits."""
    import httpx

    if not url:
        return None

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()

            # Enforce size limit (20 MB)
            if len(resp.content) > 20 * 1024 * 1024:
                logger.warning("Image at %s exceeds 20 MB, skipping", url[:100])
                return None

            return resp.content

    except httpx.HTTPStatusError as e:
        logger.warning("HTTP error fetching image %s: status %d", url[:100], e.response.status_code)
        return None
    except Exception as e:
        logger.warning("Failed to fetch image %s: %s", url[:100], e)
        return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main(mode: str = "queue", batch_size: int = DEFAULT_BATCH_SIZE) -> None:
    """Run the vision ingest worker in the specified mode."""
    logger.info("Starting vision_ingest_worker mode=%s batch_size=%d", mode, batch_size)

    try:
        if mode == "queue":
            await _process_vision_queue(batch_size)
        elif mode == "items":
            await _process_unclassified_items(batch_size)
        elif mode == "legacy":
            await _process_legacy_log(batch_size)
        elif mode == "all":
            # Run all modes sequentially
            await _process_vision_queue(batch_size)
            await _process_unclassified_items(batch_size)
            await _process_legacy_log(batch_size)
        else:
            logger.error("Unknown mode: %s (valid: queue, items, legacy, all)", mode)
            return

    except Exception as e:
        log_dead_letter("vision_ingest_worker", {"mode": mode, "batch_size": batch_size}, e)
        logger.exception("vision_ingest_worker crashed: %r", e)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CollectAI Vision Ingest Worker")
    parser.add_argument(
        "--mode",
        choices=["queue", "items", "legacy", "all"],
        default="queue",
        help="Processing mode (default: queue)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of items to process per batch (default: {DEFAULT_BATCH_SIZE})",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(main(mode=args.mode, batch_size=args.batch_size))
