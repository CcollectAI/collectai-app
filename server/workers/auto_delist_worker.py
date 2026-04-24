#!/usr/bin/env python3
"""Auto-delist worker — automatically delists items from other marketplaces when sold.

When a sale is recorded on one marketplace, this worker finds all other active
listings for the same item_id and marks them as 'delisted' with reason
'auto_delist_sold_elsewhere'. This prevents overselling and keeps inventory
consistent across all connected marketplaces.

Runs every 15 minutes via auto_delist_scheduler.py.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

import asyncpg

from app.worker_registry import record_run
from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [auto_delist] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")

# How far back to look for recent sales (minutes)
LOOKBACK_MINUTES = int(os.getenv("AUTO_DELIST_LOOKBACK_MINUTES", "60"))


@with_async_retry(max_retries=2, base_delay=1.0, max_delay=30.0)
async def run_once():
    """Execute a single auto-delist cycle."""
    if not DSN:
        logger.error("DB_DSN not set in environment")
        record_run("auto_delist_worker", "error")
        return

    # Prefer direct DSN — round-6 pattern, avoids pooler 30s timeout on
    # queries that join items + market_hits. 2026-04-20 round 7.
    conn = await asyncpg.connect(os.getenv("DB_DSN_DIRECT") or DSN)
    logger.info("Connected to DB — starting auto-delist cycle")

    delisted_count = 0
    sales_processed = 0

    try:
        # Find recent sales within the lookback window.
        # Join with marketplace_listings to get the item_id for each sale.
        recent_sales = await conn.fetch(
            """
            SELECT ms.id AS sale_id,
                   ms.listing_id,
                   ml.item_id,
                   ml.user_id,
                   ml.marketplace_id AS sold_marketplace_id,
                   ms.sold_at
            FROM marketplace_sales ms
            JOIN marketplace_listings ml ON ml.id = ms.listing_id
            WHERE ms.sold_at > now() - ($1 || ' minutes')::interval
            ORDER BY ms.sold_at DESC
            """,
            str(LOOKBACK_MINUTES),
        )

        if not recent_sales:
            logger.info("No recent sales found in last %d minutes", LOOKBACK_MINUTES)
            cycle_status = "ok"
            return

        logger.info("Found %d recent sales to process", len(recent_sales))

        now = datetime.now(timezone.utc)

        for sale in recent_sales:
            sale_id = str(sale["sale_id"])
            item_id = str(sale["item_id"])
            user_id = str(sale["user_id"])
            sold_listing_id = str(sale["listing_id"])
            sold_marketplace = sale["sold_marketplace_id"]

            try:
                # Find all other active listings for the same item by the same user
                # that are NOT the listing that was sold
                sibling_listings = await conn.fetch(
                    """
                    SELECT id, marketplace_id, status
                    FROM marketplace_listings
                    WHERE item_id = $1
                      AND user_id = $2
                      AND id != $3
                      AND status IN ('active', 'draft')
                    """,
                    item_id,
                    user_id,
                    sold_listing_id,
                )

                if not sibling_listings:
                    sales_processed += 1
                    continue

                for listing in sibling_listings:
                    listing_id = str(listing["id"])
                    marketplace_id = listing["marketplace_id"]

                    # Update listing to delisted
                    result = await conn.execute(
                        """
                        UPDATE marketplace_listings
                        SET status = 'delisted',
                            status_message = $1,
                            updated_at = $2
                        WHERE id = $3
                          AND status IN ('active', 'draft')
                        """,
                        "auto_delist_sold_elsewhere",
                        now,
                        listing_id,
                    )

                    # Check if the update actually changed a row
                    rows_affected = int(result.split(" ")[-1]) if result else 0
                    if rows_affected > 0:
                        delisted_count += 1
                        logger.info(
                            "Auto-delisted: listing=%s marketplace=%s item=%s "
                            "(sold on %s via listing=%s)",
                            listing_id,
                            marketplace_id,
                            item_id,
                            sold_marketplace,
                            sold_listing_id,
                        )

                sales_processed += 1

            except Exception as e:
                per_sale_failures = per_sale_failures + 1 if "per_sale_failures" in locals() else 1
                # 2026-04-24: capture last per-sale error so worker_runs.metadata
                # surfaces a sample. If multiple sales fail, only the last one
                # is recorded — sufficient for triage.
                last_sale_err = f"{type(e).__name__}: {e!s}"[:500]
                logger.warning(
                    "Failed to process sale %s for item %s: %s",
                    sale_id, item_id, e,
                    exc_info=True,
                )

        logger.info(
            "Auto-delist cycle complete: sales_processed=%d delisted=%d",
            sales_processed, delisted_count,
        )
        # Inventory integrity matters — if every sale failed to delist, that's
        # data-consistency risk (overselling). Emit error so the supervisor
        # and Telegram alerts surface it rather than 'ok'-papering-over.
        cycle_status = "error" if (locals().get("per_sale_failures", 0) > 0 and sales_processed == 0) else "ok"

    finally:
        await conn.close()
        record_run(
            "auto_delist_worker",
            cycle_status if "cycle_status" in locals() else "error",
            error_repr=last_sale_err if "last_sale_err" in locals() else None,
        )


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run(
            "auto_delist_worker", "error",
            error_repr=f"{type(e).__name__}: {e!s}"[:500],
        )
        log_dead_letter("auto_delist_worker", {}, e)
        logger.exception("auto_delist_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
