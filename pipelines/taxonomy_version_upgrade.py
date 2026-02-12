"""
Taxonomy version upgrade tool.

Migrates items, market_hits, and training data from one taxonomy version
to another by applying migration rules that remap categories.

Usage:
    python -m pipelines.taxonomy_version_upgrade --from-version v1.0 --to-version v1.1 --rules rules.json
    python -m pipelines.taxonomy_version_upgrade --from-version v1.0 --to-version v1.1 --dry-run
    python -m pipelines.taxonomy_version_upgrade --from-version v1.0 --to-version v1.1 --rules rules.json --dry-run

The rules file should be a JSON array like:
    [
        {"from_category": "old_cat", "to_category": "new_cat", "condition": null},
        {"from_category": "retro_games", "to_category": "retro_handhelds", "condition": "subtype_id = 'handheld'"}
    ]

If --rules is not provided, the tool attempts to read migration_rules from
the target version in the taxonomy_registry table.
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

logger = logging.getLogger("collectai.taxonomy_upgrade")


def _setup_logging(level: str = "INFO") -> None:
    if logger.handlers:
        return
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    logger.addHandler(handler)


# ---------------------------------------------------------------------------
# Migration rule types
# ---------------------------------------------------------------------------

class MigrationRule:
    """A single category remapping rule."""

    def __init__(self, from_category: str, to_category: str, condition: str | None = None):
        self.from_category = from_category
        self.to_category = to_category
        self.condition = condition  # optional SQL WHERE clause fragment

    def to_dict(self) -> dict:
        return {
            "from_category": self.from_category,
            "to_category": self.to_category,
            "condition": self.condition,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MigrationRule:
        return cls(
            from_category=d["from_category"],
            to_category=d["to_category"],
            condition=d.get("condition"),
        )


def load_rules_from_file(path: str) -> list[MigrationRule]:
    """Load migration rules from a JSON file."""
    with open(path, "r") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}, got {type(data).__name__}")
    return [MigrationRule.from_dict(r) for r in data]


async def load_rules_from_registry(
    conn: asyncpg.Connection,
    to_version: str,
) -> list[MigrationRule]:
    """Load migration_rules from the taxonomy_registry for the target version."""
    row = await conn.fetchrow(
        "SELECT migration_rules FROM taxonomy_registry WHERE version = $1",
        to_version,
    )
    if row is None:
        raise ValueError(f"Taxonomy version {to_version} not found in registry")
    rules_json = row["migration_rules"]
    if rules_json is None:
        return []
    if isinstance(rules_json, str):
        rules_json = json.loads(rules_json)
    return [MigrationRule.from_dict(r) for r in rules_json]


# ---------------------------------------------------------------------------
# Tables to migrate
# ---------------------------------------------------------------------------

MIGRATION_TARGETS = [
    {
        "table": "items",
        "category_column": "category",
        "version_column": "taxonomy_version",
    },
    {
        "table": "market_hits",
        "category_column": "category",
        "version_column": "taxonomy_version",
    },
    {
        "table": "price_predictions",
        "category_column": "category",
        "version_column": "taxonomy_version",
    },
]


# ---------------------------------------------------------------------------
# Migration logic
# ---------------------------------------------------------------------------

async def count_affected_rows(
    conn: asyncpg.Connection,
    table: str,
    category_column: str,
    version_column: str,
    from_version: str,
    rule: MigrationRule,
) -> int:
    """Count rows that would be affected by a single migration rule."""
    base_query = (
        f"SELECT COUNT(*) FROM {table} "
        f"WHERE {category_column} = $1 AND {version_column} = $2"
    )
    params: list = [rule.from_category, from_version]

    # Note: rule.condition is for documentation/reporting only.
    # We do not inject raw SQL from conditions for safety. Conditions are
    # logged and can be applied manually in complex cases.
    count = await conn.fetchval(base_query, *params)
    return count or 0


async def apply_rule_to_table(
    conn: asyncpg.Connection,
    table: str,
    category_column: str,
    version_column: str,
    from_version: str,
    to_version: str,
    rule: MigrationRule,
) -> int:
    """Apply a single migration rule to a table. Returns number of rows updated."""
    update_query = (
        f"UPDATE {table} SET {category_column} = $1, {version_column} = $2 "
        f"WHERE {category_column} = $3 AND {version_column} = $4"
    )
    result = await conn.execute(update_query, rule.to_category, to_version, rule.from_category, from_version)
    # asyncpg returns "UPDATE N" string
    try:
        return int(result.split()[-1])
    except (ValueError, IndexError):
        return 0


async def update_remaining_version(
    conn: asyncpg.Connection,
    table: str,
    version_column: str,
    from_version: str,
    to_version: str,
) -> int:
    """Update taxonomy_version for rows that were not remapped (same category, new version)."""
    result = await conn.execute(
        f"UPDATE {table} SET {version_column} = $1 WHERE {version_column} = $2",
        to_version,
        from_version,
    )
    try:
        return int(result.split()[-1])
    except (ValueError, IndexError):
        return 0


async def run_migration(
    from_version: str,
    to_version: str,
    rules: list[MigrationRule],
    dry_run: bool = False,
) -> dict:
    """Run the full taxonomy migration.

    Args:
        from_version: Source taxonomy version.
        to_version: Target taxonomy version.
        rules: List of migration rules to apply.
        dry_run: If True, only compute counts without modifying data.

    Returns:
        Summary report dict.
    """
    dsn = os.getenv("DB_DSN", "")
    if not dsn:
        logger.error("DB_DSN not set. Cannot run migration.")
        return {"error": "no_dsn"}

    report: dict = {
        "from_version": from_version,
        "to_version": to_version,
        "dry_run": dry_run,
        "rule_count": len(rules),
        "tables": {},
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    conn = None
    try:
        conn = await asyncpg.connect(dsn)

        # Verify target version exists in registry (unless dry_run with no DB registry)
        target_exists = await conn.fetchval(
            "SELECT version FROM taxonomy_registry WHERE version = $1",
            to_version,
        )
        if not target_exists and not dry_run:
            logger.error(
                "Target version %s not found in taxonomy_registry. "
                "Seed it first with taxonomy_seed.py.",
                to_version,
            )
            return {"error": "target_version_not_found"}

        for target in MIGRATION_TARGETS:
            table = target["table"]
            cat_col = target["category_column"]
            ver_col = target["version_column"]

            table_report: dict = {
                "rules_applied": [],
                "total_remapped": 0,
                "total_version_bumped": 0,
            }

            # Check if table exists (some tables may not be created yet)
            table_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = $1)",
                table,
            )
            if not table_exists:
                logger.info("Table %s does not exist, skipping.", table)
                table_report["skipped"] = "table_not_found"
                report["tables"][table] = table_report
                continue

            # Check if version column exists
            col_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = $1 AND column_name = $2
                )
                """,
                table,
                ver_col,
            )
            if not col_exists:
                logger.info(
                    "Column %s.%s does not exist, skipping.",
                    table, ver_col,
                )
                table_report["skipped"] = "version_column_not_found"
                report["tables"][table] = table_report
                continue

            # Apply each rule
            for rule in rules:
                affected = await count_affected_rows(
                    conn, table, cat_col, ver_col, from_version, rule,
                )

                rule_entry = {
                    "from_category": rule.from_category,
                    "to_category": rule.to_category,
                    "condition": rule.condition,
                    "affected_rows": affected,
                }

                if affected > 0 and not dry_run:
                    updated = await apply_rule_to_table(
                        conn, table, cat_col, ver_col,
                        from_version, to_version, rule,
                    )
                    rule_entry["updated_rows"] = updated
                    table_report["total_remapped"] += updated
                    logger.info(
                        "Table %s: %s -> %s remapped %d rows",
                        table, rule.from_category, rule.to_category, updated,
                    )
                elif affected > 0:
                    logger.info(
                        "[DRY RUN] Table %s: %s -> %s would affect %d rows",
                        table, rule.from_category, rule.to_category, affected,
                    )
                    table_report["total_remapped"] += affected

                table_report["rules_applied"].append(rule_entry)

            # Bump version on remaining rows that were not remapped
            if not dry_run:
                bumped = await update_remaining_version(
                    conn, table, ver_col, from_version, to_version,
                )
                table_report["total_version_bumped"] = bumped
                logger.info(
                    "Table %s: version bumped %d remaining rows to %s",
                    table, bumped, to_version,
                )
            else:
                remaining = await conn.fetchval(
                    f"SELECT COUNT(*) FROM {table} WHERE {ver_col} = $1",
                    from_version,
                )
                table_report["total_version_bumped"] = remaining or 0
                logger.info(
                    "[DRY RUN] Table %s: %d remaining rows would be bumped to %s",
                    table, remaining or 0, to_version,
                )

            report["tables"][table] = table_report

        # Deprecate old version in registry (if not dry run)
        if not dry_run:
            await conn.execute(
                """
                UPDATE taxonomy_registry
                SET deprecated_at = $1
                WHERE version = $2 AND deprecated_at IS NULL
                """,
                datetime.now(timezone.utc),
                from_version,
            )
            logger.info("Deprecated taxonomy version %s", from_version)

    except Exception:
        logger.exception("Migration failed")
        report["error"] = "migration_exception"
    finally:
        if conn is not None:
            await conn.close()

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate taxonomy from one version to another.",
    )
    parser.add_argument(
        "--from-version",
        required=True,
        help="Source taxonomy version (e.g. v1.0)",
    )
    parser.add_argument(
        "--to-version",
        required=True,
        help="Target taxonomy version (e.g. v1.1)",
    )
    parser.add_argument(
        "--rules",
        default=None,
        help="Path to JSON file with migration rules. "
             "If not provided, reads from taxonomy_registry.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only compute counts, do not modify data.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()
    _setup_logging(args.log_level)

    # Load rules
    if args.rules:
        logger.info("Loading migration rules from file: %s", args.rules)
        rules = load_rules_from_file(args.rules)
    else:
        logger.info(
            "No --rules file provided. Will load from taxonomy_registry for version %s",
            args.to_version,
        )
        # Need a temporary connection to load rules
        dsn = os.getenv("DB_DSN", "")
        if not dsn:
            logger.error("DB_DSN not set. Provide --rules file or set DB_DSN.")
            sys.exit(1)

        async def _load() -> list[MigrationRule]:
            conn = None
            try:
                conn = await asyncpg.connect(dsn)
                return await load_rules_from_registry(conn, args.to_version)
            finally:
                if conn is not None:
                    await conn.close()

        rules = asyncio.run(_load())

    if not rules:
        logger.warning("No migration rules found. Only version bumping will occur.")

    logger.info(
        "Migration: %s -> %s with %d rules (dry_run=%s)",
        args.from_version, args.to_version, len(rules), args.dry_run,
    )

    report = asyncio.run(
        run_migration(
            from_version=args.from_version,
            to_version=args.to_version,
            rules=rules,
            dry_run=args.dry_run,
        )
    )

    # Print summary
    logger.info("\n%s", "=" * 60)
    logger.info("TAXONOMY MIGRATION REPORT")
    logger.info("%s", "=" * 60)
    logger.info("%s", json.dumps(report, indent=2))

    if report.get("error"):
        logger.error("Migration finished with errors: %s", report["error"])
        sys.exit(1)

    logger.info("Migration complete.")


if __name__ == "__main__":
    main()
