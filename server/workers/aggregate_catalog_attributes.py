"""
Catalog attribute aggregator — data flywheel (R50k).

Groups market_hits by item_ref (= "{category}:{item_key}") and promotes
the most-observed structured attributes to
`category_items.attributes_json.market_observed`.

For string fields: mode + distribution + confidence.
For numeric fields: median + p25/p75.

A minimum number of observations per value is required before promotion
(default 3, configurable via `--min-obs` or env `ATTR_AGGREGATION_MIN_OBS`).

Feature-flagged behind env `ATTR_AGGREGATION_ENABLED=true` (default false).

Writes use `jsonb_set` targeting the `market_observed` key so we REPLACE
our namespace rather than merging — avoids the R50e JSONB array-vs-object
trap documented in learnings.md.

CLI:
    python -m workers.aggregate_catalog_attributes --dry-run
    python -m workers.aggregate_catalog_attributes --apply
    python -m workers.aggregate_catalog_attributes --dry-run --category pokemon
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from typing import Any, Optional

logger = logging.getLogger(__name__)

_DEFAULT_MIN_OBS = int(os.getenv("ATTR_AGGREGATION_MIN_OBS", "3"))
_WORKER_NAME = "aggregate_catalog_attributes"


# ---------------------------------------------------------------------------
# Aggregation math (pure — testable without DB)
# ---------------------------------------------------------------------------

def _is_numeric(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value)
            return True
        except ValueError:
            return False
    return False


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def aggregate_attrs_for_group(
    hits_attrs: list[dict[str, Any]],
    min_obs: int = _DEFAULT_MIN_OBS,
) -> dict[str, dict[str, Any]]:
    """Aggregate a list of attrs dicts (one per hit) into a summary.

    Returns a dict: {field: {value, n, distribution, confidence}} for strings,
    or {field: {median, n, p25, p75}} for numerics.
    Only fields with >= min_obs total observations are included.
    """
    # Collect values by field
    field_values: dict[str, list[Any]] = defaultdict(list)
    for attrs in hits_attrs:
        if not isinstance(attrs, dict):
            continue
        for field, value in attrs.items():
            # Skip the raw escape hatch — it's not a promotable field
            if field == "attributes_raw":
                continue
            if value is None or value == "":
                continue
            field_values[field].append(value)

    summary: dict[str, dict[str, Any]] = {}
    for field, values in field_values.items():
        if len(values) < min_obs:
            continue

        # Classify as numeric if all values parse to float
        numeric_values = [v for v in (_to_float(x) for x in values) if v is not None]
        if len(numeric_values) >= min_obs and len(numeric_values) == len(values):
            numeric_values.sort()
            n = len(numeric_values)
            summary[field] = {
                "type": "numeric",
                "median": statistics.median(numeric_values),
                "p25": numeric_values[max(0, n // 4)],
                "p75": numeric_values[min(n - 1, (3 * n) // 4)],
                "n": n,
            }
            continue

        # String mode + distribution
        str_values = [str(v).strip() for v in values if str(v).strip()]
        if len(str_values) < min_obs:
            continue
        counter = Counter(str_values)
        mode_value, mode_count = counter.most_common(1)[0]
        confidence = mode_count / len(str_values) if str_values else 0.0
        summary[field] = {
            "type": "string",
            "value": mode_value,
            "n": len(str_values),
            "distribution": dict(counter.most_common(10)),  # cap to top-10
            "confidence": round(confidence, 3),
        }

    return summary


# ---------------------------------------------------------------------------
# DB access
# ---------------------------------------------------------------------------

async def _fetch_groups(conn, category_filter: Optional[str], limit_per_item: int):
    """Stream market_hits grouped by item_ref.

    Returns an async iterator of (category, item_key, [attrs, ...]).
    """
    where = "WHERE mh.item_ref IS NOT NULL AND mh.attrs IS NOT NULL AND mh.attrs <> '{}'::jsonb"
    params: list[Any] = []
    if category_filter:
        where += " AND ci.category = $1"
        params.append(category_filter)

    # Aggregate in DB — emit one row per item_ref with jsonb_agg of attrs.
    # ORDER BY seen_at (was incorrectly created_at — market_hits uses seen_at;
    # the created_at reference errored out on every run, masked by the
    # ATTR_AGGREGATION_ENABLED flag recording status=ok on flag-skip. Fixed
    # 2026-04-19 during silent-sleepers audit.)
    query = f"""
        SELECT ci.category AS category,
               ci.item_key AS item_key,
               jsonb_agg(mh.attrs ORDER BY mh.seen_at DESC) AS attrs_list
        FROM public.market_hits mh
        JOIN public.category_items ci
          ON ci.category = split_part(mh.item_ref, ':', 1)
         AND ci.item_key = split_part(mh.item_ref, ':', 2)
        {where}
        GROUP BY ci.category, ci.item_key
        HAVING count(*) >= 2
    """
    rows = await conn.fetch(query, *params)
    return rows


async def _write_aggregate(conn, category: str, item_key: str, summary: dict[str, Any]) -> None:
    """Write market_observed summary using jsonb_set (namespace replace).

    Critical: this avoids the R50e JSONB `||` merge trap. We target the
    `market_observed` key explicitly so we REPLACE that sub-object rather
    than merging into a possibly-array-typed root.
    """
    # Guard: if attributes_json is currently an array or scalar, reset to object
    # with just our namespace. This is intentional — market_observed is our
    # managed sub-namespace, not user data.
    payload = json.dumps(summary)
    await conn.execute(
        """
        UPDATE public.category_items
        SET attributes_json = CASE
            WHEN attributes_json IS NULL THEN jsonb_build_object('market_observed', $3::jsonb)
            WHEN jsonb_typeof(attributes_json) = 'object'
                THEN jsonb_set(attributes_json, '{market_observed}', $3::jsonb, true)
            ELSE jsonb_build_object('market_observed', $3::jsonb)
        END
        WHERE category = $1 AND item_key = $2
        """,
        category,
        item_key,
        payload,
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

async def run_once(
    dry_run: bool = True,
    category_filter: Optional[str] = None,
    min_obs: int = _DEFAULT_MIN_OBS,
) -> dict[str, Any]:
    """Run a single aggregation pass. Returns summary stats."""
    start = time.time()
    stats = {
        "groups_scanned": 0,
        "groups_promoted": 0,
        "fields_promoted": 0,
        "dry_run": dry_run,
        "min_obs": min_obs,
    }

    # Feature flag
    if not dry_run and os.getenv("ATTR_AGGREGATION_ENABLED", "false").lower() != "true":
        logger.warning(
            "[%s] ATTR_AGGREGATION_ENABLED is not 'true' — apply mode disabled. "
            "Set env to enable writes.", _WORKER_NAME,
        )
        stats["skipped_flag"] = True
        # Record as error, NOT ok — skipping because of a feature flag being
        # off is a silent-sleeper signal, not a healthy outcome. Per the
        # R50l correctness-over-liveness rule this distinction matters.
        _record_run_safe(stats, status="error")
        return stats

    try:
        from app.db import get_conn, db_configured
    except ImportError:
        logger.error("[%s] DB module not available", _WORKER_NAME)
        stats["error"] = "db_unavailable"
        _record_run_safe(stats, status="error")
        return stats

    if not db_configured():
        logger.info("[%s] DB not configured", _WORKER_NAME)
        stats["skipped_db"] = True
        _record_run_safe(stats)
        return stats

    sample_output: list[dict[str, Any]] = []
    try:
        async with get_conn() as conn:
            rows = await _fetch_groups(conn, category_filter, limit_per_item=500)
            for row in rows:
                stats["groups_scanned"] += 1
                category = row["category"]
                item_key = row["item_key"]
                attrs_list_raw = row["attrs_list"]
                # asyncpg returns jsonb as str for older versions; handle both
                if isinstance(attrs_list_raw, str):
                    attrs_list = json.loads(attrs_list_raw)
                else:
                    attrs_list = attrs_list_raw
                if not isinstance(attrs_list, list):
                    continue
                summary = aggregate_attrs_for_group(attrs_list, min_obs=min_obs)
                if not summary:
                    continue
                stats["groups_promoted"] += 1
                stats["fields_promoted"] += len(summary)

                if len(sample_output) < 5:
                    sample_output.append({
                        "item_ref": f"{category}:{item_key}",
                        "hits_analyzed": len(attrs_list),
                        "fields": list(summary.keys()),
                        "sample_field": next(iter(summary.items()), None),
                    })

                if not dry_run:
                    try:
                        await _write_aggregate(conn, category, item_key, summary)
                    except Exception as e:
                        logger.warning(
                            "[%s] write failed for %s:%s — %s",
                            _WORKER_NAME, category, item_key, e,
                        )
    except Exception as e:
        logger.error("[%s] aggregator failed: %s", _WORKER_NAME, e, exc_info=True)
        stats["error"] = str(e)
        _record_run_safe(stats, status="error")
        return stats

    stats["duration_s"] = round(time.time() - start, 2)
    stats["sample"] = sample_output
    logger.info("[%s] %s", _WORKER_NAME, json.dumps({k: v for k, v in stats.items() if k != "sample"}))
    _record_run_safe(stats)
    return stats


def _record_run_safe(stats: dict[str, Any], status: str = "ok") -> None:
    """Record worker run; never raise."""
    try:
        from app.worker_registry import record_run
        record_run(_WORKER_NAME, status=status, duration_s=stats.get("duration_s"))
    except Exception:
        logger.debug("[%s] record_run failed", _WORKER_NAME, exc_info=True)


# ---------------------------------------------------------------------------
# Long-running worker loop (registered in worker_registry; default interval 6h)
# ---------------------------------------------------------------------------

async def run_forever(interval_s: int = 6 * 3600) -> None:
    while True:
        try:
            await run_once(dry_run=False)
        except Exception as e:
            logger.error("[%s] loop error: %s", _WORKER_NAME, e, exc_info=True)
        await asyncio.sleep(interval_s)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> int:
    parser = argparse.ArgumentParser(description="Aggregate market_hits.attrs into category_items.attributes_json.market_observed")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--dry-run", action="store_true", help="Compute aggregates but do not write to DB")
    grp.add_argument("--apply", action="store_true", help="Write aggregates to DB (requires ATTR_AGGREGATION_ENABLED=true)")
    parser.add_argument("--category", type=str, default=None, help="Restrict to one category")
    parser.add_argument("--min-obs", type=int, default=_DEFAULT_MIN_OBS, help="Minimum observations per value")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    stats = asyncio.run(run_once(
        dry_run=args.dry_run,
        category_filter=args.category,
        min_obs=args.min_obs,
    ))
    print(json.dumps(stats, indent=2, default=str))
    return 0 if "error" not in stats else 1


if __name__ == "__main__":
    sys.exit(_cli())
