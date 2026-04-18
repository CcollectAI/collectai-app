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

# Minimum predictions + actuals needed to compute meaningful metrics.
# Lowered from 5 → 2 in R50l because post-clamp many categories had <5
# (predictions, actual) pairs and the worker was silently skipping every
# category — 19 OK runs produced 0 snapshots. 2 samples is too few for a
# robust PICP but gives us *some* signal instead of none.
MIN_SAMPLES = 2

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

    status = "ok"
    categories: list = []
    snapshots_created = 0

    try:
        # Derive the canonical 54 categories from the small category_items table
        # (fast, indexed). DISTINCT over price_predictions.category hits 99k+
        # rows and times out on Supabase pooler — even with an index, the scan
        # is serialized through pgbouncer transaction mode.
        categories = await conn.fetch(
            "SELECT DISTINCT category FROM public.category_items WHERE category IS NOT NULL"
        )

        if not categories:
            logger.info("No categories with recent predictions to calibrate")
            return

        logger.info("Calibrating %d categories", len(categories))

        for cat_row in categories:
            category = cat_row["category"]
            if not category:
                continue

            # For each item_ref in this category, get the latest prediction.
            # Filter by the indexed `category` column, not by item_ref LIKE.
            predictions = await conn.fetch(
                """
                SELECT DISTINCT ON (pp.item_ref)
                    pp.item_ref,
                    pp.q10::float AS q10,
                    pp.q50::float AS q50,
                    pp.q90::float AS q90
                FROM public.price_predictions pp
                WHERE pp.category = $1
                  AND pp.item_ref IS NOT NULL
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

            # Batch-fetch all actuals for this category's item_refs (avoids N+1).
            # Join on market_hits.item_ref (has category: prefix after R50l backfill)
            # — NOT normalized_key, which is still un-prefixed on many rows.
            # Also include listings as a fallback when the bake has few ended auctions:
            # a rough-cut PICP from listings is better than no signal at all.
            item_refs = [pred["item_ref"] for pred in predictions]
            all_actuals = await conn.fetch(
                """
                SELECT item_ref, price::float AS price
                FROM public.market_hits
                WHERE item_ref = ANY($1)
                  AND price IS NOT NULL
                  AND price > 0
                  AND seen_at > now() - ($2 || ' days')::interval
                """,
                item_refs,
                str(SOLD_LOOKBACK_DAYS),
            )

            # Group actuals by item_ref
            actuals_by_key: dict[str, list[float]] = {}
            for row in all_actuals:
                actuals_by_key.setdefault(row["item_ref"], []).append(row["price"])

            covered = 0
            total = 0
            abs_errors = []

            for pred in predictions:
                item_ref = pred["item_ref"]
                q10 = pred["q10"]
                q50 = pred["q50"]
                q90 = pred["q90"]

                prices = actuals_by_key.get(item_ref, [])
                if not prices:
                    continue

                for actual_price in prices:
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
                    (category, picp, ace, mae, samples, gate_pass, gate_reasons)
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

        # Check ground truth accuracy per category (ops monitoring)
        await _check_ground_truth_accuracy(conn)

        # Correctness probe: producing 0 snapshots when categories existed
        # means the market_hits join matched nothing (e.g. key-format drift).
        # Surface as error so discovery_audit doesn't have to infer it.
        if categories and snapshots_created == 0:
            status = "error"
            logger.error(
                "calibration_worker ran against %d categories but produced 0 snapshots — "
                "likely join mismatch or empty sold-comps window",
                len(categories),
            )

    except Exception:
        status = "error"
        raise
    finally:
        await conn.close()
        record_run("calibration_worker", status)


async def _check_ground_truth_accuracy(conn) -> None:
    """Query price_ground_truths for 30-day MAE per category and log warnings."""
    try:
        rows = await conn.fetch(
            """
            SELECT i.category,
                   AVG(ABS(gt.error_pct)) AS mae,
                   COUNT(*) AS n
            FROM public.price_ground_truths gt
            JOIN public.items i ON i.id = gt.item_id
            WHERE gt.recorded_at >= now() - interval '30 days'
              AND gt.error_pct IS NOT NULL
            GROUP BY i.category
            HAVING COUNT(*) >= 3
            ORDER BY mae DESC
            """
        )

        if not rows:
            logger.info("No ground truth data for accuracy check")
            return

        for row in rows:
            category = row["category"]
            mae = float(row["mae"] or 0)
            n = row["n"]

            if mae > 0.25:
                logger.warning(
                    "HIGH MAE for category %s: %.1f%% (n=%d) — review model calibration",
                    category, mae * 100, n,
                )
            else:
                logger.info(
                    "Ground truth accuracy %s: MAE=%.1f%% (n=%d)",
                    category, mae * 100, n,
                )
    except Exception as e:
        logger.warning("Ground truth accuracy check failed: %s", e)


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("calibration_worker", "error")
        log_dead_letter("calibration_worker", {}, e)
        logger.exception("calibration_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
