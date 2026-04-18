#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import datetime
import json
import logging
import math
import os

import asyncpg
from app.worker_registry import record_run
from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [valuation_worker] %(levelname)s: %(message)s",
)

DSN = os.getenv("DB_DSN")

_EVIDENCE_LOOKBACK_DAYS = 90

# Temporal decay: half-life in days (listings older than this get exponentially less weight)
_DECAY_HALF_LIFE = 30.0

# Model blending weight when calibration gate passes
_MODEL_BLEND_ALPHA = 0.7

# Sanity ceiling on predicted prices. Anything above this is almost certainly
# a feature-extraction NaN/Inf or a log-space blow-up (e.g. expm1 on a large
# intercept). Lego Ridge model was emitting €1.5B for 65 items in Apr 2026;
# this clamp drops the model contribution and falls back to empirical.
# 20M euro is the documented grail-tier upper bound (R50f).
_MAX_SANE_PRICE_EUR = 20_000_000.0


def _build_evidence(hits: list[dict]) -> tuple[list[str], dict, str]:
    """
    Build evidence artifacts from a list of market hit dicts.

    Args:
        hits: List of dicts with keys ``id``, ``source``, ``price``,
              ``observed_at``.

    Returns:
        Tuple of (evidence_hit_ids, evidence_summary, explanation_text).
    """
    evidence_hit_ids: list[str] = [str(h["id"]) for h in hits]

    # Group by source
    source_groups: dict[str, list[dict]] = {}
    for h in hits:
        src = h["source"] or "unknown"
        source_groups.setdefault(src, []).append(h)

    source_summaries: list[dict] = []
    for src, group in sorted(source_groups.items()):
        prices = [float(g["price"]) for g in group]
        dates = [g["observed_at"] for g in group if g["observed_at"] is not None]
        avg_price = round(sum(prices) / len(prices), 2)

        date_range = None
        if dates:
            earliest = min(dates).strftime("%Y-%m-%d")
            latest = max(dates).strftime("%Y-%m-%d")
            date_range = f"{earliest} to {latest}" if earliest != latest else earliest

        source_summaries.append({
            "source": src,
            "count": len(group),
            "avg_price": avg_price,
            "date_range": date_range,
        })

    evidence_summary = {
        "sources": source_summaries,
        "total_comps": len(hits),
    }

    # Human-readable explanation
    _SOURCE_NAMES = {
        "ebay": "eBay sold",
        "tcgplayer": "TCGPlayer",
        "cardmarket": "Cardmarket",
        "mercari": "Mercari",
        "amazon": "Amazon",
        "catawiki": "Catawiki",
        "vinted": "Vinted",
        "stockx": "StockX",
        "discogs": "Discogs",
    }
    parts: list[str] = []
    for s in source_summaries:
        src_label = _SOURCE_NAMES.get(s["source"].lower(), s["source"].replace("_", " ").title())
        parts.append(
            f"{s['count']} {src_label} listing{'s' if s['count'] != 1 else ''} "
            f"(avg \u20ac{s['avg_price']:.2f})"
        )

    explanation_text = (
        f"Based on {' and '.join(parts)} "
        f"over the last {_EVIDENCE_LOOKBACK_DAYS} days."
    )

    return evidence_hit_ids, evidence_summary, explanation_text


async def _check_gate_pass(conn, category: str) -> bool:
    """Check if the latest calibration snapshot for a category has gate_pass=True."""
    try:
        row = await conn.fetchrow(
            """
            SELECT gate_pass FROM public.calibration_snapshots
            WHERE category = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            category,
        )
        return bool(row and row["gate_pass"])
    except Exception:
        return False


def _predict_ridge(model: dict, item_ref: str, fallback_q50: float) -> float | None:
    """Run Ridge model inference to get a q50 prediction.

    Uses the model artifact's standardizer and ridge coefficients.
    Returns predicted value or None on failure.
    """
    try:
        standardizer = model["standardizer"]
        ridge = model["ridge"]
        features = model.get("features", [])
        mean = standardizer["mean"]
        std = standardizer["std"]
        coef = ridge["coef"]
        intercept = ridge["intercept"]

        # Build a simple feature vector using the empirical q50 as the primary feature
        # The Ridge model expects standardized features
        x = [fallback_q50] + [0.0] * (len(features) - 1)
        if len(x) != len(mean) or len(x) != len(coef):
            return None

        # Standardize
        x_std = [(x[i] - mean[i]) / std[i] if std[i] > 0 else 0.0 for i in range(len(x))]

        # Predict
        prediction = sum(x_std[i] * coef[i] for i in range(len(x_std))) + intercept

        # If model was trained on log-scale, convert back to EUR
        # (math is imported at module level — do NOT re-import here, as a local
        # `import math` makes the name function-local and shadows module-level
        # for the non-log path, triggering UnboundLocalError).
        if model.get("log_scale"):
            prediction = math.expm1(prediction)  # exp(x) - 1, inverse of log1p

        if not math.isfinite(prediction):
            return None
        if prediction <= 0:
            return None
        if prediction > _MAX_SANE_PRICE_EUR:
            # Log-space blow-up or feature NaN — drop model, empirical wins
            return None
        return float(prediction)
    except Exception:
        return None


@with_async_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
async def run_once():
    if not DSN:
        logging.error("DB_DSN not set in environment")
        return

    conn = await asyncpg.connect(DSN)
    logging.info("Connected to DB")
    try:
        # -------------------------------------------------------------------
        # Fetch unprocessed market hits with full detail for evidence building
        # -------------------------------------------------------------------
        hit_rows = await conn.fetch("""
            SELECT id, item_ref, source, COALESCE(price_eur, price)::numeric AS price, observed_at
            FROM public.market_hits
            WHERE processed = false
              AND price IS NOT NULL
              AND item_ref IS NOT NULL
              AND (is_listing IS NOT TRUE)  -- exclude asking-price rows (Discogs listings)
            ORDER BY item_ref, observed_at
        """)

        if not hit_rows:
            logging.info("No unprocessed market_hits found")
            return

        # Group by item_ref
        groups: dict[str, list[dict]] = {}
        for row in hit_rows:
            ref = row["item_ref"]
            groups.setdefault(ref, []).append({
                "id": row["id"],
                "source": row["source"],
                "price": row["price"],
                "observed_at": row["observed_at"],
            })

        logging.info("Found %d item_ref groups to process", len(groups))

        for item_ref, hits in groups.items():
            now = datetime.datetime.now(datetime.timezone.utc)

            # ── Temporal decay weighting ──────────────────────────────────
            weighted_prices = []
            weights = []
            for h in hits:
                price = float(h["price"])
                observed = h["observed_at"]
                if observed is not None:
                    days_old = max(0, (now - observed).total_seconds() / 86400)
                else:
                    days_old = _DECAY_HALF_LIFE  # assume moderate age if unknown
                weight = math.exp(-days_old / _DECAY_HALF_LIFE)
                weighted_prices.append((price, weight))
                weights.append(weight)

            if not weighted_prices:
                logging.warning("No valid prices for item_ref=%s, skipping", item_ref)
                continue

            # Sort by price for weighted quantile computation
            weighted_prices.sort(key=lambda pw: pw[0])
            total_weight = sum(w for _, w in weighted_prices)

            def weighted_quantile(p: float) -> float:
                """Compute weighted quantile at percentile p in [0,1]."""
                if total_weight <= 0:
                    return weighted_prices[len(weighted_prices) // 2][0]
                cumulative = 0.0
                target = p * total_weight
                for price, w in weighted_prices:
                    cumulative += w
                    if cumulative >= target:
                        return price
                return weighted_prices[-1][0]

            q10 = weighted_quantile(0.10)
            q50 = weighted_quantile(0.50)
            q90 = weighted_quantile(0.90)

            n = len(weighted_prices)

            # ── Model blending ────────────────────────────────────────────
            # Try to blend with Ridge model prediction if available
            model_used = False
            try:
                from app.ml.model_loader import get_active_model
                category = item_ref.split(":")[0] if ":" in item_ref else item_ref
                model = await get_active_model(category, routing_key=item_ref)
                if model and model.get("ridge") and model.get("standardizer"):
                    # Check calibration gate_pass
                    gate_pass = await _check_gate_pass(conn, category)
                    alpha = _MODEL_BLEND_ALPHA if gate_pass else 0.0
                    if alpha > 0:
                        model_q50 = _predict_ridge(model, item_ref, q50)
                        if model_q50 is not None:
                            blended = alpha * model_q50 + (1 - alpha) * q50
                            if math.isfinite(blended) and 0 < blended <= _MAX_SANE_PRICE_EUR:
                                q50 = blended
                                model_used = True
            except Exception as e:
                logging.debug("Model blending skipped for %s: %s", item_ref, e)

            # ── Confidence score ──────────────────────────────────────────
            # conf = min(1.0, source_count/5) × source_diversity × recency
            unique_sources = len({h["source"] for h in hits if h["source"]})
            source_diversity = min(1.0, unique_sources / 3)
            source_count_factor = min(1.0, n / 5)
            # Recency: average weight (closer to 1.0 = more recent data)
            avg_weight = total_weight / n if n > 0 else 0.5
            recency_factor = min(1.0, avg_weight)
            confidence_score = round(source_count_factor * source_diversity * recency_factor, 4)

            # Build evidence artifacts
            evidence_hit_ids, evidence_summary, explanation_text = _build_evidence(hits)
            if model_used:
                explanation_text += " Model-blended prediction applied."

            logging.info(
                "item_ref=%s n=%d q10=%.2f q50=%.2f q90=%.2f conf=%.3f comps=%d model=%s",
                item_ref, n, q10, q50, q90, confidence_score, len(evidence_hit_ids),
                "blended" if model_used else "empirical",
            )

            # ---------------------------------------------------------------
            # INSERT price prediction with evidence + confidence
            # ---------------------------------------------------------------
            category = item_ref.split(":")[0] if ":" in item_ref else None
            await conn.execute(
                """
                INSERT INTO public.price_predictions
                    (item_ref, category, q10, q50, q90, generated_at,
                     evidence_hit_ids, evidence_summary, explanation,
                     conf_score)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10)
                """,
                item_ref,
                category,
                q10,
                q50,
                q90,
                now,
                evidence_hit_ids,
                json.dumps(evidence_summary),
                explanation_text,
                confidence_score,
            )

            # ---------------------------------------------------------------
            # INSERT price history snapshot for anomaly detection (Task 3)
            # ---------------------------------------------------------------
            await conn.execute(
                """
                INSERT INTO public.price_history
                    (item_ref, price_q50, price_q10, price_q90, source, snapshot_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                item_ref,
                q50,
                q10,
                q90,
                "valuation_worker",
                now,
            )

            # Mark hits as processed
            await conn.execute(
                "UPDATE public.market_hits SET processed = true WHERE item_ref = $1",
                item_ref,
            )

        logging.info("Done valuation cycle")
    finally:
        await conn.close()
    record_run("valuation_worker", "ok")


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("valuation_worker", "error")
        log_dead_letter("valuation_worker", {}, e)
        logging.exception("valuation_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
