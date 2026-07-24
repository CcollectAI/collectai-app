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

# Max market_hits fetched (and thus item_refs processed) per cycle. The worker
# was fetching the ENTIRE unprocessed backlog (≈580k rows / 32k refs) and
# trying to value all of it in one pass, blowing past the 1800s bake cycle
# timeout. Bounding it lets each cycle finish green and drains the backlog
# across cycles. Measured throughput is ~12 rows/s (per-group model + DB
# round-trips), so 15k rows ≈ ~20 min — comfortably under the 1800s cap with
# margin for DB load. Env-overridable so it can be tuned without a redeploy.
_MAX_HITS_PER_CYCLE = int(os.getenv("VALUATION_MAX_HITS_PER_CYCLE", "15000"))

_EVIDENCE_LOOKBACK_DAYS = 90

# Temporal decay: half-life in days (listings older than this get exponentially less weight)
_DECAY_HALF_LIFE = 30.0

# Model blending weight when calibration gate passes
_MODEL_BLEND_ALPHA = 0.7

# Model-vs-empirical sanity band. Even a gate-passing model can be degraded —
# _check_gate_pass reads the LATEST calibration_snapshots.gate_pass and a stale
# TRUE row keeps a since-broken model live (2026-07-24: comic_books had a
# 2026-06-30 gate_pass=t row while its artifact had train_mae €33.8k / intercept
# €24.1k and emitted a flat €44k for every item, pinning q50 near €28k
# regardless of the real comps). The empirical q50 here is built from
# >=_MIN_COMPS_FOR_MODEL real sold comps, so it is the trustworthy per-item
# anchor: if the model's central estimate is more than this factor away from it,
# refuse to blend and keep empirical. Unit-agnostic (both EUR), self-calibrating,
# never trips a healthy model (verified 2026-07-24: pokemon/yugioh ratios 0.4-10x
# pass; comic_books 426-4690x and a mispriced yugioh outlier correctly skip).
# Generous on purpose — real items span an order of magnitude (graded vs raw).
_MODEL_SANITY_BAND = 10.0

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


async def _get_latest_picp(conn, category: str) -> float | None:
    """Latest PICP value for a category (None when no snapshot exists).

    PICP = Prediction Interval Coverage Probability — fraction of actual
    sale prices that fall inside the predicted [q10, q90] band. Target
    is 0.80; values 0.70–0.90 are normal in production.

    Used by the conf_score formula to boost categories whose intervals
    have been validated against real sales, and to penalise ones where
    the model is over- or under-confident.
    """
    try:
        row = await conn.fetchrow(
            """
            SELECT picp FROM public.calibration_snapshots
            WHERE category = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            category,
        )
        if row and row["picp"] is not None:
            return float(row["picp"])
        return None
    except Exception:
        return None


# Minimum real comps before we trust the item-level model features enough to
# blend, and before a prediction is treated as more than "estimate only" (V6).
_MIN_COMPS_FOR_MODEL = 3
_MIN_COMPS_RELIABLE = 3
_LOW_COMP_CONF_CAP = 0.5


def _predict_quantile(model: dict, feature_values: dict, coef_key: str = "ridge") -> float | None:
    """Run one Ridge (or quantile-Ridge) head against a REAL feature vector.

    V1: the feature vector is built from the item's actual attributes via the
    shared extractor (`build_feature_vector`), in the artifact's own feature
    order — NOT the old hack of stuffing the empirical median into slot 0.
    V3: `coef_key` selects which head — "ridge" (q50), "ridge_q10", or
    "ridge_q90" — so the trained quantile models are actually consumed instead
    of computed-then-ignored.

    Returns the predicted price in EUR, or None on any failure / out-of-range.
    """
    try:
        sub = model.get(coef_key)
        if not sub or "coef" not in sub:
            return None
        standardizer = model["standardizer"]
        features = model.get("features", [])
        mean = standardizer["mean"]
        std = standardizer["std"]
        coef = sub["coef"]
        intercept = sub["intercept"]

        from app.ml.valuation_features import build_feature_vector
        x = build_feature_vector(features, feature_values)
        if len(x) != len(mean) or len(x) != len(coef):
            # Dimension mismatch (e.g. an older 3-feature artifact vs a newer
            # schema) — skip the model, empirical wins. Safe by construction.
            return None

        # Standardize. std==0 (a feature that was constant in training, e.g. a
        # legacy artifact's rarity/edition) zeroes that term — so feeding it a
        # real value can't destabilize an old model; it just gets ignored.
        x_std = [(x[i] - mean[i]) / std[i] if std[i] > 0 else 0.0 for i in range(len(x))]
        prediction = sum(x_std[i] * coef[i] for i in range(len(x_std))) + intercept

        # math is module-level — do NOT re-import (local import would shadow it
        # and trigger UnboundLocalError on the non-log path).
        if model.get("log_scale"):
            prediction = math.expm1(prediction)  # inverse of log1p

        if not math.isfinite(prediction) or prediction <= 0 or prediction > _MAX_SANE_PRICE_EUR:
            return None
        return float(prediction)
    except Exception:
        return None


@with_async_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
async def run_once():
    if not DSN:
        logging.error("DB_DSN not set in environment")
        return

    # Tagged via application_name so the ExecStop cancel hook
    # (scripts/cancel_bake_queries.py) can identify our backend.
    conn = await asyncpg.connect(
        DSN,
        server_settings={"application_name": "collectai-bake-valuation_worker"},
    )
    logging.info("Connected to DB")
    try:
        # -------------------------------------------------------------------
        # Fetch unprocessed market hits with full detail for evidence building
        # -------------------------------------------------------------------
        # COALESCE(observed_at, seen_at) covers historical rows where
        # writers (pre-2026-05-02) left observed_at NULL. Going forward,
        # both writer paths (marketplace_agent.py + upsert_market_hits_batch
        # RPC) populate observed_at directly. Without this fallback,
        # temporal-decay weighting collapses to a uniform 0.368 weight on
        # ~800K legacy rows.
        # Served by the partial index `idx_market_hits_valuation_queue`
        # (item_ref, seen_at) WHERE processed=false AND is_listing IS NOT TRUE
        # AND price IS NOT NULL AND item_ref IS NOT NULL — its predicate mirrors
        # this WHERE so the planner does a Merge-Append index scan (no seq scan,
        # no global sort) and the LIMIT short-circuits (~0.2s for 30k rows vs a
        # seq-scan+sort that hit the 30s pooler cap → QueryCanceledError, and a
        # full backlog drain that blew past the 1800s bake cycle timeout).
        # ORDER BY mirrors the index (item_ref, seen_at) so rows arrive
        # clustered per item_ref, ascending by recency — preserved for the
        # `reversed(hits)` "most recent condition" pick below. The Python
        # grouping is order-independent and quantiles re-sort by price, so the
        # old COALESCE(observed_at, seen_at) sort key (not indexable) was dead
        # weight. LIMIT bounds per-cycle work so the backlog drains across
        # cycles instead of one cycle trying (and failing) to process it all.
        hit_rows = await conn.fetch("""
            SELECT id, item_ref, source,
                   COALESCE(price_eur, price)::numeric AS price,
                   COALESCE(observed_at, seen_at) AS observed_at,
                   condition, attrs
            FROM public.market_hits
            WHERE processed = false
              AND seen_at > now() - interval '90 days'
              AND price IS NOT NULL
              AND item_ref IS NOT NULL
              AND (is_listing IS NOT TRUE)  -- exclude asking-price rows (Discogs listings)
            ORDER BY item_ref, seen_at
            LIMIT $1
        """, _MAX_HITS_PER_CYCLE)

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
                "condition": row["condition"],
                "attrs": row["attrs"],
            })

        # When we hit the LIMIT, the last item_ref's comps may be truncated at
        # the row boundary. Drop it this cycle so no item is ever valued on a
        # partial comp set (the per-item UPDATE below would otherwise mark all
        # its hits processed). It is fully picked up next cycle. Rows are
        # clustered by item_ref (ORDER BY item_ref), so only the final group
        # can be partial. Keep it if it's the only group (else we'd stall).
        if len(hit_rows) >= _MAX_HITS_PER_CYCLE and len(groups) > 1:
            truncated_ref = next(reversed(groups))
            del groups[truncated_ref]

        logging.info("Found %d item_ref groups to process", len(groups))

        # Per-cycle memo caches. gate-pass and latest-PICP are keyed purely by
        # category (item_ref prefix), but were being fetched once per item_ref
        # — ~2 DB round-trips × 16k groups dominated the cycle time on the
        # pooler. Categories number ~54, so caching collapses ~32k round-trips
        # to ~54. Cleared each run so fresh gate/calibration state is picked up.
        _gate_cache: dict[str, bool] = {}
        _picp_cache: dict[str, float | None] = {}

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
            # Blend the empirical quantiles with the Ridge model when (a) the
            # category's calibration gate passes AND (b) we have enough real
            # comps to trust the item-level feature aggregation (V6). The model
            # is fed REAL features built from the comps' attrs (V1) and its
            # trained q10/q90 heads are actually used (V3).
            model_used = False
            try:
                from app.ml.model_loader import get_active_model
                from app.ml.valuation_features import extract_core_features
                category = item_ref.split(":")[0] if ":" in item_ref else item_ref
                model = await get_active_model(category, routing_key=item_ref)
                if (
                    model and model.get("ridge") and model.get("standardizer")
                    and n >= _MIN_COMPS_FOR_MODEL
                ):
                    if category not in _gate_cache:
                        _gate_cache[category] = await _check_gate_pass(conn, category)
                    gate_pass = _gate_cache[category]
                    alpha = _MODEL_BLEND_ALPHA if gate_pass else 0.0
                    if alpha > 0:
                        # V1: build real feature values from the item's comps.
                        # rarity/edition are item-level (same across listings) →
                        # merge attrs; condition is listing-level → use the most
                        # recent comp's condition as representative.
                        merged_attrs: dict = {}
                        for h in hits:
                            a = h.get("attrs")
                            if isinstance(a, dict):
                                for k, v in a.items():
                                    merged_attrs.setdefault(k, v)
                        rep_condition = next(
                            (h.get("condition") for h in reversed(hits) if h.get("condition")),
                            None,
                        )
                        fv = extract_core_features(rep_condition, merged_attrs)

                        m50 = _predict_quantile(model, fv, "ridge")
                        # Model-vs-empirical sanity band (see _MODEL_SANITY_BAND):
                        # refuse a model whose central estimate is wildly off the
                        # item's own comps, so a degraded-but-still-gated model
                        # falls back to empirical instead of dominating at alpha.
                        if (
                            m50 is not None and q50 and q50 > 0
                            and not (q50 / _MODEL_SANITY_BAND <= m50 <= q50 * _MODEL_SANITY_BAND)
                        ):
                            logging.warning(
                                "valuation: skipping model blend for %s — model q50=%.2f "
                                "outside %.0fx band around empirical q50=%.2f (n=%d)",
                                item_ref, m50, _MODEL_SANITY_BAND, q50, n,
                            )
                            m50 = None
                        if m50 is not None:
                            # V3: blend each quantile head with its empirical
                            # counterpart; fall back to empirical per-head when a
                            # head is missing/invalid.
                            m10 = _predict_quantile(model, fv, "ridge_q10")
                            m90 = _predict_quantile(model, fv, "ridge_q90")
                            b50 = alpha * m50 + (1 - alpha) * q50
                            b10 = alpha * m10 + (1 - alpha) * q10 if m10 is not None else q10
                            b90 = alpha * m90 + (1 - alpha) * q90 if m90 is not None else q90
                            # Enforce monotonicity so the q10<=q50<=q90 CHECK
                            # constraint on price_predictions can't be violated,
                            # even if a head extrapolates out of order.
                            b10, b50, b90 = sorted((b10, b50, b90))
                            if (
                                all(math.isfinite(v) for v in (b10, b50, b90))
                                and 0 < b10 and b90 <= _MAX_SANE_PRICE_EUR
                            ):
                                q10, q50, q90 = b10, b50, b90
                                model_used = True
            except Exception as e:
                logging.debug("Model blending skipped for %s: %s", item_ref, e)

            # ── Confidence score ──────────────────────────────────────────
            # 4 multiplicative factors (all in [0, 1+]):
            #   1. count_factor      — sigmoid in n: 1 - exp(-n/5)
            #                          gives 0.18@n=1, 0.55@n=4, 0.86@n=10.
            #                          Old min(1, n/5) was too punitive on
            #                          tail cats with 1-3 comps (0.2-0.6).
            #   2. diversity_factor  — min(1, unique_sources/2). Old /3
            #                          ceiling was unfair to single-source
            #                          cats (e.g. MTG via tcgplayer alone
            #                          got max 0.33).
            #   3. recency_factor    — average decay weight. Pre-2026-05-02
            #                          observed_at was NULL on all rows so
            #                          this collapsed to exp(-1)=0.368
            #                          everywhere. With the writer fix +
            #                          COALESCE reader, fresh comps push
            #                          this toward 1.0.
            #   4. picp_boost        — clamp(picp/0.8, 0.5, 1.2). Categories
            #                          whose intervals are validated against
            #                          real sales get up to +20%; mis-
            #                          calibrated cats get capped to 0.5.
            #                          NULL when no snapshot → boost=1.0.
            unique_sources = len({h["source"] for h in hits if h["source"]})
            count_factor = 1.0 - math.exp(-n / 5.0)
            diversity_factor = min(1.0, unique_sources / 2.0) if unique_sources > 0 else 0.5
            avg_weight = total_weight / n if n > 0 else 0.5
            recency_factor = min(1.0, avg_weight)

            cat_for_picp = item_ref.split(":")[0] if ":" in item_ref else item_ref
            if cat_for_picp not in _picp_cache:
                _picp_cache[cat_for_picp] = await _get_latest_picp(conn, cat_for_picp)
            picp = _picp_cache[cat_for_picp]
            if picp is None:
                picp_boost = 1.0
            else:
                picp_boost = max(0.5, min(1.2, picp / 0.8))

            confidence_score = round(
                count_factor * diversity_factor * recency_factor * picp_boost,
                4,
            )
            # Cap at 1.0 — picp_boost can push the product above 1.0 for
            # well-calibrated cats with lots of recent diverse comps, but
            # the FE displays this as a percentage so > 1.0 is confusing.
            confidence_score = min(1.0, confidence_score)

            # Synthetic-comp penalty: if every comp for this item is a
            # Claude estimate (no real marketplace data), cap confidence
            # at 0.4. This drives the FE to render an "early access" /
            # "estimate only" badge rather than treating a hallucinated
            # number as a high-confidence prediction. As soon as a single
            # real comp lands (Scrape.do top-up, organic crawl), the cap
            # lifts.
            if all(h.get("source") == "claude_estimate" for h in hits):
                confidence_score = min(confidence_score, 0.4)

            # V6: minimum-comp floor. With fewer than _MIN_COMPS_RELIABLE real
            # comps the quantiles are essentially a point estimate (1 comp →
            # q10=q50=q90), so cap confidence to flag it as "estimate only"
            # rather than letting a thin sample look authoritative.
            if n < _MIN_COMPS_RELIABLE:
                confidence_score = min(confidence_score, _LOW_COMP_CONF_CAP)

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

            # Mark hits as processed. The predicate must mirror the fetch
            # above: `processed = false` so we never rewrite rows that are
            # already true (Postgres rewrites the row even when the value is
            # unchanged — the bare item_ref version re-dirtied EVERY
            # historical row for the ref on EVERY cycle: 1.2M calls / 20M
            # blocks dirtied in pg_stat_statements, the DB's top write-churn
            # query), and the `seen_at` floor so the partitioned table prunes
            # to recent partitions instead of probing all of them per call.
            await conn.execute(
                """
                UPDATE public.market_hits
                SET processed = true
                WHERE item_ref = $1
                  AND processed = false
                  AND seen_at > now() - interval '90 days'
                """,
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
