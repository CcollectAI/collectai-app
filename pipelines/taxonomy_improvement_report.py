"""
Taxonomy Improvement Report.

Queries the taxonomy_corrections table and produces a report showing which
taxonomy patterns need updating based on user feedback.

- Groups by (original_category, corrected_category) with counts
- Corrections with count >= 5 are flagged as "strong signals"
- Outputs a formatted table to stdout

Usage:
    python -m pipelines.taxonomy_improvement_report
    python -m pipelines.taxonomy_improvement_report --threshold 3
    python -m pipelines.taxonomy_improvement_report --json
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

import asyncpg

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logger = logging.getLogger("collectai.taxonomy_report")

# ---------------------------------------------------------------------------
# Default threshold for "strong signal"
# ---------------------------------------------------------------------------

DEFAULT_STRONG_SIGNAL_THRESHOLD = 5


# ---------------------------------------------------------------------------
# Core report logic
# ---------------------------------------------------------------------------

async def generate_report(
    threshold: int = DEFAULT_STRONG_SIGNAL_THRESHOLD,
    output_json: bool = False,
) -> list[dict]:
    """
    Query taxonomy_corrections and produce a grouped report.

    Returns list of dicts:
        [
            {
                "original_category": "funko",
                "corrected_category": "designer_toys",
                "count": 12,
                "latest_at": "2026-02-09T...",
                "unique_users": 5,
                "strong_signal": True,
            },
            ...
        ]
    """
    dsn = os.getenv("DB_DSN", "")
    if not dsn:
        logger.error("DB_DSN environment variable is not set")
        return []

    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            """
            SELECT
                original_category,
                corrected_category,
                COUNT(*)::int AS correction_count,
                MAX(created_at) AS latest_at,
                COUNT(DISTINCT user_id)::int AS unique_users
            FROM public.taxonomy_corrections
            GROUP BY original_category, corrected_category
            ORDER BY correction_count DESC, original_category, corrected_category
            """
        )
    finally:
        await conn.close()

    if not rows:
        logger.info("No taxonomy corrections found in the database.")
        return []

    results = []
    for row in rows:
        latest_at = row["latest_at"]
        if latest_at:
            latest_at = latest_at.isoformat()

        results.append(
            {
                "original_category": row["original_category"],
                "corrected_category": row["corrected_category"],
                "count": row["correction_count"],
                "latest_at": latest_at,
                "unique_users": row["unique_users"],
                "strong_signal": row["correction_count"] >= threshold,
            }
        )

    return results


def print_table(results: list[dict], threshold: int) -> None:
    """Print results as a formatted table via logger."""
    if not results:
        logger.info("No taxonomy corrections found.")
        return

    # Column widths
    col_orig = max(len("Original Category"), max(len(r["original_category"]) for r in results))
    col_corr = max(len("Corrected Category"), max(len(r["corrected_category"]) for r in results))
    col_count = max(len("Count"), 5)
    col_users = max(len("Users"), 5)
    col_signal = len("Signal")
    col_latest = max(len("Latest"), 19)

    # Header
    header = (
        f"{'Original Category':<{col_orig}}  "
        f"{'Corrected Category':<{col_corr}}  "
        f"{'Count':>{col_count}}  "
        f"{'Users':>{col_users}}  "
        f"{'Signal':<{col_signal}}  "
        f"{'Latest':<{col_latest}}"
    )
    separator = "-" * len(header)

    logger.info("")
    logger.info("%s", "=" * len(header))
    logger.info("TAXONOMY IMPROVEMENT REPORT")
    logger.info("Strong signal threshold: >= %d corrections", threshold)
    logger.info("Generated: %s", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
    logger.info("%s", "=" * len(header))
    logger.info("")
    logger.info("%s", header)
    logger.info("%s", separator)

    strong_signals = []

    for r in results:
        signal_str = "***" if r["strong_signal"] else ""
        latest_str = r["latest_at"][:19] if r["latest_at"] else "N/A"

        line = (
            f"{r['original_category']:<{col_orig}}  "
            f"{r['corrected_category']:<{col_corr}}  "
            f"{r['count']:>{col_count}}  "
            f"{r['unique_users']:>{col_users}}  "
            f"{signal_str:<{col_signal}}  "
            f"{latest_str:<{col_latest}}"
        )
        logger.info("%s", line)

        if r["strong_signal"]:
            strong_signals.append(r)

    logger.info("%s", separator)
    logger.info("Total correction patterns: %d", len(results))
    logger.info("Strong signals (>= %d): %d", threshold, len(strong_signals))
    logger.info("")

    if strong_signals:
        logger.info("ACTION REQUIRED - Strong signals detected:")
        logger.info("%s", "-" * 60)
        for s in strong_signals:
            logger.info(
                "  %s -> %s (%d corrections from %d users)",
                s["original_category"], s["corrected_category"],
                s["count"], s["unique_users"],
            )
        logger.info("")
        logger.info(
            "These patterns should be reviewed and potentially added to "
            "src/ingest/taxonomy_mapper.py"
        )
        logger.info("")
    else:
        logger.info("No strong signals detected. Taxonomy patterns look healthy.")
        logger.info("")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate taxonomy improvement report from user corrections"
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_STRONG_SIGNAL_THRESHOLD,
        help=f"Minimum correction count to flag as strong signal (default: {DEFAULT_STRONG_SIGNAL_THRESHOLD})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output results as JSON instead of formatted table",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Extra logging",
    )

    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    logger.setLevel(level)

    results = asyncio.run(generate_report(threshold=args.threshold, output_json=args.output_json))

    if args.output_json:
        logger.info("%s", json.dumps(results, indent=2, default=str))
    else:
        print_table(results, threshold=args.threshold)

    # Exit with code 1 if there are strong signals (useful in CI)
    strong = [r for r in results if r.get("strong_signal")]
    if strong:
        logger.info(
            "%d strong signal(s) detected; returning exit code 1 for CI visibility",
            len(strong),
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
