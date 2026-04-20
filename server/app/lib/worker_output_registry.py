"""Worker output registry — declarative contract per worker.

Each worker's entry records where its primary side-effect lands. The
silent_writer probe cross-checks "worker recorded ok in last 2h" against
"declared output row moved in last N hours" and pages when they diverge.

Added 2026-04-20 after 5 days of instance-by-instance bugfixing revealed
the same failure mode: workers swallow exceptions, log WARNING, and then
record `status=ok` — so `worker_runs` shows all-green while the observable
output has been stale for days. Fixing this requires a declarative
contract + a probe that enforces it, not another round of manual patches.

Example:
    WORKER_OUTPUTS["marketplace_scrape_worker"] = WorkerOutput(
        table="market_hits",
        timestamp_column="seen_at",
        max_staleness_hours=2,  # worker runs every 5m, 2h = 24× interval
    )

If a registered worker has ok runs in the last 2h but its output table's
most recent timestamp is older than max_staleness_hours, that's a
silent-writer violation. The probe pages Telegram with the diagnosis.

Workers that don't produce observable table output (probes, audits,
exports to S3) are intentionally absent — their health is tracked by
run cadence alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class WorkerOutput:
    """Declarative contract: where a worker's side-effects are observable."""

    table: str
    """Postgres table that receives the worker's writes."""

    timestamp_column: str
    """Column on `table` holding the write timestamp (MAX is used)."""

    max_staleness_hours: float
    """Trip threshold — if MAX(timestamp_column) is older than this, and
    the worker has had `ok` runs recently, flag as silent-writer. Usually
    2–4× the worker's schedule interval to give headroom for yielding."""

    where_clause: Optional[str] = None
    """Optional SQL predicate scoping the check — e.g. for a shared
    alerts_outbox table, scope to this worker's own `kind` value.
    Injected verbatim as `AND (<clause>)`. Never accept user input here."""


# Registry — one entry per worker that has a deterministic observable
# output. New workers should add themselves here; probes/audits/exports
# that don't produce table rows are intentionally omitted.
WORKER_OUTPUTS: dict[str, WorkerOutput] = {
    "marketplace_scrape_worker": WorkerOutput(
        table="market_hits",
        timestamp_column="seen_at",
        max_staleness_hours=2.0,
    ),
    "valuation_worker": WorkerOutput(
        table="price_predictions",
        timestamp_column="generated_at",
        max_staleness_hours=12.0,
    ),
    "catalog_learning_worker": WorkerOutput(
        table="category_items",
        timestamp_column="updated_at",
        max_staleness_hours=6.0,
    ),
    "catalog_crawler_worker": WorkerOutput(
        table="category_items",
        timestamp_column="last_crawled_at",
        max_staleness_hours=48.0,  # daily crawl, 2× interval
    ),
    "feedback_loop_worker": WorkerOutput(
        table="price_ground_truths",
        timestamp_column="recorded_at",
        max_staleness_hours=24.0,  # may legitimately be empty for new users
    ),
    "event_scraper_worker": WorkerOutput(
        table="events",
        timestamp_column="created_at",
        max_staleness_hours=12.0,
    ),
    "calibration_worker": WorkerOutput(
        table="calibration_snapshots",
        timestamp_column="created_at",
        max_staleness_hours=48.0,
    ),
    "deal_discovery": WorkerOutput(
        table="mandate_deals",
        timestamp_column="discovered_at",
        max_staleness_hours=4.0,
    ),
    # Shared alerts_outbox — scope via `kind` column so workers don't cover
    # for each other.
    "auction_alert_worker": WorkerOutput(
        table="alerts_outbox",
        timestamp_column="created_at",
        max_staleness_hours=24.0,  # legit to have no auctions ending
        where_clause="kind = 'auction_ending'",
    ),
    "signal_alerts_worker": WorkerOutput(
        table="alerts_outbox",
        timestamp_column="created_at",
        max_staleness_hours=24.0,
        where_clause="kind = 'signal'",
    ),
    "value_change_worker": WorkerOutput(
        table="alerts_outbox",
        timestamp_column="created_at",
        max_staleness_hours=72.0,  # daily worker + legit no-value-change days
        where_clause="kind = 'value_change'",
    ),
    # aggregate_catalog_attributes writes a watermark `_last_aggregated_at`
    # into category_items.attributes_json.market_observed — the check
    # extracts it via ->>'_last_aggregated_at'. Added 2026-04-20 along with
    # the watermark field so the worker is actually observable.
    "aggregate_catalog_attributes": WorkerOutput(
        table="category_items",
        timestamp_column=(
            "(attributes_json->'market_observed'->>'_last_aggregated_at')::timestamptz"
        ),
        max_staleness_hours=24.0,  # 6h schedule, 4× interval for headroom
    ),
}


def get_worker_output(worker_name: str) -> Optional[WorkerOutput]:
    """Return the declared output for `worker_name`, or None if not registered."""
    return WORKER_OUTPUTS.get(worker_name)
