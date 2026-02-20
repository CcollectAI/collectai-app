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
import httpx
import re

from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [vision_ingest] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.environ.get("DB_DSN", "")
DEFAULT_BATCH_SIZE = int(os.getenv("VISION_BATCH_SIZE", "10"))


def _sanitize_error(e: Exception) -> str:
    """Return a sanitized error string safe for DB storage.

    Includes the exception type and a truncated message with common secret
    patterns redacted (URLs with tokens, Authorization headers, API keys).
    """
    raw = str(e)[:200]
    # Redact common secret patterns
    raw = re.sub(r'(https?://[^\s]*[?&](?:key|token|secret|api_key|access_token)=)[^\s&"\']+', r'\1[REDACTED]', raw, flags=re.IGNORECASE)
    raw = re.sub(r'(Authorization:\s*(?:Bearer|Basic|Token)\s+)\S+', r'\1[REDACTED]', raw, flags=re.IGNORECASE)
    raw = re.sub(r'((?:api[_-]?key|secret[_-]?key|access[_-]?token|password)\s*[=:]\s*)[^\s,;"\']+', r'\1[REDACTED]', raw, flags=re.IGNORECASE)
    return f"{type(e).__name__}: {raw}"


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

    Uses a "claim then process" pattern to prevent double-processing:

    1. SHORT transaction: atomically UPDATE pending -> processing (SKIP LOCKED)
       so concurrent workers never claim the same rows.
    2. OUTSIDE the transaction: classify images (slow I/O / API calls).
    3. Per-row: UPDATE to completed or error status.

    If a worker crashes mid-processing, rows remain in 'processing' state
    and can be reclaimed by a timeout cleanup job later.

    Returns the number of items processed.
    """
    if not DSN:
        logger.error("DB_DSN not set; cannot process vision queue")
        return 0

    conn = await asyncpg.connect(DSN)
    processed = 0
    try:
        # ------------------------------------------------------------------
        # Step 0: Recover stale rows stuck in 'processing' for > 15 minutes
        # (crashed workers that never completed). Reset them to 'pending'.
        # ------------------------------------------------------------------
        stale_recovered = await conn.execute(
            """
            UPDATE public.vision_queue
            SET status = 'pending'
            WHERE status = 'processing'
              AND created_at < now() - interval '15 minutes'
            """
        )
        # asyncpg returns "UPDATE N" — extract the count
        try:
            stale_count = int(str(stale_recovered).split()[-1])
        except (ValueError, IndexError, AttributeError):
            stale_count = 0
        if stale_count > 0:
            logger.warning("vision_queue: recovered %d stale 'processing' rows", stale_count)

        # ------------------------------------------------------------------
        # Step 1: Atomically claim rows in a short transaction.
        # The UPDATE ... FOR UPDATE SKIP LOCKED inside an explicit
        # transaction ensures concurrent workers never claim the same rows.
        # The transaction commits immediately after the RETURNING, so the
        # row locks are held only for milliseconds.
        # ------------------------------------------------------------------
        async with conn.transaction():
            rows = await conn.fetch(
                """
                UPDATE public.vision_queue
                SET status = 'processing'
                WHERE id IN (
                    SELECT id
                    FROM public.vision_queue
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT $1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id, item_id, image_url, image_data, filename, created_at
                """,
                batch_size,
            )
        # Transaction closed — row locks released.  Other workers now see
        # status = 'processing' and will skip these rows.

        if not rows:
            logger.info("vision_queue: no pending entries")
            return 0

        logger.info("vision_queue: claimed %d entries for processing", len(rows))

        # Import classifier lazily to avoid circular imports at module level
        from app.ml.vision_classifier import classify_image
        import httpx as _httpx

        # ------------------------------------------------------------------
        # Step 2: Process each claimed row outside any long-running txn.
        # Share a single httpx client across all image fetches in this batch
        # to avoid creating/destroying a TCP connection per image.
        # ------------------------------------------------------------------
        async with _httpx.AsyncClient(timeout=15.0, follow_redirects=False) as shared_client:
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
                        image_bytes = await _fetch_image_url(image_url, client=shared_client)

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

                    # Step 3: Update queue entry + item in a single transaction
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
                        _sanitize_error(e),
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
        import httpx as _httpx

        async with _httpx.AsyncClient(timeout=15.0, follow_redirects=False) as shared_client:
            for row in rows:
                item_id = row["id"]
                title = row.get("title") or ""
                image_url = row.get("image_url") or ""

                try:
                    # Fetch the image
                    image_bytes = await _fetch_image_url(image_url, client=shared_client) if image_url else None

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
        import httpx as _httpx

        async with _httpx.AsyncClient(timeout=15.0, follow_redirects=False) as shared_client:
            for row in rows:
                vid = row["id"]
                item_ref = row.get("item_ref") or ""
                image_url = row.get("image_url") or ""

                try:
                    # Try to fetch image if URL is available
                    image_bytes = b""
                    if image_url:
                        fetched = await _fetch_image_url(image_url, client=shared_client)
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


async def _fetch_image_url(
    url: str,
    timeout: float = 15.0,
    _max_redirects: int = 5,
    client: httpx.AsyncClient | None = None,
) -> bytes | None:
    """Fetch image bytes from a URL with timeout, size limits, and SSRF protection.

    Validates every URL (including redirect targets) against private/internal IP
    ranges before making the request.  See ``app.ssrf.validate_url`` for the
    full list of blocked networks.

    If *client* is provided it will be used directly (connection pooling across
    a batch of fetches).  Otherwise a one-shot client is created and closed
    automatically for backward compatibility.
    """
    from app.ssrf import validate_url

    if not url:
        return None

    # When a shared client is supplied, use it directly (no context manager).
    # When not supplied, create a short-lived client as before.
    owns_client = client is None

    try:
        # --- SSRF gate: validate the initial URL --------------------------
        validate_url(url)

        if owns_client:
            client = httpx.AsyncClient(timeout=timeout, follow_redirects=False)

        try:
            # Disable automatic redirect following so we can validate each
            # redirect target against the SSRF allowlist before following it.
            current_url = url
            for _ in range(_max_redirects):
                resp = await client.get(current_url)

                # Handle redirects manually with SSRF validation
                if resp.is_redirect:
                    redirect_url = str(resp.next_request.url) if resp.next_request else None
                    if not redirect_url:
                        logger.warning(
                            "Redirect from %s with no Location header, aborting",
                            current_url[:100],
                        )
                        return None
                    # Validate the redirect target before following
                    validate_url(redirect_url)
                    current_url = redirect_url
                    continue

                # Not a redirect — process the response
                resp.raise_for_status()

                # Enforce size limit (20 MB)
                if len(resp.content) > 20 * 1024 * 1024:
                    logger.warning("Image at %s exceeds 20 MB, skipping", url[:100])
                    return None

                return resp.content

            # If we exhausted the redirect budget
            logger.warning("Too many redirects (%d) for %s", _max_redirects, url[:100])
            return None

        finally:
            if owns_client and client is not None:
                await client.aclose()

    except ValueError as e:
        # validate_url raises ValueError for blocked URLs
        logger.warning("SSRF blocked URL %s: %s", url[:100], e)
        return None
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
