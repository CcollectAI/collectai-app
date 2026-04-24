#!/usr/bin/env python3
"""Partition drop worker — detaches + drops monthly partitions older than
the retention window, but ONLY after verifying the partition's data is
safely in S3 (checked via the exports manifest).

Week-8 deliverable from `docs/DATA_SCALING_PLAN.md`.

Operates on three partitioned parent tables:
    public.market_hits        (by seen_at)
    public.price_predictions  (by generated_at)
    public.price_history      (by as_of)

Partition naming convention: `{parent}_y{YYYY}m{MM}`. The month embedded
in the name is the earliest month the partition holds.

Algorithm per run:
  1. List all partitions of each parent (via pg_inherits).
  2. Parse (year, month) from name. Skip 'default' partitions.
  3. If month is strictly older than (current month − RETENTION_MONTHS):
       a. Fetch manifest entries from s3://$DATALAKE_BUCKET/manifests/exports.jsonl
       b. For market_hits: look for partition name literal match
          For price_predictions/price_history: look for bucket manifest id
          (e.g. `price_predictions_y2026m01`)
       c. If manifest confirms export: ALTER TABLE parent DETACH PARTITION child;
          DROP TABLE child.
       d. If manifest missing: log + skip. If this recurs for > 2 cycles
          in a row, emit 'error' so sanity_probe surfaces it.

Env:
  PARTITION_RETENTION_MONTHS  — age threshold (default 6)
  PARTITION_DROP_ENABLED       — 'true' to actually drop; default 'false'
                                 for dry-run mode (logs what it would do)
  DATALAKE_BUCKET             — S3 bucket holding the exports manifest
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import date, datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

BUCKET = os.getenv("DATALAKE_BUCKET", "collectai-warehouse-prod-eu-north-1")
REGION = os.getenv("DATALAKE_REGION", "eu-north-1")
RETENTION_MONTHS = int(os.getenv("PARTITION_RETENTION_MONTHS", "6"))
ENABLED = os.getenv("PARTITION_DROP_ENABLED", "false").lower() == "true"
MANIFEST_KEY = "manifests/exports.jsonl"

# Parents to audit. The manifest_id_fmt says how the partition name maps
# to the S3 manifest `partition` field: market_hits uses the bare partition
# name; the two time-bucketed tables use `{prefix}_y{YYYY}m{MM}`.
PARENTS = [
    # (parent_table, manifest_id_format)
    ("market_hits",       "{part_name}"),
    ("price_predictions", "price_predictions_y{year:04d}m{month:02d}"),
    ("price_history",     "price_history_y{year:04d}m{month:02d}"),
]

_PARTITION_RE = re.compile(r"y(\d{4})m(\d{2})")


def _months_between(a: date, b: date) -> int:
    """Return (a - b) in calendar months (a >= b assumed)."""
    return (a.year - b.year) * 12 + (a.month - b.month)


async def _list_partitions(conn, parent: str) -> list[str]:
    rows = await conn.fetch(
        """
        SELECT inhrelid::regclass::text AS part
        FROM pg_inherits
        WHERE inhparent = $1::regclass
        ORDER BY 1
        """,
        f"public.{parent}",
    )
    return [r["part"].replace("public.", "") for r in rows]


def _parse_partition_name(name: str) -> Optional[tuple[int, int]]:
    """Extract (year, month) from a partition name like `foo_y2026m04`."""
    m = _PARTITION_RE.search(name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _load_manifest(s3_client) -> set[str]:
    """Return the set of partition ids (manifest `partition` field) that
    have successfully been exported to S3."""
    exported: set[str] = set()
    try:
        obj = s3_client.get_object(Bucket=BUCKET, Key=MANIFEST_KEY)
        for line in obj["Body"].read().splitlines():
            try:
                exported.add(json.loads(line)["partition"])
            except Exception:  # noqa: BLE001
                continue
    except Exception as e:  # noqa: BLE001
        logger.warning("[partition_drop] manifest fetch failed: %s", e)
    return exported


async def run_once() -> dict:
    """Detach + drop eligible partitions. Returns summary stats."""
    from app.worker_registry import record_run

    import asyncpg
    import boto3

    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ["DB_DSN"]
    conn = await asyncpg.connect(dsn, timeout=60)
    await conn.execute("SET statement_timeout = 0")

    s3 = boto3.client("s3", region_name=REGION)
    exported = _load_manifest(s3)
    logger.info("[partition_drop] %d exported partitions in manifest", len(exported))

    today = datetime.now(timezone.utc).date()
    cutoff_month = today.replace(day=1)
    # cutoff_month is the start of current month; anything whose month is
    # strictly older than cutoff_month by >= RETENTION_MONTHS is eligible.

    stats = {
        "checked": 0,
        "eligible_by_age": 0,
        "confirmed_in_s3": 0,
        "dropped": 0,
        "skipped_no_manifest": [],
        "dropped_parts": [],
    }

    try:
        for parent, manifest_fmt in PARENTS:
            parts = await _list_partitions(conn, parent)
            for part_name in parts:
                stats["checked"] += 1
                if "default" in part_name or "legacy" in part_name:
                    continue

                parsed = _parse_partition_name(part_name)
                if not parsed:
                    logger.debug("[partition_drop] unparseable: %s", part_name)
                    continue
                year, month = parsed
                part_start = date(year, month, 1)
                age_months = _months_between(cutoff_month, part_start)

                if age_months < RETENTION_MONTHS:
                    continue
                stats["eligible_by_age"] += 1

                manifest_id = manifest_fmt.format(
                    part_name=part_name, year=year, month=month,
                )
                if manifest_id not in exported:
                    stats["skipped_no_manifest"].append(part_name)
                    logger.warning(
                        "[partition_drop] %s is %d months old but not in S3 manifest — skipping",
                        part_name, age_months,
                    )
                    continue
                stats["confirmed_in_s3"] += 1

                if not ENABLED:
                    logger.info(
                        "[partition_drop] DRY-RUN — would detach+drop %s (age=%d mo, in manifest)",
                        part_name, age_months,
                    )
                    continue

                # Execute detach + drop. DETACH is O(1) metadata; DROP
                # reclaims disk immediately.
                try:
                    await conn.execute(
                        f"ALTER TABLE public.{parent} DETACH PARTITION public.{part_name}"
                    )
                    await conn.execute(f"DROP TABLE public.{part_name}")
                    stats["dropped"] += 1
                    stats["dropped_parts"].append(part_name)
                    logger.info(
                        "[partition_drop] ✓ dropped %s (age=%d mo)",
                        part_name, age_months,
                    )
                except Exception as exc:
                    logger.exception(
                        "[partition_drop] drop failed for %s: %s", part_name, exc,
                    )
                    # Don't re-raise — keep trying other partitions.

        status = "ok"
        # Emit 'error' if we have eligible-but-unexported partitions — the
        # export worker is behind and needs attention. Harmless in dry-run.
        if stats["skipped_no_manifest"]:
            status = "error"
        err_repr = (
            f"{len(stats['skipped_no_manifest'])} partitions old enough but missing from manifest: "
            f"{stats['skipped_no_manifest'][:5]}"
            if stats["skipped_no_manifest"] else None
        )
    finally:
        await conn.close()

    record_run("partition_drop_worker", status, error_repr=err_repr)
    return stats


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [partition_drop] %(levelname)s: %(message)s",
    )
    try:
        stats = await run_once()
        logger.info("Partition drop complete: %s", stats)
    except Exception as e:
        from app.worker_registry import record_run
        record_run(
            "partition_drop_worker", "error",
            error_repr=f"{type(e).__name__}: {e!s}"[:500],
        )
        logger.exception("partition_drop_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
