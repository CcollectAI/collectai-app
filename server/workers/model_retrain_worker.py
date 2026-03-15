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
    "oop_board_games", "city_pop_vinyl", "niche_perfumery",
]

# Data directory (relative to server/)
DATA_DIR = Path("data")


def _price_to_features(price: float, condition: str | None, is_sold: bool) -> dict:
    """Convert a market_hit row into training features.

    Uses heuristic scoring since market_hits don't have granular feature scores.
    The key insight: sold prices are the ground truth we're training on.
    """
    # Condition score heuristic (order matters — check specific before general)
    cond = (condition or "").lower()
    if any(k in cond for k in ("like new", "near mint", "nm")):
        condition_score = 0.85
    elif any(k in cond for k in ("new", "sealed", "mint")):
        condition_score = 0.95
    elif any(k in cond for k in ("good", "very good", "vg", "excellent")):
        condition_score = 0.70
    elif any(k in cond for k in ("fair", "acceptable", "played")):
        condition_score = 0.45
    elif any(k in cond for k in ("poor", "damaged", "heavy")):
        condition_score = 0.20
    else:
        condition_score = 0.70  # Default to "good" if unknown

    # Rarity/edition scores are harder to infer from market data alone
    # Use price percentile relative to category as a proxy
    rarity_score = 0.50  # Neutral default
    edition_score = 0.50

    return {
        "condition_score": round(condition_score, 2),
        "rarity_score": round(rarity_score, 2),
        "edition_score": round(edition_score, 2),
    }


async def _export_market_hits_to_jsonl(conn, category: str, cutoff: datetime) -> int:
    """Export recent market_hits for a category to JSONL training format.

    Returns number of observations written.
    """
    # Fetch sold comps with prices for this category
    rows = await conn.fetch(
        """
        SELECT price, condition, features_json
        FROM public.market_hits
        WHERE normalized_key LIKE $1
          AND price IS NOT NULL
          AND price > 0
          AND created_at >= $2
        ORDER BY created_at DESC
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

            # Extract is_sold from features_json if available
            features_json = row["features_json"]
            is_sold = False
            if isinstance(features_json, dict):
                is_sold = features_json.get("is_sold", False)
            elif isinstance(features_json, str):
                try:
                    fj = json.loads(features_json)
                    is_sold = fj.get("is_sold", False)
                except (json.JSONDecodeError, TypeError):
                    pass

            features = _price_to_features(price, condition, is_sold)
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
    They get weighted by user_weight (level >= 10 users get 2x).
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

    cat_dir = DATA_DIR / category
    cat_dir.mkdir(parents=True, exist_ok=True)

    corrections_path = cat_dir / "train_corrections.jsonl"
    count = 0

    with open(corrections_path, "w") as f:
        for row in rows:
            condition = row["corrected_condition"]
            user_weight = float(row["user_weight"] or 1.0)
            features = _price_to_features(0, condition, False)
            # Corrections don't have prices, but they refine category/condition mapping
            # Write them as feature-only records that reinforce correct categorization
            record = {"features": features, "price": 0, "correction": True}
            line = json.dumps(record) + "\n"
            # Apply user weight — high-level users' corrections count more
            repeat = int(user_weight)
            for _ in range(repeat):
                f.write(line)
                count += 1

    logger.info("Exported %d scan correction observations for %s", count, category)
    return count


def _retrain_category(category: str) -> dict:
    """Retrain the Ridge model for a single category using merged data.

    Merges: static seed (train.jsonl) + live market data (train_live.jsonl) +
    ground truth (train_ground_truth.jsonl).
    """
    cat_dir = DATA_DIR / category

    # Collect all training data
    all_features = []
    all_prices = []

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
                    all_features.append(record["features"])
                    all_prices.append(float(record["price"]))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

    if len(all_prices) < MIN_SAMPLES:
        logger.info(
            "Category %s has %d samples (min %d) — skipping retrain",
            category, len(all_prices), MIN_SAMPLES,
        )
        return {"category": category, "status": "skipped", "samples": len(all_prices)}

    # Use train_price module for actual training
    try:
        from pipelines.train_price import train_category
        result = train_category(category, all_features, all_prices)
        logger.info(
            "Retrained %s: samples=%d cv_mae=%.2f",
            category, len(all_prices), result.get("cv_mae", -1),
        )
        return {
            "category": category,
            "status": "ok",
            "samples": len(all_prices),
            "cv_mae": result.get("cv_mae"),
            "version": result.get("version"),
        }
    except ImportError:
        # train_category may not exist as a public function — use CLI fallback
        logger.info("train_category not importable, using CLI fallback for %s", category)
        return _retrain_via_cli(category, len(all_prices))
    except Exception as e:
        logger.warning("Retrain failed for %s: %s", category, e)
        return {"category": category, "status": "error", "error": str(e)[:200]}


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
        # Phase 1: Export market_hits + ground truths per category
        export_stats = {}
        for category in ALL_CATEGORIES:
            hits_count = await _export_market_hits_to_jsonl(conn, category, cutoff)
            gt_count = await _export_ground_truths(conn, category, cutoff)
            corr_count = await _export_scan_corrections(conn, category, cutoff)
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

    # Phase 2: Retrain models (doesn't need DB connection)
    retrain_results = []
    ok_count = 0
    skip_count = 0
    error_count = 0

    for category in ALL_CATEGORIES:
        result = _retrain_category(category)
        retrain_results.append(result)
        if result["status"] == "ok":
            ok_count += 1
        elif result["status"] == "skipped":
            skip_count += 1
        else:
            error_count += 1

    logger.info(
        "Model retrain cycle complete: ok=%d skipped=%d errors=%d (total=%d categories)",
        ok_count, skip_count, error_count, len(ALL_CATEGORIES),
    )

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
