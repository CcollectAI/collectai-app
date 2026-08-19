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

    input_exists_sql: Optional[str] = None
    """Optional SQL that returns a single row with column `cnt` (integer).
    If cnt == 0, the silent-writer check is SKIPPED — this lets us avoid
    false-positive pages in low-traffic environments where a worker
    legitimately has no input (no active users, no mandates, no auctions,
    etc.). Injected verbatim. Never accept user input here."""


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
        # The worker reads catalog_suggestions and writes category_candidates
        # (and updates catalog_suggestions.status). It does NOT write
        # category_items — that's catalog_crawler_worker's job. Earlier the
        # probe was pointed at category_items.updated_at, which never moved
        # when this worker ran, so SILENT WRITER kept paging despite the
        # worker doing its actual job correctly. Track category_candidates
        # instead — that's what this worker actually populates / promotes.
        # `category_candidates` has no `updated_at`; the writer bumps
        # `last_seen` on every ON CONFLICT update, so that's the column the
        # probe must read. Pre-fix the probe SQL errored every cycle with
        # `column "updated_at" does not exist`, masking real silent-writer
        # signal behind a harmless-looking warning.
        table="category_candidates",
        timestamp_column="last_seen",
        max_staleness_hours=24.0,
        # Worker Step 2 only writes when ≥2 pending suggestions exist for a
        # *new* category (one not already in category_items). Without those
        # two conditions, 0 candidate rows is the correct outcome. Earlier
        # gate just counted any pending row, which fired a false-positive
        # silent_writer alert pre-launch with 1 demo suggestion.
        input_exists_sql=(
            "SELECT COUNT(*) AS cnt FROM ("
            "  SELECT suggested_category"
            "    FROM public.catalog_suggestions"
            "   WHERE status IN ('pending','new_category')"
            "     AND suggested_category IS NOT NULL"
            "     AND suggested_category NOT IN ("
            "       SELECT DISTINCT category FROM public.category_items"
            "        WHERE category IS NOT NULL"
            "     )"
            "   GROUP BY suggested_category"
            "  HAVING count(*) >= 2"
            ") t"
        ),
    ),
    "catalog_crawler_worker": WorkerOutput(
        table="category_items",
        timestamp_column="last_crawled_at",
        max_staleness_hours=48.0,  # daily crawl, 2× interval
    ),
    "feedback_loop_worker": WorkerOutput(
        table="price_ground_truths",
        timestamp_column="recorded_at",
        max_staleness_hours=48.0,
        # Only flag if there are unprocessed label_events.correction rows
        # waiting to turn into ground truths. Empty input = nothing to do.
        input_exists_sql=(
            "SELECT COUNT(*) AS cnt FROM public.label_events "
            "WHERE action = 'correction' AND processed_at IS NULL"
        ),
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
        max_staleness_hours=24.0,
        # Only flag if there are active purchase_mandates to scan against.
        # Empty mandates = 0 output is correct, not a silent failure.
        input_exists_sql=(
            "SELECT COUNT(*) AS cnt FROM public.purchase_mandates "
            "WHERE status = 'active' AND (expires_at IS NULL OR expires_at > now())"
        ),
    ),
    # auction_alert_worker writes to alert_trigger_history with
    # trigger_type='auction_ending' (not alerts_outbox — corrected round 6
    # 2026-04-20). Input gate narrowed to current-month market_hits
    # partition so it doesn't scan the full partitioned set and time out
    # on the pooler.
    "auction_alert_worker": WorkerOutput(
        table="alert_trigger_history",
        timestamp_column="created_at",
        max_staleness_hours=48.0,
        where_clause="trigger_type = 'auction_ending'",
        input_exists_sql=(
            "SELECT COUNT(*) AS cnt FROM public.watchlist_items "
            "WHERE target_price IS NOT NULL"
        ),
    ),
    # value_change_worker writes to alert_trigger_history, not alerts_outbox.
    # max_staleness_hours bumped 96h → 720h (30d) on 2026-04-28: pre-launch
    # state has 2 items + 0 real users, so no value-change events trigger
    # writes. The 96h threshold paged silently every 4 days. Re-tighten to
    # ~96h once active users + items > ~50 (probe correctly fires when there
    # IS input but the worker stops writing). The input_exists_sql gate
    # doesn't help here because the 2 demo items count as "input present".
    "value_change_worker": WorkerOutput(
        table="alert_trigger_history",
        timestamp_column="created_at",
        max_staleness_hours=720.0,
        where_clause="trigger_type IN ('value_change','item_value_change')",
        input_exists_sql=(
            "SELECT COUNT(*) AS cnt FROM public.items"
        ),
    ),
    # aggregate_catalog_attributes writes a watermark `_last_aggregated_at`
    # into category_items.attributes_json.market_observed — the check
    # extracts it via ->>'_last_aggregated_at'. Added 2026-04-20 along with
    # the watermark field so the worker is actually observable.
    # The reminder's output IS its own idempotency record: one
    # notification_history row per (party, offer), scoped by `data->>'kind'`.
    # `input_exists_sql` is the whole point here — the honest steady state of
    # this worker is "nothing to send", and without the gate it would page for
    # doing exactly what it should. It counts trades that are actually OWED a
    # reminder, using the same three predicates as the worker's own query, so
    # "input present, output stale" can only mean the worker stopped writing.
    "grade_reminder_worker": WorkerOutput(
        table="notification_history",
        timestamp_column="created_at",
        max_staleness_hours=48.0,  # hourly schedule; 48h tolerates a quiet day
        where_clause="data->>'kind' = 'p2p_grade_reminder'",
        input_exists_sql=(
            "SELECT COUNT(*) AS cnt FROM public.p2p_offers o "
            "WHERE o.status = 'completed' "
            "  AND o.seller_confirmed_at IS NOT NULL "
            "  AND o.buyer_confirmed_at IS NOT NULL "
            "  AND GREATEST(o.seller_confirmed_at, o.buyer_confirmed_at) "
            "      <= now() - interval '24 hours' "
            "  AND GREATEST(o.seller_confirmed_at, o.buyer_confirmed_at) "
            "      >  now() - interval '7 days' "
            "  AND (NOT EXISTS (SELECT 1 FROM public.member_grades g "
            "                    WHERE g.offer_id = o.id AND g.rater_id = o.buyer_id) "
            "    OR NOT EXISTS (SELECT 1 FROM public.member_grades g "
            "                    WHERE g.offer_id = o.id AND g.rater_id = o.seller_id))"
        ),
    ),
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
