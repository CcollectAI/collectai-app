"""
Background task worker.

Polls the task_queue table for pending tasks and executes them.
Each task type maps to a handler function.

Usage:
    python -m app.lib.task_worker

Or import and call in a FastAPI startup event:
    asyncio.create_task(task_worker.run_worker())
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

# Registry of task handlers
_handlers: dict[str, Callable[[dict], Awaitable[Any]]] = {}


def register_task(task_type: str):
    """Decorator to register a task handler."""
    def decorator(fn: Callable[[dict], Awaitable[Any]]):
        _handlers[task_type] = fn
        return fn
    return decorator


# ── Built-in task handlers ────────────────────────────────────────────────────

@register_task("catalog_refresh")
async def handle_catalog_refresh(payload: dict) -> dict:
    """Refresh catalog data for a category."""
    category_id = payload.get("category_id")
    logger.info("Refreshing catalog for category: %s", category_id)
    # In production, this would trigger the import pipeline
    return {"category_id": category_id, "status": "refreshed"}


@register_task("image_optimize")
async def handle_image_optimize(payload: dict) -> dict:
    """Optimize uploaded images (resize, compress)."""
    image_url = payload.get("image_url")
    logger.info("Optimizing image: %s", image_url)
    # In production, this would download, resize, and re-upload
    return {"image_url": image_url, "optimized": True}


@register_task("market_persist")
async def handle_market_persist(payload: dict) -> dict:
    """Persist market search results to database."""
    item_id = payload.get("item_id")
    logger.info("Persisting market data for item: %s", item_id)
    return {"item_id": item_id, "persisted": True}


@register_task("provenance_log")
async def handle_provenance_log(payload: dict) -> dict:
    """Log provenance information for an item."""
    item_id = payload.get("item_id")
    event = payload.get("event")
    logger.info("Logging provenance for item %s: %s", item_id, event)
    return {"item_id": item_id, "event": event, "logged": True}


# ── Worker loop ───────────────────────────────────────────────────────────────

async def process_one_task(pool) -> bool:
    """Claim and process one task. Returns True if a task was processed."""
    try:
        async with pool.acquire() as conn:
            # Claim the next pending task using FOR UPDATE SKIP LOCKED
            task = await conn.fetchrow(
                """
                UPDATE task_queue tq
                SET status = 'running',
                    started_at = now(),
                    attempts = tq.attempts + 1
                WHERE tq.id = (
                    SELECT t.id FROM task_queue t
                    WHERE t.status = 'pending'
                      AND t.scheduled_for <= now()
                      AND t.attempts < t.max_attempts
                    ORDER BY t.priority DESC, t.scheduled_for ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING tq.id, tq.task_type, tq.payload, tq.attempts
                """
            )

        if not task:
            return False

        task_id = str(task["id"])
        task_type = task["task_type"]
        payload = json.loads(task["payload"]) if isinstance(task["payload"], str) else (task["payload"] or {})
        attempts = task["attempts"]

        logger.info("Processing task %s (type=%s, attempt=%d)", task_id, task_type, attempts)

        handler = _handlers.get(task_type)
        if not handler:
            error_msg = f"Unknown task type: {task_type}"
            logger.warning(error_msg)
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE task_queue
                    SET status = CASE
                          WHEN attempts >= max_attempts THEN 'failed'
                          ELSE 'pending'
                        END,
                        error_message = $2,
                        completed_at = CASE WHEN attempts >= max_attempts THEN now() ELSE NULL END
                    WHERE id = $1 AND status = 'running'
                    """,
                    task["id"],
                    error_msg,
                )
            return True

        try:
            task_result = await handler(payload)
            result_json = json.dumps(task_result) if task_result else None
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE task_queue
                    SET status = 'completed',
                        completed_at = now(),
                        result = $2::jsonb
                    WHERE id = $1 AND status = 'running'
                    """,
                    task["id"],
                    result_json,
                )
            logger.info("Task %s completed successfully", task_id)
        except Exception as e:
            error_msg = str(e)[:500]
            logger.exception("Task %s failed: %s", task_id, error_msg)
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE task_queue
                    SET status = CASE
                          WHEN attempts >= max_attempts THEN 'failed'
                          ELSE 'pending'
                        END,
                        error_message = $2,
                        completed_at = CASE WHEN attempts >= max_attempts THEN now() ELSE NULL END
                    WHERE id = $1 AND status = 'running'
                    """,
                    task["id"],
                    error_msg,
                )

        return True

    except Exception:
        logger.exception("Worker error while claiming/processing task")
        return False


async def run_worker(
    poll_interval: float = 5.0,
    max_iterations: int | None = None,
):
    """Main worker loop. Polls for tasks and processes them.

    Args:
        poll_interval: Seconds to wait between polls when idle
        max_iterations: Stop after N iterations (None = forever, for testing)
    """
    from app.db import get_pool

    logger.info("Task worker started (poll_interval=%.1fs)", poll_interval)
    iterations = 0

    while True:
        pool = get_pool()
        if pool is None:
            logger.warning("Task worker: DB pool not available, waiting...")
            await asyncio.sleep(poll_interval)
            iterations += 1
            if max_iterations and iterations >= max_iterations:
                break
            continue

        processed = await process_one_task(pool)

        if not processed:
            await asyncio.sleep(poll_interval)

        iterations += 1
        if max_iterations and iterations >= max_iterations:
            logger.info("Worker stopping after %d iterations", iterations)
            break


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())
