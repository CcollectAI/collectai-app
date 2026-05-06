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

# Use DB_DSN_DIRECT (port 5432) to escape the Supabase pooler 30s statement
# cap. The per-category DISTINCT-ON over partitioned price_predictions plus
# the market_hits actuals fetches add up across 54 categories — even though
# each individual query is sub-second, the cumulative single-connection
# transaction was hitting 30s on a busy bake. Same fix family as
# marketplace_agent.persist_comps_to_db (commit 50cefd3, 2026-04-27).
# See learning_use_direct_dsn_for_partitioned_writes.md.
DSN = os.getenv("DB_DSN_DIRECT") or os.getenv("DB_DSN")

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

    # Tagged via application_name for the ExecStop cancel hook.
    conn = await asyncpg.connect(
        DSN,
        server_settings={"application_name": "collectai-bake-calibration_worker"},
    )
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
            # The generated_at filter triggers partition pruning (Subplans
            # Removed: 1 in EXPLAIN) and drops planning time from 160ms to
            # 3ms — verified 2026-05-02. Calibration only needs recent
            # predictions to compute PICP/MAE so 90 days is plenty.
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
                  AND pp.generated_at > now() - interval '90 days'
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
                  -- Exclude synthetic Claude estimates from PICP. We must
                  -- measure the model against REAL sold prices, not
                  -- against our own LLM fallback. Otherwise calibration
                  -- becomes "how well does Claude match Claude" and
                  -- gate_pass passes for the wrong reason.
                  AND (source IS NULL OR source <> 'claude_estimate')
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

            # Auto-rollback gate (B2.2): if PICP collapsed > 10pp vs 7-day
            # median AND gate=FAIL, revert artifacts/{cat}/active one version.
            await _maybe_rollback_on_picp_collapse(conn, category, picp, gate_pass)

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


# PICP-collapse rollback: if a category's current PICP drops > N pp from
# its 7-day median AND fails the gate, swap the active model symlink back
# one version. Default 10 percentage points — anything less is noise on
# small samples.
PICP_REGRESSION_THRESHOLD_PP = float(os.getenv("CALIBRATION_PICP_ROLLBACK_PP", "10")) / 100.0


async def _maybe_rollback_on_picp_collapse(conn, category: str, current_picp: float, current_gate_pass: bool) -> None:
    """If today's PICP is materially worse than the trailing median AND fails
    the gate, revert artifacts/{category}/active to the prior version.

    The prior version is read from the on-disk artifact directory listing —
    the version directly preceding (lexicographic) what the current symlink
    points at. Versions are timestamped (YYYYMMDD_HHMMSS) so lex sort = chrono.
    """
    if current_gate_pass:
        return  # gate passed; nothing to roll back

    median_row = await conn.fetchrow(
        """
        SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY picp) AS median_picp
        FROM public.calibration_snapshots
        WHERE category = $1
          AND created_at >= now() - interval '7 days'
          AND created_at < now() - interval '15 minutes'
        """,
        category,
    )
    median_picp = median_row and median_row["median_picp"]
    if median_picp is None:
        return  # no historical baseline yet
    median_picp = float(median_picp)
    if current_picp >= median_picp - PICP_REGRESSION_THRESHOLD_PP:
        return  # within tolerance

    try:
        from app.ml.model_loader import _resolve_artifacts_root
        root = _resolve_artifacts_root()
        if root is None:
            return
        cat_dir = root / category
        active_link = cat_dir / "active"
        if not active_link.is_symlink():
            return
        current_target = os.readlink(str(active_link))
        # Sort sibling version dirs (excluding 'active' / 'canary') chronologically
        siblings = sorted(
            d.name for d in cat_dir.iterdir()
            if d.is_dir() and d.name not in ("active", "canary")
        )
        if current_target not in siblings or len(siblings) < 2:
            return
        idx = siblings.index(current_target)
        if idx == 0:
            return  # no earlier version to roll back to
        prior_version = siblings[idx - 1]

        active_link.unlink()
        active_link.symlink_to(prior_version)

        logger.warning(
            "[calibration] AUTO-ROLLBACK %s: PICP=%.2f vs 7d-median=%.2f (drop>%.0fpp + gate=FAIL); "
            "reverted active %s -> %s",
            category, current_picp, median_picp,
            PICP_REGRESSION_THRESHOLD_PP * 100,
            current_target, prior_version,
        )
        # Page Telegram so the rollback is visible
        try:
            from app.lib.telegram_ops import send_ops_alert
            await send_ops_alert(
                f"[calibration] AUTO-ROLLBACK {category}: "
                f"PICP {current_picp:.2f} vs 7d-median {median_picp:.2f}; "
                f"active reverted {current_target} -> {prior_version}"
            )
        except Exception:
            pass
    except Exception as e:
        logger.warning("[calibration] rollback for %s failed: %s", category, e)


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
