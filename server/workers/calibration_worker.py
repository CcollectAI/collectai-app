#!/usr/bin/env python3
"""Calibration worker — measures prediction accuracy and populates calibration_snapshots.

For each category with price_predictions, compares predicted intervals
against actual sold prices from market_hits to compute:
  - PICP  (Prediction Interval Coverage Probability)
  - ACE   (Average Coverage Error)
  - MAE   (Mean Absolute Error of q50 vs actual)

Sets gate_pass = true if PICP >= 0.8 (80% coverage).
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
    format="%(asctime)s [calibration_worker] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")

# Minimum predictions + actuals needed to compute meaningful metrics
MIN_SAMPLES = 5

# PICP threshold for gate_pass
PICP_THRESHOLD = 0.80

# Lookback window for sold comps (days)
SOLD_LOOKBACK_DAYS = 90


@with_async_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
async def run_once():
    """Execute a single calibration cycle."""
    if not DSN:
        logger.error("DB_DSN not set in environment")
        record_run("calibration_worker", "error")
        return

    conn = await asyncpg.connect(DSN)
    logger.info("Connected to DB — starting calibration cycle")

    try:
        # Get distinct categories that have predictions
        categories = await conn.fetch(
            """
            SELECT DISTINCT
                SPLIT_PART(item_ref, ':', 1) AS category
            FROM public.price_predictions
            WHERE generated_at > now() - interval '30 days'
              AND q10 IS NOT NULL
              AND q50 IS NOT NULL
              AND q90 IS NOT NULL
            """
        )

        if not categories:
            logger.info("No categories with recent predictions to calibrate")
            record_run("calibration_worker", "ok")
            return

        logger.info("Calibrating %d categories", len(categories))
        snapshots_created = 0

        for cat_row in categories:
            category = cat_row["category"]
            if not category:
                continue

            # For each item_ref in this category, get the latest prediction
            # and compare against actual sold prices
            predictions = await conn.fetch(
                """
                SELECT DISTINCT ON (pp.item_ref)
                    pp.item_ref,
                    pp.q10::float AS q10,
                    pp.q50::float AS q50,
                    pp.q90::float AS q90
                FROM public.price_predictions pp
                WHERE pp.item_ref LIKE $1 || ':%'
                   OR pp.item_ref = $1
                ORDER BY pp.item_ref, pp.generated_at DESC
                """,
                category,
            )

            if len(predictions) < MIN_SAMPLES:
                logger.debug(
                    "Category %s: only %d predictions, skipping",
                    category, len(predictions),
                )
                continue

            # For each prediction, find actual sold prices
            covered = 0
            total = 0
            abs_errors = []

            for pred in predictions:
                item_ref = pred["item_ref"]
                q10 = pred["q10"]
                q50 = pred["q50"]
                q90 = pred["q90"]

                # Get actual sold prices for this item_ref
                actuals = await conn.fetch(
                    """
                    SELECT price::float AS price
                    FROM public.market_hits
                    WHERE normalized_key = $1
                      AND price IS NOT NULL
                      AND ended_at IS NOT NULL
                      AND ended_at > now() - ($2 || ' days')::interval
                    """,
                    item_ref,
                    str(SOLD_LOOKBACK_DAYS),
                )

                if not actuals:
                    continue

                for actual_row in actuals:
                    actual_price = actual_row["price"]
                    total += 1

                    # PICP: is actual within [q10, q90]?
                    if q10 <= actual_price <= q90:
                        covered += 1

                    # MAE: |q50 - actual|
                    abs_errors.append(abs(q50 - actual_price))

            if total < MIN_SAMPLES:
                logger.debug(
                    "Category %s: only %d actuals matched, skipping",
                    category, total,
                )
                continue

            # Compute metrics
            picp = covered / total
            ace = picp - PICP_THRESHOLD  # positive = better than threshold
            mae = sum(abs_errors) / len(abs_errors) if abs_errors else 0.0
            gate_pass = picp >= PICP_THRESHOLD

            gate_reasons = []
            if not gate_pass:
                gate_reasons.append(
                    f"PICP {picp:.2%} below threshold {PICP_THRESHOLD:.0%}"
                )

            # Insert calibration snapshot
            await conn.execute(
                """
                INSERT INTO public.calibration_snapshots
                    (category, picp, ace, mae, n_samples, gate_pass, gate_reasons)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                category,
                picp,
                ace,
                mae,
                total,
                gate_pass,
                gate_reasons,
            )

            snapshots_created += 1
            logger.info(
                "Calibrated %s: PICP=%.2f ACE=%.2f MAE=%.2f n=%d gate=%s",
                category, picp, ace, mae, total,
                "PASS" if gate_pass else "FAIL",
            )

        logger.info(
            "Calibration cycle complete: %d snapshots created",
            snapshots_created,
        )

    finally:
        await conn.close()
        record_run("calibration_worker", "ok")


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("calibration_worker", "error")
        log_dead_letter("calibration_worker", {}, e)
        logger.exception("calibration_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
