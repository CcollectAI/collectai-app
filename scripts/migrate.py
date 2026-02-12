#!/usr/bin/env python3
"""
Lightweight database migration runner for CollectAI.

Usage:
    python scripts/migrate.py                # apply all pending migrations
    python scripts/migrate.py --status       # show applied vs pending
    python scripts/migrate.py --dry-run      # show what would be applied
    python scripts/migrate.py --target 20260210_evidence_native.sql  # apply up to (inclusive)

Reads DB_DSN from the environment.  Migrations are read from supabase/migrations/*.sql
and applied in filename-sorted order.  Each migration runs inside its own transaction;
if it fails, the transaction is rolled back and the runner stops immediately.

The tracking table ``schema_migrations`` stores (version, applied_at) for each
successfully applied file.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import pathlib
import re
import sys
import time

import asyncpg

logger = logging.getLogger("migrate")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "supabase" / "migrations"

TRACKING_TABLE_DDL = """\
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

# Regex to strip explicit BEGIN/COMMIT wrappers from migration files.
# The runner wraps every migration in its own transaction, so we need
# to remove author-provided transaction boundaries to avoid nesting errors.
_TX_STRIP_RE = re.compile(
    r"^\s*BEGIN\s*;\s*$|^\s*COMMIT\s*;\s*$",
    re.MULTILINE | re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def discover_migrations() -> list[pathlib.Path]:
    """Return all .sql files in the migrations directory, sorted by name."""
    if not MIGRATIONS_DIR.is_dir():
        logger.error("Migrations directory not found: %s", MIGRATIONS_DIR)
        sys.exit(1)
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    return files


def strip_transaction_wrappers(sql: str) -> str:
    """Remove bare BEGIN; / COMMIT; lines so we can wrap in our own transaction."""
    return _TX_STRIP_RE.sub("", sql).strip()


async def ensure_tracking_table(conn: asyncpg.Connection) -> None:
    """Create the schema_migrations table if it does not exist."""
    await conn.execute(TRACKING_TABLE_DDL)


async def get_applied_versions(conn: asyncpg.Connection) -> set[str]:
    """Return the set of migration versions already recorded."""
    rows = await conn.fetch("SELECT version FROM public.schema_migrations ORDER BY version")
    return {r["version"] for r in rows}


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


async def cmd_status(dsn: str) -> None:
    """Print a table of all migrations and their applied status."""
    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        await ensure_tracking_table(conn)
        applied = await get_applied_versions(conn)

        # Also fetch applied_at timestamps for display
        rows = await conn.fetch(
            "SELECT version, applied_at FROM public.schema_migrations ORDER BY version"
        )
        applied_map = {r["version"]: r["applied_at"] for r in rows}
    finally:
        await conn.close()

    all_files = discover_migrations()
    pending_count = 0
    applied_count = 0

    logger.info("\n%-10s %-60s %s", "STATUS", "MIGRATION", "APPLIED AT")
    logger.info("-" * 100)

    for f in all_files:
        name = f.name
        if name in applied:
            ts = applied_map[name].strftime("%Y-%m-%d %H:%M:%S UTC")
            logger.info("%-10s %-60s %s", "applied", name, ts)
            applied_count += 1
        else:
            logger.info("%-10s %-60s %s", "pending", name, "--")
            pending_count += 1

    logger.info("-" * 100)
    logger.info("Total: %d  |  Applied: %d  |  Pending: %d", len(all_files), applied_count, pending_count)


async def cmd_apply(dsn: str, *, dry_run: bool = False, target: str | None = None) -> None:
    """Apply pending migrations (or just list them in dry-run mode)."""
    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        await ensure_tracking_table(conn)
        applied = await get_applied_versions(conn)
    finally:
        await conn.close()

    all_files = discover_migrations()
    pending = [f for f in all_files if f.name not in applied]

    # If a target is specified, only include up to (and including) that file.
    if target:
        cut: list[pathlib.Path] = []
        found = False
        for f in pending:
            cut.append(f)
            if f.name == target or f.stem == target:
                found = True
                break
        if not found:
            logger.error("Target migration %r not found among pending migrations.", target)
            sys.exit(1)
        pending = cut

    if not pending:
        logger.info("Nothing to apply -- all migrations are up to date.")
        return

    if dry_run:
        logger.info("[DRY RUN] %d migration(s) would be applied:", len(pending))
        for f in pending:
            logger.info("  - %s", f.name)
        return

    # Apply each migration in its own connection + transaction.
    applied_count = 0
    for f in pending:
        sql = f.read_text(encoding="utf-8")
        sql = strip_transaction_wrappers(sql)

        if not sql:
            logger.warning("Skipping empty migration: %s", f.name)
            continue

        conn = await asyncpg.connect(dsn, timeout=10)
        try:
            t0 = time.monotonic()
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO public.schema_migrations (version) VALUES ($1)",
                    f.name,
                )
            elapsed = time.monotonic() - t0
            applied_count += 1
            logger.info("  applied: %s  (%.2fs)", f.name, elapsed)
        except Exception:
            logger.exception("Migration FAILED: %s -- rolled back. Stopping.", f.name)
            sys.exit(1)
        finally:
            await conn.close()

    logger.info("Done. %d migration(s) applied successfully.", applied_count)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CollectAI database migration runner",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show applied vs pending migrations and exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List migrations that would be applied without executing them.",
    )
    parser.add_argument(
        "--target",
        type=str,
        default=None,
        help="Apply migrations up to and including this version (filename or stem).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    dsn = os.environ.get("DB_DSN", "")
    if not dsn:
        logger.error("DB_DSN environment variable is not set.")
        sys.exit(1)

    if args.status:
        asyncio.run(cmd_status(dsn))
    else:
        asyncio.run(cmd_apply(dsn, dry_run=args.dry_run, target=args.target))


if __name__ == "__main__":
    main()
