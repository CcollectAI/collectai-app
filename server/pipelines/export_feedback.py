"""
Export unprocessed user feedback into training JSONL and taxonomy corrections.

Closes the feedback -> retraining loop:
  1. Queries user_feedback_events_v1 WHERE incorporated_at IS NULL
  2. For sale_price / price_correction / verified_sale: creates training JSONL rows
  3. For category_correction: logs to taxonomy_corrections table (if not already there)
  4. Marks processed feedback with incorporated_at = NOW() and incorporated_run_id
  5. Outputs JSONL to data/feedback_export.jsonl

Usage:
    python -m pipelines.export_feedback
    python -m pipelines.export_feedback --dry-run
    python -m pipelines.export_feedback --dry-run --verbose
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import asyncpg

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logger = logging.getLogger("collectai.export_feedback")

# ---------------------------------------------------------------------------
# Feedback types eligible for training data export
# ---------------------------------------------------------------------------

PRICE_FEEDBACK_TYPES = ("sale_price", "price_correction", "verified_sale")

# Condition and rarity score maps (duplicated minimally for standalone usage)
CONDITION_SCORE_MAP: dict[str, float] = {
    "Mint": 1.0, "Near Mint": 0.9, "NM": 0.9, "Excellent": 0.8,
    "EX": 0.8, "Light Play": 0.7, "Lightly Played": 0.7, "LP": 0.7,
    "Good": 0.6, "GD": 0.6, "Moderate Play": 0.5, "Moderately Played": 0.5,
    "MP": 0.5, "Heavy Play": 0.3, "Heavily Played": 0.3, "HP": 0.3,
    "Damaged": 0.1, "DMG": 0.1, "Poor": 0.1,
    "PSA 10": 1.0, "PSA 9": 0.9, "PSA 8": 0.8, "PSA 7": 0.7,
    "PSA 6": 0.6, "PSA 5": 0.5, "PSA 4": 0.4, "PSA 3": 0.3,
    "PSA 2": 0.2, "PSA 1": 0.1, "Sealed": 1.0, "New": 1.0,
}

RARITY_SCORE_MAP: dict[str, float] = {
    "Common": 0.1, "Uncommon": 0.3, "Rare": 0.5, "Rare Holo": 0.65,
    "Rare Ultra": 0.8, "Rare Secret": 0.9, "Mythic Rare": 0.9,
    "Ultra Rare": 0.8, "Secret Rare": 0.9, "Vaulted": 0.8,
    "Chase": 0.85, "Grail": 0.95, "Exclusive": 0.7,
    "Limited Edition": 0.75, "Standard": 0.3, "N/A": 0.3, "": 0.3,
}


# ---------------------------------------------------------------------------
# Core export logic
# ---------------------------------------------------------------------------

async def export_feedback(
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Main export function.

    Returns summary dict with counts.
    """
    dsn = os.getenv("DB_DSN", "")
    if not dsn:
        # Fallback: construct DSN from SUPABASE_URL if available
        # SUPABASE_URL looks like https://<ref>.supabase.co — derive the
        # pooler connection string from it + service key.
        supa_url = os.getenv("SUPABASE_URL", "")
        supa_key = os.getenv("SUPABASE_SERVICE_KEY", "")
        if supa_url and supa_key:
            # Extract the project ref from https://<ref>.supabase.co
            import re as _re
            match = _re.search(r"https://([^.]+)\.supabase", supa_url)
            if match:
                ref = match.group(1)
                dsn = (
                    f"postgresql://postgres.{ref}:{supa_key}"
                    f"@aws-0-eu-north-1.pooler.supabase.com:5432/postgres"
                )
                logger.info("Constructed DB_DSN from SUPABASE_URL (ref=%s)", ref)
            else:
                logger.error("Could not parse project ref from SUPABASE_URL")
                return {"error": "DB_DSN not set and SUPABASE_URL unparseable", "exported": 0, "taxonomy": 0}
        else:
            logger.error("DB_DSN environment variable is not set (SUPABASE_URL fallback also missing)")
            return {"error": "DB_DSN not set", "exported": 0, "taxonomy": 0}

    run_id = f"export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
    logger.info("Starting feedback export run_id=%s (dry_run=%s)", run_id, dry_run)

    conn = await asyncpg.connect(dsn)
    try:
        return await _process_feedback(conn, run_id, dry_run, verbose)
    finally:
        await conn.close()


async def _process_feedback(
    conn: asyncpg.Connection,
    run_id: str,
    dry_run: bool,
    verbose: bool,
) -> dict:
    """Query unprocessed feedback and export to JSONL / taxonomy_corrections."""

    # ------------------------------------------------------------------
    # 1. Fetch all un-incorporated feedback rows
    # ------------------------------------------------------------------
    rows = await conn.fetch(
        """
        SELECT
            f.id,
            f.user_id,
            f.item_id,
            f.feedback_type,
            f.value_json,
            f.created_at
        FROM public.user_feedback_events_v1 f
        WHERE f.incorporated_at IS NULL
        ORDER BY f.created_at ASC
        """
    )

    if not rows:
        logger.info("No unprocessed feedback found. Nothing to export.")
        return {"exported": 0, "taxonomy": 0, "skipped": 0, "run_id": run_id}

    logger.info("Found %d unprocessed feedback rows", len(rows))

    # ------------------------------------------------------------------
    # 2. For price-related feedback, look up item details
    # ------------------------------------------------------------------
    price_rows = [r for r in rows if r["feedback_type"] in PRICE_FEEDBACK_TYPES]
    category_rows = [r for r in rows if r["feedback_type"] == "category_correction"]

    # Gather unique item IDs that we need to look up
    item_ids = list({r["item_id"] for r in price_rows if r["item_id"]})

    items_by_id: dict[str, asyncpg.Record] = {}
    if item_ids:
        # Fetch items in batches of 200
        for i in range(0, len(item_ids), 200):
            batch = item_ids[i : i + 200]
            item_rows = await conn.fetch(
                """
                SELECT id, category, condition, attributes_json
                FROM public.items
                WHERE id = ANY($1::text[])
                """,
                batch,
            )
            for ir in item_rows:
                items_by_id[ir["id"]] = ir

    logger.info(
        "Looked up %d items for %d price-feedback rows",
        len(items_by_id),
        len(price_rows),
    )

    # ------------------------------------------------------------------
    # 3. Build JSONL training rows from price feedback
    # ------------------------------------------------------------------
    jsonl_records: list[dict] = []
    skipped = 0

    for row in price_rows:
        value_json = row["value_json"]
        if isinstance(value_json, str):
            try:
                value_json = json.loads(value_json)
            except json.JSONDecodeError:
                logger.warning("Skipping row %d: invalid value_json", row["id"])
                skipped += 1
                continue

        # Extract the price value
        price = (
            value_json.get("price")
            or value_json.get("corrected_price")
            or value_json.get("sale_price")
        )
        if price is None:
            logger.warning("Skipping row %d: no price in value_json", row["id"])
            skipped += 1
            continue

        try:
            price = float(price)
        except (ValueError, TypeError):
            logger.warning("Skipping row %d: non-numeric price %r", row["id"], price)
            skipped += 1
            continue

        if price <= 0:
            logger.warning("Skipping row %d: non-positive price %.2f", row["id"], price)
            skipped += 1
            continue

        # Build features from item attributes
        item = items_by_id.get(row["item_id"])
        attrs: dict = {}
        category = "unknown"

        if item:
            category = item["category"] or "unknown"
            raw_attrs = item.get("attributes_json")
            if isinstance(raw_attrs, str):
                try:
                    attrs = json.loads(raw_attrs)
                except json.JSONDecodeError:
                    attrs = {}
            elif isinstance(raw_attrs, dict):
                attrs = raw_attrs

        # Also check if value_json carries attributes directly (some feedback types do)
        for attr_key in ("condition", "condition_score", "rarity", "rarity_score"):
            if attr_key in value_json and attr_key not in attrs:
                attrs[attr_key] = value_json[attr_key]

        # Map condition/rarity strings to scores if not already numeric
        condition_score = attrs.get("condition_score")
        if condition_score is None:
            cond_str = attrs.get("condition", "")
            if isinstance(cond_str, str) and cond_str:
                condition_score = CONDITION_SCORE_MAP.get(cond_str, 0.5)
            else:
                condition_score = 0.7  # default

        rarity_score = attrs.get("rarity_score")
        if rarity_score is None:
            rar_str = attrs.get("rarity", "")
            if isinstance(rar_str, str) and rar_str:
                rarity_score = RARITY_SCORE_MAP.get(rar_str, 0.3)
            else:
                rarity_score = 0.5  # default

        edition_score = attrs.get("edition_score", 0.5)

        features = {
            "condition_score": float(condition_score),
            "rarity_score": float(rarity_score),
            "edition_score": float(edition_score),
        }

        # Copy additional numeric attributes
        for k, v in attrs.items():
            if k not in features and isinstance(v, (int, float)):
                features[k] = float(v)

        record = {
            "features": features,
            "price": price,
            "category": category,
            "source": "user_feedback",
            "feedback_id": row["id"],
        }
        jsonl_records.append(record)

        if verbose:
            logger.debug(
                "  row %d -> category=%s price=%.2f features=%s",
                row["id"],
                category,
                price,
                features,
            )

    logger.info(
        "Built %d JSONL training rows from price feedback (%d skipped)",
        len(jsonl_records),
        skipped,
    )

    # ------------------------------------------------------------------
    # 4. Write JSONL output file
    # ------------------------------------------------------------------
    output_path = DATA_DIR / "feedback_export.jsonl"

    if jsonl_records:
        if dry_run:
            logger.info("[DRY RUN] Would write %d rows to %s", len(jsonl_records), output_path)
        else:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                for rec in jsonl_records:
                    f.write(json.dumps(rec) + "\n")
            logger.info("Wrote %d rows to %s", len(jsonl_records), output_path)

        # Also append to per-category train.jsonl files
        by_category: dict[str, list[dict]] = {}
        for rec in jsonl_records:
            cat = rec.get("category", "unknown")
            if cat != "unknown":
                by_category.setdefault(cat, []).append(rec)

        for cat, recs in by_category.items():
            cat_dir = DATA_DIR / cat
            cat_train_path = cat_dir / "train.jsonl"
            if dry_run:
                logger.info(
                    "[DRY RUN] Would append %d feedback rows to %s",
                    len(recs),
                    cat_train_path,
                )
            else:
                cat_dir.mkdir(parents=True, exist_ok=True)
                with open(cat_train_path, "a") as f:
                    for rec in recs:
                        # Write only features + price (standard train.jsonl format)
                        f.write(
                            json.dumps({"features": rec["features"], "price": rec["price"]})
                            + "\n"
                        )
                logger.info("Appended %d feedback rows to %s", len(recs), cat_train_path)

    # ------------------------------------------------------------------
    # 5. Process category_correction feedback -> taxonomy_corrections
    # ------------------------------------------------------------------
    taxonomy_count = 0

    for row in category_rows:
        value_json = row["value_json"]
        if isinstance(value_json, str):
            try:
                value_json = json.loads(value_json)
            except json.JSONDecodeError:
                logger.warning("Skipping category correction row %d: invalid value_json", row["id"])
                skipped += 1
                continue

        original_category = value_json.get("original_category", "")
        corrected_category = value_json.get("corrected_category", "")

        if not original_category or not corrected_category:
            logger.warning(
                "Skipping category correction row %d: missing original/corrected category",
                row["id"],
            )
            skipped += 1
            continue

        if dry_run:
            logger.info(
                "[DRY RUN] Would insert taxonomy correction: %s -> %s (feedback row %d)",
                original_category,
                corrected_category,
                row["id"],
            )
        else:
            try:
                await conn.execute(
                    """
                    INSERT INTO public.taxonomy_corrections
                        (user_id, item_id, original_category, corrected_category, source)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT DO NOTHING
                    """,
                    str(row["user_id"]) if row["user_id"] else "system",
                    row["item_id"],
                    original_category,
                    corrected_category,
                    "feedback_export",
                )
                taxonomy_count += 1
            except Exception as e:
                logger.warning(
                    "Failed to insert taxonomy correction for row %d: %s", row["id"], e
                )

        if verbose:
            logger.debug(
                "  row %d -> taxonomy: %s -> %s",
                row["id"],
                original_category,
                corrected_category,
            )

    logger.info("Processed %d category corrections", taxonomy_count if not dry_run else len(category_rows))

    # ------------------------------------------------------------------
    # 6. Mark all processed feedback as incorporated
    # ------------------------------------------------------------------
    feedback_ids = [r["id"] for r in rows]

    if dry_run:
        logger.info(
            "[DRY RUN] Would mark %d feedback rows as incorporated (run_id=%s)",
            len(feedback_ids),
            run_id,
        )
    else:
        now = datetime.now(timezone.utc)
        updated = await conn.execute(
            """
            UPDATE public.user_feedback_events_v1
            SET incorporated_at = $1,
                incorporated_run_id = $2
            WHERE id = ANY($3::bigint[])
              AND incorporated_at IS NULL
            """,
            now,
            run_id,
            feedback_ids,
        )
        logger.info("Marked feedback as incorporated: %s (run_id=%s)", updated, run_id)

    # ------------------------------------------------------------------
    # 7. Summary
    # ------------------------------------------------------------------
    summary = {
        "run_id": run_id,
        "exported": len(jsonl_records),
        "taxonomy": taxonomy_count if not dry_run else len(category_rows),
        "skipped": skipped,
        "total_processed": len(rows),
        "dry_run": dry_run,
    }

    logger.info("Export complete: %s", json.dumps(summary))
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Export unprocessed user feedback to training JSONL and taxonomy corrections"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and display feedback without writing files or updating DB",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Extra logging (debug level)",
    )

    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    logger.setLevel(level)

    result = asyncio.run(export_feedback(dry_run=args.dry_run, verbose=args.verbose))

    if result.get("error"):
        sys.exit(1)

    logger.info(
        "SUMMARY: exported=%d, taxonomy=%d, skipped=%d, total=%d",
        result.get("exported", 0),
        result.get("taxonomy", 0),
        result.get("skipped", 0),
        result.get("total_processed", 0),
    )


if __name__ == "__main__":
    main()
