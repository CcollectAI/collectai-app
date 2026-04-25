"""DuckDB query layer for warm-tier S3 parquet reads.

After `partition_drop_worker` drops partitions older than the retention
window (default 6 months), the data is no longer in Postgres — only in
S3 parquet via `datalake_export_worker`. This module exposes that data
back to the app via DuckDB's `read_parquet()` over httpfs.

Why DuckDB:
- Reads parquet directly from S3 with predicate pushdown (only fetches
  needed columns + row groups)
- Zero additional infra — embedded process, no separate query engine
- Same SQL most of our app code already speaks
- 100x cheaper than keeping years of history in Postgres

Cost: ~30-300 ms per query depending on column count + row-group hits.
Acceptable for analytics / trend-chart endpoints; NOT for hot-path item
detail. Hot path stays on Postgres partitioned-table reads.

Usage:
    from app.lib.warm_tier import warm_tier_read

    rows = warm_tier_read(
        "price_predictions",
        year_from=2024, month_from=1,
        year_to=2025, month_to=12,
        where="category = 'mtg' AND q50 > 100",
        limit=500,
    )
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Tables that have been time-bucketed exported via datalake_export_worker.
# Match the s3_prefix values in TIME_BUCKETED_TABLES + the partitioned
# market_hits export path.
WARM_TIER_TABLES: Dict[str, str] = {
    "market_hits":       "market_hits",
    "price_predictions": "price_predictions",
    "price_history":     "price_history",
}

BUCKET = os.getenv("DATALAKE_BUCKET", "collectai-warehouse-prod-eu-north-1")
REGION = os.getenv("DATALAKE_REGION", "eu-north-1")


def _ddb_connection():
    """Build a DuckDB connection with httpfs configured for our S3 bucket.

    A new connection per call is intentional — DuckDB connections are
    cheap and per-request isolation prevents one bad query from
    poisoning shared state.
    """
    import duckdb
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"SET s3_region='{REGION}'")
    ak = os.environ.get("AWS_ACCESS_KEY_ID")
    sk = os.environ.get("AWS_SECRET_ACCESS_KEY")
    if ak and sk:
        con.execute(f"SET s3_access_key_id='{ak}'")
        con.execute(f"SET s3_secret_access_key='{sk}'")
    return con


def _build_glob(table: str, year_from: int, month_from: int,
                year_to: int, month_to: int) -> str:
    """Construct an S3 glob pattern that DuckDB will expand into the
    matching parquet files. We use year-bracket globbing because DuckDB
    handles brace-expansion naturally.

    Example:
        _build_glob("price_predictions", 2025, 6, 2026, 2)
        → s3://bucket/price_predictions/year=2025/month=*/part-*.snappy.parquet
          (DuckDB will then prune by year/month via partition predicates)
    """
    s3_prefix = WARM_TIER_TABLES[table]
    # We over-fetch year glob then filter by month range in SQL — simpler
    # than trying to compose a brace expansion that's correct across year
    # boundaries.
    return f"s3://{BUCKET}/{s3_prefix}/year=*/month=*/part-*.snappy.parquet"


def warm_tier_read(
    table: str,
    *,
    year_from: int,
    month_from: int,
    year_to: int,
    month_to: int,
    where: Optional[str] = None,
    select: str = "*",
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """Run a SELECT against warm-tier parquet for the given date range.

    Parameters:
        table:       one of WARM_TIER_TABLES keys.
        year_from / month_from / year_to / month_to: inclusive bounds on
            the partition's (year, month) tuple. Caller is responsible
            for not selecting massive ranges (~hundreds of millions of
            rows would be slow even with predicate pushdown).
        where:       optional SQL filter applied AFTER predicate
            pushdown. SECURITY: this is concatenated into SQL — caller
            must NOT pass user input directly. Whitelist column names
            and operators in caller.
        select:      column list. SECURITY: same caveat as `where`.
        limit:       hard cap (default 1000).

    Returns rows as a list of dicts.
    """
    if table not in WARM_TIER_TABLES:
        raise ValueError(f"unknown warm-tier table: {table}")
    if limit > 100_000:
        raise ValueError("limit too high — split into chunks")

    glob = _build_glob(table, year_from, month_from, year_to, month_to)
    sql = f"""
        SELECT {select}
        FROM read_parquet('{glob}', hive_partitioning=true)
        WHERE (year > {int(year_from)} OR (year = {int(year_from)} AND month >= {int(month_from)}))
          AND (year < {int(year_to)}   OR (year = {int(year_to)}   AND month <= {int(month_to)}))
        {("AND (" + where + ")") if where else ""}
        LIMIT {int(limit)}
    """
    con = _ddb_connection()
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as exc:
        logger.exception("warm_tier_read failed for %s: %s", table, exc)
        raise
    finally:
        con.close()


def warm_tier_count(
    table: str,
    *,
    year_from: int,
    month_from: int,
    year_to: int,
    month_to: int,
    where: Optional[str] = None,
) -> int:
    """Count rows matching the filter — useful for trend-chart sparklines
    or pre-flight cost estimates before doing a real read."""
    rows = warm_tier_read(
        table,
        year_from=year_from, month_from=month_from,
        year_to=year_to, month_to=month_to,
        where=where, select="COUNT(*) AS n", limit=1,
    )
    return int(rows[0]["n"]) if rows else 0
