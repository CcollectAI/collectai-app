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
  DATALAKE_BUCKET   — S3 bucket name (default: collectai-warehouse-prod-eu-north-1)
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

BUCKET = os.getenv("DATALAKE_BUCKET", "collectai-warehouse-prod-eu-north-1")
REGION = os.getenv("DATALAKE_REGION", "eu-north-1")
ENABLED = os.getenv("DATALAKE_ENABLED", "false").lower() == "true"
MANIFEST_KEY = "manifests/exports.jsonl"


def _partition_s3_key(partition_name: str, year: int, month: int) -> str:
    """Returns e.g. market_hits/year=2026/month=04/part-000.snappy.parquet"""
    return f"market_hits/year={year:04d}/month={month:02d}/part-000.snappy.parquet"


# 2026-04-24: tables to archive that AREN'T partitioned. Bucketed by month
# from a timestamp column. Each bucket older than the current month is exported
# once (manifest dedup); the prune worker (separate) drops the rows after a
# retention window so a bad export can be reversed.
TIME_BUCKETED_TABLES = [
    # (table, time_col, s3_prefix, manifest_partition_format)
    ("price_predictions", "generated_at", "price_predictions"),
    ("price_history",     "as_of",        "price_history"),
]


def _bucket_s3_key(s3_prefix: str, year: int, month: int) -> str:
    return f"{s3_prefix}/year={year:04d}/month={month:02d}/part-000.snappy.parquet"


def _bucket_manifest_id(s3_prefix: str, year: int, month: int) -> str:
    """Stable identifier for the manifest. Mirrors partition naming so dedup
    works the same way as the market_hits partition path."""
    return f"{s3_prefix}_y{year:04d}m{month:02d}"


def _row_to_arrow_safe(row) -> dict:
    """Convert asyncpg Record -> dict with UUIDs stringified.
    pyarrow.Table.from_pylist can't auto-infer asyncpg.pgproto.UUID; the
    cleanest fix is to stringify at the boundary before Arrow conversion.
    Same for any other non-primitive types we hit later (datetime.date is
    handled natively by pyarrow)."""
    import uuid as _uuid
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, _uuid.UUID):
            d[k] = str(v)
    return d


# Bounded streaming: how many rows to hold in memory per Parquet part file.
# 50k rows ≈ ~100 MB peak (rows + Arrow copy) — fits comfortably on the
# t3.medium (~2.4 GB free) no matter how large the partition is. The old
# single-shot `conn.fetch(SELECT *)` loaded the whole partition (2 GB+ for a
# full month) and would OOM the box. Tunable via DATALAKE_EXPORT_BATCH_ROWS.
EXPORT_BATCH_ROWS = int(os.getenv("DATALAKE_EXPORT_BATCH_ROWS", "50000"))


def _part_key(s3_dir: str, idx: int) -> str:
    """e.g. market_hits/year=2026/month=05 + idx 0 -> .../part-000.snappy.parquet"""
    return f"{s3_dir}/part-{idx:03d}.snappy.parquet"


async def _stream_export_to_s3(conn, s3, *, query: str, params: tuple, s3_dir: str):
    """Stream a SELECT to S3 as one or more snappy Parquet part files using a
    server-side cursor, so peak memory is bounded to EXPORT_BATCH_ROWS rows
    regardless of partition size.

    Writes part-000, part-001, … under s3_dir. The warm_tier reader globs
    `part-*.snappy.parquet` with union_by_name, so multiple parts read back as
    one logical table. Returns (total_rows, total_bytes, n_parts).
    """
    import pyarrow as pa  # type: ignore
    import pyarrow.parquet as pq  # type: ignore

    total_rows = 0
    total_bytes = 0
    part_idx = 0
    # Server-side cursor must run inside a transaction. The partition is a
    # closed month (no concurrent writes), so the held snapshot is safe.
    async with conn.transaction():
        cur = await conn.cursor(query, *params)
        while True:
            batch = await cur.fetch(EXPORT_BATCH_ROWS)
            if not batch:
                break
            tbl = pa.Table.from_pylist([_row_to_arrow_safe(r) for r in batch])
            with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                pq.write_table(tbl, tmp_path, compression="snappy")
                size_bytes = tmp_path.stat().st_size
                s3.upload_file(str(tmp_path), BUCKET, _part_key(s3_dir, part_idx))
                total_rows += len(batch)
                total_bytes += size_bytes
                part_idx += 1
            finally:
                tmp_path.unlink(missing_ok=True)
            del tbl, batch  # release before the next fetch
    return total_rows, total_bytes, part_idx


def _append_manifest(s3, entry: dict) -> None:
    """Append one JSON line to the exports manifest (read-modify-write of a
    single small file). Written only after all part files for a month upload
    OK, so an interrupted run leaves no manifest entry and is safely re-run."""
    existing_body = b""
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=MANIFEST_KEY)
        existing_body = obj["Body"].read()
    except s3.exceptions.NoSuchKey:
        pass
    new_body = existing_body + (json.dumps(entry) + "\n").encode("utf-8")
    s3.put_object(Bucket=BUCKET, Key=MANIFEST_KEY, Body=new_body)


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
    # Bounded 2026-05-04 (was 0/unbounded). 30 min headroom for bulk parquet export.
    await conn.execute("SET statement_timeout = '1800s'")

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

    import re as _re
    _PART_RE = _re.compile(r"y(\d{4})m(\d{2})")
    for part in to_export:
        # Parse y2026m04 → (2026, 4). Old split-based parser broke on
        # any partition name containing 'm' (every market_hits_y* did).
        m = _PART_RE.search(part)
        if not m:
            logger.warning("[datalake_export] unparseable partition name: %s", part)
            continue
        year, month = int(m.group(1)), int(m.group(2))

        n_rows = await conn.fetchval(f"SELECT COUNT(*) FROM public.{part}")
        if n_rows == 0:
            logger.info("[datalake_export] %s empty, skipping", part)
            continue

        # Stream rows → Parquet part files (bounded memory). The old single-
        # shot SELECT loaded the whole partition and would OOM the box at full
        # month size; _stream_export_to_s3 caps peak memory to a single batch.
        s3_dir = f"market_hits/year={year:04d}/month={month:02d}"
        rows_written, size_bytes, n_parts = await _stream_export_to_s3(
            conn, s3, query=f"SELECT * FROM public.{part}", params=(), s3_dir=s3_dir,
        )
        if rows_written == 0:
            continue

        _append_manifest(s3, {
            "partition": part,
            "s3_dir": s3_dir,
            "parts": n_parts,
            "rows": rows_written,
            "bytes": size_bytes,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        })
        stats["exported"] += 1
        stats["rows"] += rows_written
        stats["bytes"] += size_bytes
        stats["partitions"].append(part)
        logger.info(
            "[datalake_export] ✓ %s → s3://%s/%s/part-*  (%d rows, %d parts, %.1f MB)",
            part, BUCKET, s3_dir, rows_written, n_parts, size_bytes / 1024 / 1024,
        )

    # ----------------------------------------------------------------------
    # 2026-04-24: time-bucketed export for non-partitioned tables.
    # Same parquet+manifest pattern as the partition path; uses (year, month)
    # buckets derived from a timestamp column. Skips the current month.
    # ----------------------------------------------------------------------
    for table, time_col, s3_prefix in TIME_BUCKETED_TABLES:
        # Discover all (year, month) buckets that have rows AND are older than
        # current month. SET operations on millions of rows can be slow; the
        # GROUP BY truncated month is supported by btree on time_col so it's
        # cheap on the indexes that already exist.
        bucket_rows = await conn.fetch(
            f"""
            SELECT EXTRACT(YEAR FROM {time_col})::int  AS year,
                   EXTRACT(MONTH FROM {time_col})::int AS month,
                   COUNT(*) AS n
            FROM public.{table}
            WHERE {time_col} IS NOT NULL
              AND date_trunc('month', {time_col}) < date_trunc('month', now())
            GROUP BY 1, 2
            ORDER BY 1, 2
            """
        )

        for r in bucket_rows:
            year, month, n_rows = int(r["year"]), int(r["month"]), int(r["n"])
            mid = _bucket_manifest_id(s3_prefix, year, month)
            if mid in exported:
                continue

            # Stream this month's rows → Parquet part files (bounded memory).
            # price_predictions months are ~2M rows now — single-shot loaded
            # all of it and would OOM; the cursor caps memory to one batch.
            s3_dir = f"{s3_prefix}/year={year:04d}/month={month:02d}"
            rows_written, size_bytes, n_parts = await _stream_export_to_s3(
                conn, s3,
                query=f"""
                    SELECT * FROM public.{table}
                    WHERE {time_col} >= make_date($1, $2, 1)
                      AND {time_col} <  (make_date($1, $2, 1) + interval '1 month')
                """,
                params=(year, month),
                s3_dir=s3_dir,
            )
            if rows_written == 0:
                continue

            _append_manifest(s3, {
                "partition": mid,        # stays as 'partition' so reader dedup doesn't fork
                "table": table,
                "s3_dir": s3_dir,
                "parts": n_parts,
                "rows": rows_written,
                "bytes": size_bytes,
                "exported_at": datetime.now(timezone.utc).isoformat(),
            })
            exported.add(mid)  # so we don't re-export within the same run
            stats["exported"] += 1
            stats["rows"] += rows_written
            stats["bytes"] += size_bytes
            stats["partitions"].append(mid)
            logger.info(
                "[datalake_export] ✓ %s → s3://%s/%s/part-*  (%d rows, %d parts, %.1f MB)",
                mid, BUCKET, s3_dir, rows_written, n_parts, size_bytes / 1024 / 1024,
            )

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
