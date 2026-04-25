#!/usr/bin/env python3
"""Vision quality worker — turns scan_corrections into actionable model
recalibration without retraining the OpenAI vision model itself.

OpenAI does not yet expose vision model fine-tuning, so we cannot train
GPT-4o-mini on our scan_corrections directly. Instead this worker:

  1. Joins `scan_corrections` (corrected_category) with `predict_sessions`
     (predicted category + confidence) to compute per-category accuracy
     and confidence calibration over the last 30 days.
  2. Identifies the top-2 confusion targets per category (e.g.,
     yugioh→mtg corrections happen 30% of the time).
  3. Upserts results to `vision_category_quality` keyed by category.

Downstream consumer: `app.ml.openai_vision`:
  - reads `confidence_calibration_factor` to discount model confidence
    for known-unreliable categories.
  - reads `common_confusion_target` to inject a "watch for confusion with
    X" hint into the system prompt at request time (B3.2).

This is the calibration_worker pattern (PICP/ACE/MAE for prices) applied
to vision outputs. Gates the entire loop on enough samples — does nothing
useful until scan_corrections has data.
"""

from __future__ import annotations

import asyncio
import logging
import os

import asyncpg

from app.worker_registry import record_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [vision_quality] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN_DIRECT") or os.getenv("DB_DSN")
LOOKBACK_DAYS = int(os.getenv("VISION_QUALITY_LOOKBACK_DAYS", "30"))
MIN_SAMPLES_PER_CAT = int(os.getenv("VISION_QUALITY_MIN_SAMPLES", "10"))


async def _ensure_table(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS public.vision_category_quality (
            category                       text PRIMARY KEY,
            predicted_accuracy_30d         numeric,
            confidence_calibration_factor  numeric,
            common_confusion_target        text,
            common_confusion_secondary     text,
            sample_count                   integer,
            computed_at                    timestamptz NOT NULL DEFAULT now()
        )
        """
    )


async def run_once() -> dict[str, int]:
    if not DSN:
        logger.warning("DB_DSN not set — skipping")
        record_run("vision_quality_worker", "error")
        return {"updated": 0, "skipped": 0}

    conn = await asyncpg.connect(DSN)
    updated = 0
    skipped = 0
    try:
        await _ensure_table(conn)

        # Pull every (predicted_category, predicted_confidence,
        # corrected_category) tuple from the last LOOKBACK_DAYS. Join
        # scan_corrections.scan_session_id → predict_sessions.id (text id,
        # not uuid_id — verify by inspection if changed).
        rows = await conn.fetch(
            """
            SELECT
                ps.category   AS predicted,
                COALESCE(ps.confidence, 0.7) AS confidence,
                sc.corrected_category AS corrected
            FROM public.scan_corrections sc
            JOIN public.predict_sessions ps
              ON ps.uuid_id::text = sc.scan_session_id
                 OR ps.id::text = sc.scan_session_id
            WHERE sc.created_at >= now() - ($1 || ' days')::interval
              AND ps.category IS NOT NULL
              AND sc.corrected_category IS NOT NULL
            """,
            str(LOOKBACK_DAYS),
        )

        if not rows:
            logger.info("No scan_corrections in last %dd — nothing to compute", LOOKBACK_DAYS)
            record_run("vision_quality_worker", "ok")
            return {"updated": 0, "skipped": 0}

        # Group by predicted category
        by_predicted: dict[str, list[dict]] = {}
        for r in rows:
            by_predicted.setdefault(r["predicted"], []).append({
                "predicted": r["predicted"],
                "confidence": float(r["confidence"]),
                "corrected": r["corrected"],
            })

        for category, recs in by_predicted.items():
            n = len(recs)
            if n < MIN_SAMPLES_PER_CAT:
                skipped += 1
                continue

            correct = sum(1 for r in recs if r["corrected"] == category)
            accuracy = correct / n if n else 0.0

            # Confidence calibration: avg-confidence on the predictions vs
            # actual accuracy. Factor = accuracy / avg_confidence (clamped).
            # Means: if model says 0.9 but is right 60% of time, downweight.
            avg_conf = sum(r["confidence"] for r in recs) / n
            if avg_conf > 0:
                factor = max(0.5, min(1.2, accuracy / avg_conf))
            else:
                factor = 1.0

            # Top confusion targets — categories users corrected TO most often
            # when model said `category`.
            confusion_counts: dict[str, int] = {}
            for r in recs:
                if r["corrected"] != category:
                    confusion_counts[r["corrected"]] = confusion_counts.get(r["corrected"], 0) + 1
            top = sorted(confusion_counts.items(), key=lambda kv: -kv[1])
            top1 = top[0][0] if top else None
            top2 = top[1][0] if len(top) > 1 else None

            await conn.execute(
                """
                INSERT INTO public.vision_category_quality
                    (category, predicted_accuracy_30d,
                     confidence_calibration_factor,
                     common_confusion_target, common_confusion_secondary,
                     sample_count, computed_at)
                VALUES ($1, $2, $3, $4, $5, $6, now())
                ON CONFLICT (category) DO UPDATE SET
                    predicted_accuracy_30d         = EXCLUDED.predicted_accuracy_30d,
                    confidence_calibration_factor  = EXCLUDED.confidence_calibration_factor,
                    common_confusion_target        = EXCLUDED.common_confusion_target,
                    common_confusion_secondary     = EXCLUDED.common_confusion_secondary,
                    sample_count                   = EXCLUDED.sample_count,
                    computed_at                    = now()
                """,
                category, accuracy, factor, top1, top2, n,
            )
            updated += 1
            logger.info(
                "  %s: n=%d accuracy=%.2f conf_factor=%.2f confusion=%s/%s",
                category, n, accuracy, factor, top1, top2,
            )

        logger.info(
            "vision_quality cycle complete: updated=%d skipped=%d (lookback=%dd, min=%d)",
            updated, skipped, LOOKBACK_DAYS, MIN_SAMPLES_PER_CAT,
        )
        record_run("vision_quality_worker", "ok")
        return {"updated": updated, "skipped": skipped}
    finally:
        await conn.close()


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("vision_quality_worker", "error")
        logger.exception("vision_quality_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
