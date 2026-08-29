#!/usr/bin/env python3
"""Model retrain worker — weekly pipeline to refresh ML pricing models from live data.

Exports recent market_hits (last 90 days) to JSONL training data per category,
merges with static seed data and user feedback, then retrains Ridge models
using the existing train_price.py pipeline.

This closes the data loop:
  catalog_crawler_worker → market_hits → model_retrain_worker → fresh models
  → valuation_worker uses blended predictions with higher confidence

Configuration via environment variables:
  MODEL_RETRAIN_LOOKBACK_DAYS  — how far back to pull market_hits (default 90)
  MODEL_RETRAIN_MIN_SAMPLES    — minimum sold comps to retrain a category (default 20)
  DB_DSN                       — database connection string
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any
from datetime import datetime, timezone, timedelta
from pathlib import Path

import asyncpg

from app.worker_registry import record_run
from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [model_retrain] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")

LOOKBACK_DAYS = int(os.getenv("MODEL_RETRAIN_LOOKBACK_DAYS", "90"))
MIN_SAMPLES = int(os.getenv("MODEL_RETRAIN_MIN_SAMPLES", "20"))

# All supported categories (matches train_price.py)
ALL_CATEGORIES = [
    "pokemon", "mtg", "yugioh", "lorcana", "digimon", "one_piece_tcg",
    "funko", "designer_toys", "anime_figures", "hot_toys",
    "action_figures", "vintage_toys", "marvel_legends",
    "lego", "gunpla", "scale_models", "warhammer", "retro_games",
    "manga", "comic_books", "bluray_steelbook", "anime_bluray", "anime_soundtrack",
    "anime_ost_vinyl", "kpop_merch",
    "taylor_swift", "pop_fandom", "kpop_lightsticks", "disney", "theme_park", "ghibli",
    "bandai_premium", "jp_magazine", "jp_event", "nintendo_merch", "retro_pokemon",
    "one_piece", "vtuber", "keycaps", "loungefly",
    "vinyl_records", "sneakers", "watches",
    "blind_box", "plush_collectibles", "whiskey", "vintage_cameras", "pens",
    "diecast", "sportscards", "retro_handhelds",
    "oop_board_games", "city_pop_vinyl", "fragrances",
]

# Data directory (relative to server/)
DATA_DIR = Path("data")


def _price_to_features(price: float, condition: str | None, is_sold: bool,
                       attrs: Any = None) -> dict:
    """Convert a market_hit row into training features.

    V2: rarity_score and edition_score used to be hardcoded to 0.5 for EVERY
    row, so the model could only ever learn from condition_score (3 of 3
    features were 2/3 constant). Now they're derived from the row's `attrs`
    via the SAME shared extractor the serving path uses (app.ml.valuation_features),
    so train-time and serve-time features stay in lockstep.
    """
    from app.ml.valuation_features import extract_core_features
    return extract_core_features(condition, attrs)


async def _export_market_hits_to_jsonl(conn, category: str, cutoff: datetime) -> int:
    """Export recent market_hits for a category to JSONL training format.

    Returns number of observations written.
    """
    # R46.14 — column rename to match this DB's market_hits schema:
    #   features_json → attrs   (jsonb column added by an older migration)
    #   created_at    → seen_at (legacy timestamp on market_hits)
    rows = await conn.fetch(
        """
        SELECT price, condition, attrs
        FROM public.market_hits
        WHERE normalized_key LIKE $1
          AND price IS NOT NULL
          AND price > 0
          AND seen_at >= $2
          AND (is_listing IS NOT TRUE)
        ORDER BY seen_at DESC
        LIMIT 5000
        """,
        f"{category}:%",
        cutoff,
    )

    if not rows:
        return 0

    # Ensure data directory exists
    cat_dir = DATA_DIR / category
    cat_dir.mkdir(parents=True, exist_ok=True)

    # Write to a separate live-data JSONL file (don't overwrite static seed data)
    live_path = cat_dir / "train_live.jsonl"

    count = 0
    with open(live_path, "w") as f:
        for row in rows:
            price = float(row["price"])
            condition = row["condition"]

            # Extract is_sold from attrs jsonb if available
            attrs = row["attrs"]
            is_sold = False
            if isinstance(attrs, dict):
                is_sold = attrs.get("is_sold", False)
            elif isinstance(attrs, str):
                try:
                    fj = json.loads(attrs)
                    is_sold = fj.get("is_sold", False)
                except (json.JSONDecodeError, TypeError):
                    pass

            features = _price_to_features(price, condition, is_sold, attrs)
            record = {"features": features, "price": round(price, 2)}
            f.write(json.dumps(record) + "\n")
            count += 1

    logger.info("Exported %d market_hits to %s", count, live_path)
    return count


async def _export_ground_truths(conn, category: str, cutoff: datetime) -> int:
    """Export verified sales and price ground truths to training data.

    Ground truth data gets 2x weight (written twice) since it's the highest
    quality pricing signal.
    """
    # Verified sales from users
    rows = await conn.fetch(
        """
        SELECT sale_price, condition
        FROM public.verified_sales
        WHERE category = $1
          AND sale_price > 0
          AND created_at >= $2
        ORDER BY created_at DESC
        LIMIT 1000
        """,
        category,
        cutoff,
    )

    # Price ground truths from Deal Desk completed offers
    gt_rows = await conn.fetch(
        """
        SELECT actual_price, 'Good' AS condition
        FROM public.price_ground_truths
        WHERE item_id IN (
            SELECT id FROM public.items WHERE category = $1
        )
        AND actual_price > 0
        AND recorded_at >= $2
        LIMIT 500
        """,
        category,
        cutoff,
    )

    all_rows = list(rows) + list(gt_rows)
    if not all_rows:
        return 0

    cat_dir = DATA_DIR / category
    cat_dir.mkdir(parents=True, exist_ok=True)

    gt_path = cat_dir / "train_ground_truth.jsonl"
    count = 0

    with open(gt_path, "w") as f:
        for row in all_rows:
            price_field = "sale_price" if "sale_price" in row.keys() else "actual_price"
            price = float(row[price_field])
            condition = row.get("condition")
            features = _price_to_features(price, condition, True)
            record = {"features": features, "price": round(price, 2)}
            line = json.dumps(record) + "\n"
            # Write twice for 2x weight (ground truth is highest quality)
            f.write(line)
            f.write(line)
            count += 2

    logger.info("Exported %d ground truth observations for %s", count, category)
    return count


async def _export_scan_corrections(conn, category: str, cutoff: datetime) -> int:
    """Export user scan corrections to training data.

    Scan corrections represent user-verified category/condition assignments.
    Weight = user_weight × regret_multiplier where:
      - user_weight: level≥10 users contribute 2× (existing).
      - regret_multiplier: from vision_category_regret table — categories
        with high AI-error rates get up to 3× weight on corrections so the
        model learns failure modes faster (added 2026-04-26 by
        vision_regret_worker; falls back to 1.0× when table absent).
    """
    rows = await conn.fetch(
        """
        SELECT corrected_name, corrected_category, corrected_condition, user_weight
        FROM public.scan_corrections
        WHERE corrected_category = $1
          AND created_at >= $2
        ORDER BY created_at DESC
        LIMIT 1000
        """,
        category,
        cutoff,
    )

    if not rows:
        return 0

    # Look up the per-category regret multiplier (best-effort; defaults to 1×).
    # Formula: 1 + regret_rate * 2  → maps [0.0, 1.0] → [1×, 3×].
    regret_multiplier = 1.0
    try:
        row = await conn.fetchrow(
            "SELECT regret_rate_30d FROM public.vision_category_regret WHERE category = $1",
            category,
        )
        if row and row["regret_rate_30d"] is not None:
            regret_multiplier = 1.0 + float(row["regret_rate_30d"]) * 2.0
    except Exception as e:
        logger.debug("[model_retrain] regret lookup failed for %s: %s", category, e)

    cat_dir = DATA_DIR / category
    cat_dir.mkdir(parents=True, exist_ok=True)

    corrections_path = cat_dir / "train_corrections.jsonl"
    count = 0

    with open(corrections_path, "w") as f:
        for row in rows:
            condition = row["corrected_condition"]
            user_weight = float(row["user_weight"] or 1.0)
            features = _price_to_features(0, condition, False)
            record = {"features": features, "price": 0, "correction": True}
            line = json.dumps(record) + "\n"
            # Combined weight = user_weight × regret_multiplier
            repeat = max(1, int(round(user_weight * regret_multiplier)))
            for _ in range(repeat):
                f.write(line)
                count += 1

    logger.info(
        "Exported %d scan correction observations for %s (regret_x=%.2f)",
        count, category, regret_multiplier,
    )
    return count


HOLDOUT_FRACTION = float(os.getenv("MODEL_RETRAIN_HOLDOUT_FRAC", "0.20"))
PROMOTION_TOLERANCE = float(os.getenv("MODEL_RETRAIN_TOLERANCE", "1.05"))  # new MAE allowed up to 5% worse

# Minimum holdout before the gate is allowed to REVERT a freshly trained model.
#
# The 2026-08-29 run exposed the rule as incoherent: 53 categories had
# holdout_n=0 and were ALL promoted ("no_holdout — first train or empty
# ground_truth"), while lorcana had holdout_n=3 and was REVERTED on
# new_mae=24.23 > old_mae=2.82 * 1.05. Zero evidence promoted; three samples
# rejected. The gate was strictly more permissive the less it knew, and an
# 8.6x MAE ratio measured on three points is noise, not a finding.
#
# The evidence base cannot grow on its own: `price_ground_truths` holds NINE
# rows in total, and docs/ARCHITECTURE.md:838 records why — it fills only when
# a real user marks an item sold, and there are no users yet. So this will keep
# biting until launch.
#
# Below this threshold the gate promotes (consistent with the n=0 path) and
# logs the numbers at WARNING. Declining to ACT on a weak signal is not the
# same as discarding it.
MIN_HOLDOUT_FOR_GATE = int(os.getenv("MODEL_RETRAIN_MIN_HOLDOUT", "20"))


def should_revert(old_mae: float | None, new_mae: float | None,
                  holdout_n: int, tolerance: float = PROMOTION_TOLERANCE
                  ) -> tuple[bool, str]:
    """Decide whether to revert to the previous model. Returns (revert, reason).

    Pure and module-level so the rule can be tested against known-good and
    known-bad inputs -- inline in retrain_category it could only be verified by
    reading it, which is how the n=0-promotes / n=3-rejects inversion survived.
    """
    if old_mae is None or new_mae is None or holdout_n <= 0:
        return False, "no_holdout — first train or empty ground_truth"
    if holdout_n < MIN_HOLDOUT_FOR_GATE:
        return False, (
            f"insufficient holdout (n={holdout_n} < {MIN_HOLDOUT_FOR_GATE}) — "
            f"promoted unevaluated; new_mae={new_mae:.2f} vs "
            f"old_mae={old_mae:.2f} recorded but NOT acted on"
        )
    if new_mae > old_mae * tolerance:
        return True, (
            f"regression: new_mae={new_mae:.2f} > old_mae={old_mae:.2f}"
            f" * tol={tolerance} (holdout n={holdout_n})"
        )
    return False, f"promoted: new_mae={new_mae:.2f} vs old_mae={old_mae:.2f} (n={holdout_n})"


def _score_model_on_holdout(model_artifact: dict, holdout_records: list[dict]) -> float | None:
    """Score a model artifact's q50 MAE on a list of {features, price} dicts.

    Returns mean abs error in the model's training scale (price units), or None
    if the artifact is missing required fields. Uses the same standardize +
    ridge.coef·x + intercept logic as valuation_worker._predict_ridge but with
    the FULL feature vector (not just the empirical fallback).
    """
    try:
        feats = model_artifact.get("features") or []
        std_block = model_artifact.get("standardizer") or {}
        ridge = model_artifact.get("ridge") or {}
        mean = std_block.get("mean") or []
        std = std_block.get("std") or []
        coef = ridge.get("coef") or []
        intercept = float(ridge.get("intercept") or 0.0)
        log_scale = bool(model_artifact.get("log_scale"))
        if not feats or not coef or len(feats) != len(coef):
            return None
        import math as _math
        errors = []
        for rec in holdout_records:
            x = [float((rec.get("features") or {}).get(name, 0.0)) for name in feats]
            x_std = [
                (x[i] - mean[i]) / std[i] if i < len(std) and std[i] > 0 else 0.0
                for i in range(len(x))
            ]
            pred = sum(x_std[i] * coef[i] for i in range(len(x_std))) + intercept
            if log_scale:
                pred = _math.expm1(pred)
            actual = float(rec.get("price", 0.0))
            if not _math.isfinite(pred) or pred <= 0 or actual <= 0:
                continue
            errors.append(abs(pred - actual))
        if not errors:
            return None
        return sum(errors) / len(errors)
    except Exception as e:
        logger.debug("[model_retrain] _score_model_on_holdout failed: %s", e)
        return None


async def _ensure_promotion_log_table() -> None:
    """Create model_promotion_log on first run (idempotent)."""
    if not DSN:
        return
    conn = await asyncpg.connect(DSN)
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS public.model_promotion_log (
                id              bigserial PRIMARY KEY,
                category        text NOT NULL,
                old_version     text,
                new_version     text NOT NULL,
                old_mae         numeric,
                new_mae         numeric,
                holdout_n       integer,
                promoted        boolean NOT NULL,
                reason          text,
                -- `created_at`, NOT `decided_at`. The live table has shipped
                -- with created_at since it was first created, and
                -- CREATE TABLE IF NOT EXISTS is NAME-idempotent, not
                -- SHAPE-idempotent: it saw the table, no-opped, and never
                -- reconciled the column. The CREATE INDEX below then failed on
                -- `column "decided_at" does not exist` on every run, logged as
                -- "_ensure_promotion_log_table failed" — which reads as "the
                -- promotion log is broken" when in fact only the index was
                -- missing and all 54 rows of the 2026-08-29 run landed fine.
                -- See learning_create_if_not_exists_silently_noops.
                created_at      timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_model_promotion_log_created_at "
            "ON public.model_promotion_log (created_at DESC)"
        )
    finally:
        await conn.close()


async def _log_promotion(
    category: str, old_version: str | None, new_version: str,
    old_mae: float | None, new_mae: float | None, holdout_n: int,
    promoted: bool, reason: str,
) -> None:
    if not DSN:
        return
    try:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                """
                INSERT INTO public.model_promotion_log
                    (category, old_version, new_version, old_mae, new_mae,
                     holdout_n, promoted, reason)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                category, old_version, new_version, old_mae, new_mae,
                holdout_n, promoted, reason,
            )
        finally:
            await conn.close()
    except Exception as e:
        logger.debug("[model_retrain] _log_promotion failed: %s", e)


def _log_promotion_sync(
    category: str, old_version: str | None, new_version: str,
    old_mae: float | None, new_mae: float | None, holdout_n: int,
    promoted: bool, reason: str,
) -> None:
    """Synchronous promotion-log write.

    V9: the old code called `asyncio.get_event_loop().run_until_complete(...)`
    from inside `_retrain_category`, which runs DIRECTLY in the worker's already
    -running event loop — so it raised RuntimeError every time and the promotion
    log was NEVER written. _retrain_category is sync, so write synchronously via
    psycopg2 (same pattern as the vision_quality cache) instead.
    """
    if not DSN:
        return
    try:
        import psycopg2
        conn = psycopg2.connect(DSN)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO public.model_promotion_log
                    (category, old_version, new_version, old_mae, new_mae,
                     holdout_n, promoted, reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (category, old_version, new_version, old_mae, new_mae,
                 holdout_n, promoted, reason),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.debug("[model_retrain] _log_promotion_sync failed: %s", e)


def _retrain_category(category: str) -> dict:
    """Retrain Ridge model for `category` with holdout-gated promotion.

    Flow:
      1. Read all training records from data/{category}/*.jsonl.
      2. Hold back HOLDOUT_FRACTION of train_ground_truth.jsonl (most recent —
         these come from verified_sales/price_ground_truths and are the highest-
         quality reflection of production reality).
      3. Score the CURRENT artifacts/{category}/active model on the holdout.
      4. Truncate train_ground_truth.jsonl to non-holdout subset, run
         train_category — writes new artifact + flips symlink.
      5. Score the new model on the same holdout.
      6. If new_mae > old_mae * PROMOTION_TOLERANCE: revert symlink to the
         previous version (atomic os.replace via _restore_active_symlink).
      7. Restore train_ground_truth.jsonl to full (so next cycle uses all data).
      8. Write a row to model_promotion_log for ops visibility.
    """
    cat_dir = DATA_DIR / category

    # Collect all training data (for the MIN_SAMPLES gate)
    all_prices: list[float] = []
    for jsonl_file in ["train.jsonl", "train_live.jsonl", "train_ground_truth.jsonl", "train_corrections.jsonl"]:
        path = cat_dir / jsonl_file
        if not path.exists():
            continue
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    all_prices.append(float(record["price"]))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

    if len(all_prices) < MIN_SAMPLES:
        logger.info(
            "Category %s has %d samples (min %d) — skipping retrain",
            category, len(all_prices), MIN_SAMPLES,
        )
        return {"category": category, "status": "skipped", "samples": len(all_prices)}

    # ── Hold out the most-recent N records from train_ground_truth.jsonl ──
    gt_path = cat_dir / "train_ground_truth.jsonl"
    holdout_records: list[dict] = []
    train_records: list[dict] = []
    gt_full_lines: list[str] = []
    if gt_path.exists():
        with open(gt_path) as f:
            gt_full_lines = [ln for ln in f if ln.strip()]
        n_total = len(gt_full_lines)
        # _export_ground_truths writes newest-first (ORDER BY created_at DESC),
        # so the LEADING slice is the most-recent.
        n_holdout = max(0, int(n_total * HOLDOUT_FRACTION))
        for ln in gt_full_lines[:n_holdout]:
            try:
                holdout_records.append(json.loads(ln))
            except Exception:
                pass
        for ln in gt_full_lines[n_holdout:]:
            try:
                train_records.append(json.loads(ln))
            except Exception:
                pass
        # Truncate gt file to non-holdout for this train cycle
        if holdout_records:
            with open(gt_path, "w") as f:
                f.writelines(gt_full_lines[n_holdout:])

    # V10: the gt file is now truncated. Guarantee it is restored to full no
    # matter how the rest of this cycle exits (success, early return, or an
    # uncaught exception in scoring/promotion) via try/finally. The old code
    # only restored on the train try/except + success path, so a crash in
    # between left the holdout permanently deleted from training data.
    def _restore_gt() -> None:
        if gt_full_lines and holdout_records:
            try:
                with open(gt_path, "w") as f:
                    f.writelines(gt_full_lines)
            except Exception as e:
                logger.warning("[model_retrain] restore gt file failed for %s: %s", category, e)

    # Capture current active version + load it for scoring
    from app.ml.model_loader import _load_artifact_from_disk, _resolve_artifacts_root
    artifacts_root = _resolve_artifacts_root()
    old_version: str | None = None
    old_mae: float | None = None
    new_version: str | None = None
    new_mae: float | None = None
    promoted = True
    reason = "promoted"
    try:
        if artifacts_root:
            active_link = artifacts_root / category / "active"
            if active_link.is_symlink():
                old_version = os.readlink(str(active_link))
            old_artifact = _load_artifact_from_disk(category, slot="active")
            if old_artifact and holdout_records:
                old_mae = _score_model_on_holdout(old_artifact, holdout_records)

        # ── Train new model (writes artifact + flips symlink) ──
        try:
            from pipelines.train_price import train_category
            result = train_category(category)
            new_version = result.get("version")
            logger.info(
                "Retrained %s: samples=%d cv_mae=%.2f",
                category, len(all_prices), result.get("cv_mae", -1),
            )
        except ImportError:
            logger.info("train_category not importable, using CLI fallback for %s", category)
            return _retrain_via_cli(category, len(all_prices))
        except Exception as e:
            logger.warning("Retrain failed for %s: %s", category, e)
            return {"category": category, "status": "error", "error": str(e)[:200]}

        # ── Score new model on the same holdout ──
        if holdout_records:
            new_artifact = _load_artifact_from_disk(category, slot="active")
            if new_artifact:
                new_mae = _score_model_on_holdout(new_artifact, holdout_records)

        # ── Promotion gate ──
        # The rule lives in should_revert() so it can be tested; see the
        # MIN_HOLDOUT_FOR_GATE comment for why n=3 must not revert while n=0
        # promotes.
        _revert, _gate_reason = should_revert(old_mae, new_mae, len(holdout_records))
        if _revert and not (old_version and artifacts_root):
            # We would revert but cannot — say so instead of silently promoting.
            logger.warning(
                "[model_retrain] %s: %s — but no previous version to revert to; "
                "the new model stands", category, _gate_reason)
            _revert = False
        if not _revert and _gate_reason.startswith("insufficient holdout"):
            logger.warning("[model_retrain] %s: %s", category, _gate_reason)
        if _revert:
            try:
                active_link = artifacts_root / category / "active"
                if active_link.is_symlink():
                    active_link.unlink()
                active_link.symlink_to(old_version)
                promoted = False
                reason = f"{_gate_reason} — reverted to {old_version}"
                logger.warning("[model_retrain] %s: %s", category, reason)
            except Exception as e:
                logger.warning("[model_retrain] revert symlink failed for %s: %s", category, e)
                reason = f"regression detected but revert FAILED: {e}"
        elif old_mae is None or new_mae is None:
            reason = "no_holdout — first train or empty ground_truth"
    finally:
        _restore_gt()

    # ── Log to model_promotion_log (best-effort, synchronous) ──
    # V9: was run_until_complete() on the already-running loop → always raised
    # → log never written. Synchronous psycopg2 write works from this sync fn.
    _log_promotion_sync(
        category, old_version, new_version or "?",
        old_mae, new_mae, len(holdout_records), promoted, reason,
    )

    return {
        "category": category,
        "status": "ok" if promoted else "skipped_regression",
        "samples": len(all_prices),
        "old_version": old_version,
        "new_version": new_version,
        "old_mae": old_mae,
        "new_mae": new_mae,
        "holdout_n": len(holdout_records),
        "promoted": promoted,
        "reason": reason,
    }


def _retrain_via_cli(category: str, sample_count: int) -> dict:
    """Fallback: retrain via subprocess calling train_price.py."""
    import subprocess
    try:
        result = subprocess.run(
            ["python", "-m", "pipelines.train_price", "--category", category],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(Path(__file__).parent.parent),
        )
        if result.returncode == 0:
            return {"category": category, "status": "ok", "samples": sample_count}
        else:
            return {
                "category": category,
                "status": "error",
                "error": result.stderr[:200],
            }
    except Exception as e:
        return {"category": category, "status": "error", "error": str(e)[:200]}


@with_async_retry(max_retries=2, base_delay=10.0, max_delay=120.0)
async def run_once():
    """Execute a single model retraining cycle."""
    if not DSN:
        logger.error("DB_DSN not set in environment")
        record_run("model_retrain_worker", "error")
        return

    conn = await asyncpg.connect(DSN)
    logger.info("Connected to DB — starting model retrain cycle")

    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

    try:
        # R46.14 — pre-flight check tables ONCE so we don't log a warning
        # per-category for missing dependent tables. Also wrap each export
        # in try/except for safety against per-row issues.
        async def _table_exists(name: str) -> bool:
            try:
                return bool(await conn.fetchval(
                    "SELECT to_regclass($1) IS NOT NULL", f"public.{name}"
                ))
            except Exception:
                return False

        has_verified_sales = await _table_exists("verified_sales")
        has_price_ground_truths = await _table_exists("price_ground_truths")
        has_scan_corrections = await _table_exists("scan_corrections")
        if not has_scan_corrections:
            logger.info("[model_retrain] scan_corrections table missing — skipping that export type")
        if not has_verified_sales:
            logger.info("[model_retrain] verified_sales table missing — skipping that export type")
        if not has_price_ground_truths:
            logger.info("[model_retrain] price_ground_truths table missing — skipping that export type")

        async def _safe_export(fn, name, *args):
            try:
                return await fn(*args)
            except Exception as exc:
                logger.debug(
                    "[model_retrain] %s export error: %s: %s",
                    name, type(exc).__name__, str(exc)[:80],
                )
                return 0

        # Phase 1: Export market_hits + ground truths per category
        export_stats = {}
        for category in ALL_CATEGORIES:
            hits_count = await _safe_export(_export_market_hits_to_jsonl, "market_hits", conn, category, cutoff)
            gt_count = (
                await _safe_export(_export_ground_truths, "ground_truths", conn, category, cutoff)
                if has_price_ground_truths or has_verified_sales else 0
            )
            corr_count = (
                await _safe_export(_export_scan_corrections, "scan_corrections", conn, category, cutoff)
                if has_scan_corrections else 0
            )
            export_stats[category] = {
                "market_hits": hits_count,
                "ground_truths": gt_count,
                "scan_corrections": corr_count,
                "total": hits_count + gt_count + corr_count,
            }

        total_exported = sum(s["total"] for s in export_stats.values())
        categories_with_data = sum(1 for s in export_stats.values() if s["total"] > 0)
        logger.info(
            "Phase 1 complete: exported %d observations across %d categories",
            total_exported, categories_with_data,
        )

    finally:
        await conn.close()

    # Phase 2: Retrain models (doesn't need persistent DB connection)
    # Ensure the promotion log table exists once before per-category loop
    try:
        await _ensure_promotion_log_table()
    except Exception as e:
        # Say what actually broke. The INSERTs name their columns explicitly
        # and rely on the timestamp default, so promotion logging survives a
        # failure here — the old message implied the opposite.
        logger.warning(
            "[model_retrain] promotion-log table/index setup failed (%s); "
            "promotion decisions are still logged, the index may be missing", e)

    retrain_results = []
    promoted_count = 0
    regression_skipped_count = 0
    insufficient_skip_count = 0
    error_count = 0

    for category in ALL_CATEGORIES:
        result = _retrain_category(category)
        retrain_results.append(result)
        st = result["status"]
        if st == "ok":
            promoted_count += 1
        elif st == "skipped_regression":
            regression_skipped_count += 1
        elif st == "skipped":
            insufficient_skip_count += 1
        else:
            error_count += 1

    logger.info(
        "Model retrain cycle complete: promoted=%d regression_skipped=%d "
        "insufficient_data=%d errors=%d (total=%d categories)",
        promoted_count, regression_skipped_count,
        insufficient_skip_count, error_count, len(ALL_CATEGORIES),
    )

    # V4: surface any active models that are now stale (retrain silently
    # failing / a category stuck below MIN_SAMPLES for weeks). Logged greppably
    # as MODEL_STALE rather than paged, to avoid alarm fatigue on legitimately
    # low-data categories. Runs weekly with the retrain cycle — the right
    # cadence to notice a model that stopped refreshing.
    try:
        from app.ml.model_loader import stale_model_categories
        stale = stale_model_categories(max_age_days=21.0)
        if stale:
            logger.warning(
                "MODEL_STALE %d categories with active model >21d old: %s",
                len(stale),
                ", ".join(f"{c}={age}d" for c, age in stale[:15]),
            )
    except Exception as e:
        logger.debug("[model_retrain] staleness check failed: %s", e)

    # `error` only when an actual exception fired. A regression skip is the
    # gate working as designed — not an error.
    status = "ok" if error_count == 0 else "error"
    record_run("model_retrain_worker", status)


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("model_retrain_worker", "error")
        log_dead_letter("model_retrain_worker", {}, e)
        logger.exception("model_retrain_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
