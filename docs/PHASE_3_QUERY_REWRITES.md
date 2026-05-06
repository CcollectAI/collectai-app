# Phase 3: Partition-Pruning Query Rewrites (queued)

**Status: NOT YET APPLIED.** This document records the planned rewrites
and the gating test sequence. Per `feedback_no_fixes_on_assumptions.md`,
no DB-perf change ships without `EXPLAIN ANALYZE` evidence first.

## Why

2026-05-04 incident: `auction_alert_worker` cycles jumped from 30-50s to
2.6h+ over a single autoanalyze trigger on `market_hits_y2026m04`.
`EXPLAIN` against the parent partitioned table timed out at 15s in
*planning phase* — the planner walked all 9 monthly partitions per query.

Same shape exists in three other kept workers:

| Worker | File:Line | Filter |
|---|---|---|
| `valuation_worker` | `valuation_worker.py:233` | `mh.seen_at > now() - interval '90 days'` |
| `calibration_worker` | `calibration_worker.py:107` | `pp.generated_at > now() - interval '90 days'` |
| `calibration_worker` | `calibration_worker.py:133` | `mh.seen_at > now() - ($2 \|\| ' days')::interval` |
| `marketplace_scrape_scheduler` | (review needed) | (review needed) |
| `auction_alert_worker` | `auction_alert_worker.py:97` | `mh.seen_at > now() - interval '14 days'` |

Today the bounded `statement_timeout` per worker (Phase 2) caps blast
radius — these workers fail fast instead of running for hours. But that
just *contains* the disease. The partition-walk planner regression can
still trigger any time autoanalyze on a hot partition shifts the plan.

## Hypothesis

asyncpg uses extended-protocol prepared statements with generic plans
after 5+ executions. With `now()` (STABLE) inside the SQL, the planner
can't fold the value into the plan at prepare time — partition pruning
happens at execution, but only if the planner kept all partition scans
in the generic plan. When generic plan = walk-all-partitions, every
execution incurs the planning cost across all partitions (memory entry
`learning_partition_pruning_planning_cost.md` measured this at 160ms
planning + 71ms execution on `price_predictions`).

## Planned rewrite

For each occurrence above, replace `now() - interval '...'` with a
Python-computed timestamp bound as a parameter. Pattern:

```python
# Before
rows = await conn.fetch(
    """
    SELECT ... FROM market_hits mh
    WHERE mh.seen_at > now() - interval '14 days'
      AND ...
    """,
)

# After
seen_cutoff = datetime.now(timezone.utc) - timedelta(days=14)
rows = await conn.fetch(
    """
    SELECT ... FROM market_hits mh
    WHERE mh.seen_at > $N::timestamptz
      AND ...
    """,
    seen_cutoff,
    # ...other params
)
```

The `$N::timestamptz` cast is essential — without it asyncpg may bind as
`timestamp` (no tz) and the comparison won't match the `seen_at`
column's `timestamptz` type, defeating partition pruning anyway.

## Gating test sequence (run before merging)

1. Wait until DB recovers enough to run `EXPLAIN ANALYZE` (currently it
   times out at 10s; need < 5s response on a baseline `pg_stat_activity`
   query). Check via:
   ```sql
   SET statement_timeout = '10s';
   SELECT 1;
   ```
2. For each worker query above:
   ```sql
   SET statement_timeout = 0;
   SET work_mem = '256MB';
   EXPLAIN (ANALYZE, BUFFERS, VERBOSE) <existing query, today's now() form>;
   -- capture: planning ms, execution ms, "Subplans Removed: N" count
   ```
3. Apply the rewrite (Python-bound timestamp).
4. Re-run the same `EXPLAIN ANALYZE`. Confirm:
   - Planning time drops dramatically (target: <10ms vs today's likely 100-200ms+)
   - "Subplans Removed: N" appears with N >= partitions_outside_window
   - Execution time at most equal to baseline
5. Only then commit + deploy the rewrite.

## Re-enable auction_alert after Phase 3

Once the rewrite is verified and shipped:
1. Uncomment the manifest entry in `bake_orchestrator.py` (around line 76).
2. Confirm `auction_alert_worker.py:51` already tagged with
   `application_name='collectai-bake-auction_alert_worker'` (TODO if not).
3. Deploy + restart.
4. Watch the next 3 cycles for `auction_alert_worker completed in <60s`.
5. Watch `worker_runs.metadata.error_repr` for any `statement_timeout`.

## Memory updates after Phase 3

- New entry: `learning_runtime_partition_prune_needs_literal_bind.md`
  — supplements `learning_partition_pruning_planning_cost.md` for the
  asyncpg-prepared-statement + STABLE-`now()` case specifically.
- Update `MEMORY.md` index.

## Owner

Solo: Merle. Run when ready, or queue for next session when DB is
healthy enough to capture EXPLAIN ANALYZE without blocking on it.
