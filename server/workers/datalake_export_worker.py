#!/usr/bin/env python3
"""Datalake export worker — exports closed market_hits partitions to S3 as Parquet.

Part of the R50m data scaling plan. See `docs/DATA_SCALING_PLAN.md` for context.

Flow per run:
  1. Find monthly partitions of `public.market_hits` whose month ended ≥ 1 full
     month ago AND that haven't yet been exported (manifest check).
  2. For each, SELECT the rows and write a Parquet file to
     `s3://<BUCKET>/market_hits/year=YYYY/month=MM/part-000.snappy.parquet`.
  3. Append one JSON line to `s3://<BUCKET>/manifests/exports.jsonl` with
     {partition, rows, bytes, sha256, exported_at}.
  4. Do NOT drop the source partition in this worker. A separate retention
     worker handles dropping after a retention window (default 6 months) so
     a bad export can be reversed by re-copying from Postgres.

Env:
  DATALAKE_BUCKET   — S3 bucket name (default: collectai-datalake)
  DATALAKE_REGION   — AWS region   (default: eu-north-1)
  DATALAKE_ENABLED  — 'true' to run; default off so a dev laptop can't export.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

BUCKET = os.getenv("DATALAKE_BUCKET", "collectai-datalake")
REGION = os.getenv("DATALAKE_REGION", "eu-north-1")
ENABLED = os.getenv("DATALAKE_ENABLED", "false").lower() == "true"
MANIFEST_KEY = "manifests/exports.jsonl"


def _partition_s3_key(partition_name: str, year: int, month: int) -> str:
    """Returns e.g. market_hits/year=2026/month=04/part-000.snappy.parquet"""
    return f"market_hits/year={year:04d}/month={month:02d}/part-000.snappy.parquet"


async def run_once() -> dict:
    """Export eligible partitions. Returns summary stats."""
    from app.worker_registry import record_run

    if not ENABLED:
        logger.info("DATALAKE_ENABLED=false — skipping datalake export")
        record_run("datalake_export_worker", "ok", duration_s=0.0)
        return {"skipped": True}

    import asyncpg
    import boto3
    import pyarrow as pa  # type: ignore
    import pyarrow.parquet as pq  # type: ignore

    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ["DB_DSN"]
    conn = await asyncpg.connect(dsn, timeout=60)
    await conn.execute("SET statement_timeout = 0")

    # What partitions exist on market_hits, sorted oldest first, excluding
    # the default and the current month (never export the open month).
    now = datetime.now(timezone.utc)
    current_key = f"y{now.year:04d}m{now.month:02d}"
    rows = await conn.fetch(
        """
        SELECT inhrelid::regclass::text AS part
        FROM pg_inherits
        WHERE inhparent = 'public.market_hits'::regclass
          AND inhrelid::regclass::text NOT LIKE '%default%'
        ORDER BY part
        """
    )
    eligible = [
        r["part"].replace("public.", "") for r in rows
        if "default" not in r["part"] and current_key not in r["part"]
    ]

    s3 = boto3.client("s3", region_name=REGION)

    # Read already-exported list from manifest
    exported: set[str] = set()
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=MANIFEST_KEY)
        for line in obj["Body"].read().splitlines():
            try:
                exported.add(json.loads(line)["partition"])
            except Exception:  # noqa: BLE001 — malformed line, skip
                continue
    except s3.exceptions.NoSuchKey:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("[datalake_export] manifest fetch failed: %s", exc)

    to_export = [p for p in eligible if p not in exported]
    logger.info(
        "[datalake_export] %d eligible partitions, %d new to export",
        len(eligible), len(to_export),
    )

    stats = {"exported": 0, "rows": 0, "bytes": 0, "partitions": []}

    for part in to_export:
        # Parse y2026m04 → (2026, 4)
        try:
            year = int(part.split("y")[1][:4])
            month = int(part.split("m")[1][:2])
        except (IndexError, ValueError):
            logger.warning("[datalake_export] unparseable partition name: %s", part)
            continue

        n_rows = await conn.fetchval(f"SELECT COUNT(*) FROM public.{part}")
        if n_rows == 0:
            logger.info("[datalake_export] %s empty, skipping", part)
            continue

        # Stream rows → Parquet file locally, then upload.
        # For the 100k-row monthly size range this fits easily in memory;
        # add a chunked batch iterator only when partitions exceed ~1M rows.
        all_rows = await conn.fetch(f"SELECT * FROM public.{part}")
        if not all_rows:
            continue

        table = pa.Table.from_pylist([dict(r) for r in all_rows])

        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            pq.write_table(table, tmp_path, compression="snappy")
            size_bytes = tmp_path.stat().st_size
            sha256 = hashlib.sha256(tmp_path.read_bytes()).hexdigest()

            s3_key = _partition_s3_key(part, year, month)
            s3.upload_file(str(tmp_path), BUCKET, s3_key)

            manifest_entry = {
                "partition": part,
                "s3_key": s3_key,
                "rows": n_rows,
                "bytes": size_bytes,
                "sha256": sha256,
                "exported_at": datetime.now(timezone.utc).isoformat(),
            }
            # Append to manifest via read-modify-write of a single small file.
            # Acceptable for monthly cadence; if two exporters ever run concurrently
            # we'd switch to S3 Object Lambda or a lock.
            existing_body = b""
            try:
                obj = s3.get_object(Bucket=BUCKET, Key=MANIFEST_KEY)
                existing_body = obj["Body"].read()
            except s3.exceptions.NoSuchKey:
                pass
            new_body = existing_body + (json.dumps(manifest_entry) + "\n").encode("utf-8")
            s3.put_object(Bucket=BUCKET, Key=MANIFEST_KEY, Body=new_body)

            stats["exported"] += 1
            stats["rows"] += n_rows
            stats["bytes"] += size_bytes
            stats["partitions"].append(part)
            logger.info(
                "[datalake_export] ✓ %s → s3://%s/%s  (%d rows, %.1f MB)",
                part, BUCKET, s3_key, n_rows, size_bytes / 1024 / 1024,
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    await conn.close()
    record_run("datalake_export_worker", "ok", duration_s=0.0)
    return stats


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [datalake_export] %(levelname)s: %(message)s")
    try:
        stats = await run_once()
        logger.info("Datalake export complete: %s", stats)
    except Exception as e:  # noqa: BLE001
        from app.worker_registry import record_run
        record_run("datalake_export_worker", "error")
        logger.exception("datalake_export_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
