# Supabase IO Audit — 2026-05-26

**Trigger:** Supabase warning that disk IO budget is being burned. User suspected
the May 22 `SUPABASE_MODE=strict` flip (`2e8906e`) rolled back partition protections.

**Outcome:** Hypothesis was wrong. Partitions are intact. Real source is three
hourly `pg_cron` jobs that lack partition-pruning. Fix is already documented in
`docs/PHASE_3_QUERY_REWRITES.md` but never applied.

---

## What is intact (verified live 2026-05-26)

| Surface | State |
|---|---|
| `market_hits` monthly partitions | 9, intact |
| `price_predictions` monthly partitions | 8, intact |
| `price_history` monthly partitions | 4, intact |
| `pg_cron` job 32 (autocreate next-month partition, 25th @ 02:00 UTC) | Active |
| Bake hardening (`af2704b`, May 4) | In git |
| Calibration 10K-row cap (`c6e83fc`, May 19) | In git |
| Server-side commits since 2026-05-22 | **0 — nothing rolled back** |
| DB size | 4.17 GB (under 8 GB Pro tier) |

The 2026-05-22 `SUPABASE_MODE=strict` flip changed FE→DB query *volume* (real
provider replaced mock), not query *patterns*. The DB was already busy with
worker load; the FE flip stacked on top.

---

## Real IO sources (from `pg_stat_statements`)

Top hot queries by mean exec time:

| pg_cron jobid | Schedule | Function | Avg | Calls |
|---|---|---|---|---|
| **16** | `0 * * * *` | `REFRESH MATERIALIZED VIEW CONCURRENTLY mv_item_best_comp_canon` | 56.7 s | 123 |
| **21** | `0 * * * *` | `produce_alerts_price_drop_30d()` | 16.1 s | 160 |
| **24** | `5 * * * *` | `produce_alerts_price_spike_7d()` | 25.2 s | 160 |

External callers:

| Query | Source | Calls in window | Avg |
|---|---|---|---|
| `SELECT count(*) FROM market_hits WHERE seen_at > now() - interval '24 hours'` | `server/app/features/admin_health_router.py:304` (`/admin/bake-summary`) | 632 | 11.3 s |
| `SELECT id, item_ref, source ...` (catalog attrs aggregation) | `server/workers/aggregate_catalog_attributes.py` (~line 30s) | 22 | 15.2 s |

Stopping `collectai-bake` was my first instinct — **wrong**, would have done
nothing for the hot cron jobs.

---

## Why the queries are slow

Per `learning_partition_pruning_planning_cost.md` and `docs/PHASE_3_QUERY_REWRITES.md`:

asyncpg uses extended-protocol prepared statements with generic plans after 5+
executions. With `now()` (STABLE) inside SQL, the planner can't fold the value
into the plan at prepare time. The generic plan = walk all partitions; every
execution pays the planning cost across all partitions.

The fix: replace `now() - interval '...'` in SQL with a Python-computed
`datetime`, bound as `$N::timestamptz`. Same pattern that took
`portfolio_cat_breakdown` from 9.3 s → 177 ms on 2026-05-01 (`d1265b2`).

The `::timestamptz` cast is essential — without it asyncpg may bind as
`timestamp` (no tz), defeating partition pruning.

---

## Three-phase plan (paused awaiting decision)

### Phase A — surgical pg_cron pause, one knob at a time

Per `learning_tune_one_knob_at_a_time.md`. Pause **job 24 only**
(`produce_alerts_price_spike_7d`, heaviest function), measure IO budget over
60 min, decide next step.

```sql
UPDATE cron.job SET active = false WHERE jobid = 24;
-- wait 60 min, check IO budget on Supabase dashboard
-- if budget bleed stops: confirmed source; if not: re-enable, try job 21
UPDATE cron.job SET active = true WHERE jobid = 24;
```

Constraints:
- `_instance_health_monitor` pages on `matview_supply stall > 180m`. Pausing
  jobs 16/21/24 for < 3 h won't trigger; longer will.
- Fully reversible in one SQL statement.
- No bake restart required (per `learning_avoid_bake_restart_for_db_changes.md`).

### Phase B — EXPLAIN ANALYZE before rewriting (per `feedback_no_fixes_on_assumptions.md`)

For each of these 6 queries:

1. `valuation_worker.py:233` — `mh.seen_at > now() - interval '90 days'`
2. `calibration_worker.py:107` — `pp.generated_at > now() - interval '90 days'`
3. `calibration_worker.py:133` — `mh.seen_at > now() - ($2 || ' days')::interval`
4. `auction_alert_worker.py:97` — `mh.seen_at > now() - interval '14 days'`
5. `marketplace_scrape_scheduler` (line TBD)
6. `admin_health_router.py:304` — `seen_at > now() - interval '24 hours'`

Sequence per query:
```sql
SET statement_timeout = 0;
SET work_mem = '256MB';
EXPLAIN (ANALYZE, BUFFERS, VERBOSE) <current query>;
```
Capture: `planning ms`, `execution ms`, `Subplans Removed: N`.

Apply rewrite (Python-bound timestamp + `::timestamptz` cast), re-EXPLAIN,
confirm planning_ms drops and `Subplans Removed` > 0.

Deploy via `scripts/deploy_to_ec2.sh` (per `learning_ec2_deploy_path.md` —
must use `/opt/collectors/server/` not `/opt/collectors/`).

### Phase C — admin_health_router caching — ~~ACTIVE~~ STRUCK 2026-05-26 PM

**Investigation result (2026-05-26, ssh + log forensics):**

- `/opt/collectors/bake.log` shows **100 HTTP hits in 4 days** (89 × 429, 8 × 403, 3 × 200).
- **Last HTTP hit: 2026-05-22 06:11:50** — the service restart timestamp.
  Nothing has called this endpoint in 4+ days.
- Source IP: `127.0.0.1` only. No external poller.
- Caller pattern: bursts of 2–8 hits at restart times → traced to
  `ExecStartPost=postflight_smoke_test.py` in the unit file. Not a poller.
- Rate limiter is engaged and has been silently 429-ing the localhost
  caller since 2026-04-29 — 89% block rate.
- The "daily Telegram digest" the endpoint's docstring claims to feed
  **does not exist in the codebase** (grep returned zero hits).

**Why the audit doc cited 632 calls:** `pg_stat_statements` is
cumulative since the last `pg_stat_statements_reset()`. The 632 figure
was historical (weeks/months), not a recent window. Current rate ≈ zero.

**Decision:** Phase C is moot. No cache needed. Real IO pressure is
the three `pg_cron` jobs (16/21/24) and the worker queries — Phases A/B.

### Phase D — structural (per `docs/DATA_SCALING_PLAN.md`)

- Move `SELECT count(*) FROM market_hits` to a 5-min-refreshed counter matview
- Per-worker IO-budget guardrail: query > N seconds → skip iteration + page
- Migrate older `market_hits` (>90 days) to S3 Parquet warm-tier; keep only hot
  window in Postgres

---

## Decisions needed (when ready to resume)

1. Authorize Phase A — `UPDATE cron.job SET active = false WHERE jobid = 24;`
   for a 60-min measurement window?
2. ~~Identify `/admin/bake-summary` polling source.~~ **Answered 2026-05-26 PM:
   no active poller. See Phase C strike.**
3. Authorize Phase B EXPLAIN ANALYZE capture (uses `statement_timeout = 0`).

## Adjacent issue surfaced during forensics (not part of IO story)

- `/opt/collectors/bake.log` was **896 MB** on EC2, no rotation. Growing
  ~225 MB/day. EBS volume would fill in ~4 months at that rate.
- `_instance_health_monitor` pages on disk > 80% — would trigger an
  out-of-hours alert before it actually broke anything.

### Done 2026-05-26 PM

- Installed `/etc/logrotate.d/collectai-bake` (weekly, 4 rotations,
  gzip, `copytruncate` so no service restart). Config-only install —
  zero IO impact. First rotation happens on next weekly logrotate cron
  run in off-peak hours. Steady state: ~1 GB rolling cap (1 active +
  4 compressed).
- Why config-only and not `logrotate -f` immediately: per
  `docs/perf-maintenance-playbook.md`, this EBS volume is IOPS-throttled
  hard enough that a 1.8 GB copy (read 896 MB + write 896 MB back via
  `copytruncate`) would compete with active worker queries and the
  three hot `pg_cron` jobs. 67% disk usage gives us ~14 days of bake
  growth before pager fires — plenty of slack to wait for the natural
  off-peak rotation window.

---

## Deferred backlog — post-launch (`#post-launch-ops`)

Items surfaced during this audit, intentionally not done now because
they're either off-hours work or require user verification. Pick these
up after Sparrow Collect launches.

### 1. One-time force-rotate the 896 MB bake.log (off-hours window)

The logrotate config is installed but the existing 896 MB log won't
rotate until the next weekly cron run. To recover the 800 MB sooner,
in a quiet window (e.g. 02:00 CEST):

```bash
ssh collectai 'sudo logrotate -f /etc/logrotate.d/collectai-bake'
```

Trigger: only if disk usage gets uncomfortable before the weekly cron
fires. Otherwise, just let nature take its course.

### 2. Verify `/home/ubuntu/collectai/` is orphaned, then delete (recovers 1.8 GB)

Looks like a stale clone from an earlier deploy layout (`/opt/collectors/`
is the live path per `learning_ec2_deploy_path.md`). User crontab refers
to a sibling directory `/home/ubuntu/collectors-merge-recovered/`, NOT
`/home/ubuntu/collectai/`, so likely orphaned. Confirm before deleting
per `learning_dont_allowlist_dead_assert_dead.md`:

```bash
ssh collectai '
  ls -la /home/ubuntu/collectai/.git/HEAD 2>/dev/null
  sudo lsof +D /home/ubuntu/collectai 2>/dev/null | head
  stat /home/ubuntu/collectai | grep Modify
  grep -rl "/home/ubuntu/collectai" /etc/systemd /etc/cron* /home/ubuntu/.profile /home/ubuntu/.bashrc 2>/dev/null
'
```

Only delete if: nothing has it open + last modified weeks/months ago +
no systemd unit or cron entry references it.

### 3. EBS resize 25→50 GB (only if needed)

After items 1+2 you'd be at ~13.3 GB / 24 GB used (55%). Comfortable for
months. Don't resize unless growth picks up.

If/when needed:
- AWS Console → EC2 → Volumes → Modify (online, no downtime)
- Cost: ~€2/month extra on gp3
- After resize, on the instance: `sudo growpart /dev/nvme0n1 1 && sudo resize2fs /dev/nvme0n1p1`

### 4. Audit doc Phase A (cron job 24 pause + 60-min measurement)

Still gated on user authorization. See "Decisions needed" above.

### 5. Audit doc Phase B (worker query rewrites with `EXPLAIN ANALYZE`)

Still gated on user authorization. See "Decisions needed" above.

---

## RESOLVED 2026-06-05 — the actual #1 IO source was missed by this audit

The audit above ranked `pg_stat_statements` by **mean exec time**, which hid the
real budget-burner: a cheap-looking query with a huge call count.

```
UPDATE public.market_hits SET processed = $2 WHERE item_ref = $1
  → 1,211,088 calls · 22 ms mean · 26,305 s total · 20.3M blocks dirtied (~155 GB)
```

`valuation_worker.py` fired this per item_ref group, per cycle, with **no
`seen_at` partition filter** — and because Postgres rewrites a row even when the
new value equals the old one, it re-dirtied **every historical row for the ref
on every cycle** (rows already `processed = true` included). Symptoms while it
ran: 18.5 s query *planning* on the category-page browse, 2-minute `count(*)`
on the 140K-row `category_items`, category pages spinning 8–35 s.

**Fix (commit `64a31bf`)**: predicate now mirrors the worker's fetch window —
`AND processed = false AND seen_at > now() - interval '90 days'`. Partition
pruning intact, no-op rewrites gone. Category browse went 8–35 s → 0.24–0.55 s
warm the same day.

**Lessons for the next audit:**
1. Rank `pg_stat_statements` by `shared_blks_dirtied` and `shared_blks_read`
   *totals*, not mean exec time — churn hides in high-frequency cheap queries.
2. Partition-pruning review must cover **UPDATEs**, not just SELECTs. A flag
   UPDATE on a partitioned table needs both the partition-key floor and a
   `flag = :old_value` guard so unchanged rows aren't rewritten.

---

## RESOLVED 2026-06-09 — Phase A applied: jobs 21 + 24 paused (dead producer)

Re-ranked `pg_stat_statements` by `shared_blks_read` total (per the 06-05 lesson).
The clear #1 and #2 disk-read sources over the ~21-day window:

```
select public.produce_alerts_price_drop_30d()   → 493 calls · 16,994 ms mean · 69.3M blocks read (~540 GB)   [pg_cron job 21, hourly]
select public.produce_alerts_price_spike_7d()    → 494 calls · 23,657 ms mean · 55.8M blocks read (~436 GB)   [pg_cron job 24, hourly]
```

Combined ≈ **47 GB/day of disk reads**. Each call re-aggregates 90 days of
`market_hits` through a live (non-materialized) view chain:
`v_market_lens_item_summary` → `v_item_price_daily_90d` (`DISTINCT ON` +
two `percentile_cont` passes), ≈ 1 GB/call.

**They are a DEAD PRODUCER.** `alerts_outbox` last grew **2025-11-21** (31 rows
total). The only code referencing it is `worker_output_registry.py` (a liveness
monitor) — no endpoint, no FE serves it, and `signal_alerts_worker` (the intended
consumer) has been disabled since 2026-04-21. So ~47 GB/day produced alerts that
nothing reads.

**Action taken** (stronger than the May Phase A proposal, which only suggested
pausing job 24 for measurement — we now have dead-consumer proof, so both went):

```sql
-- cron.job is owned by supabase_admin even on the postgres direct connection;
-- a raw UPDATE cron.job gets "permission denied". Use the SECURITY-DEFINER
-- function with => named args (asyncpg chokes on := + $1 binding).
SELECT cron.alter_job(job_id => 21, active => false);
SELECT cron.alter_job(job_id => 24, active => false);
-- reverse with active => true
```

Fully reversible. `_instance_health_monitor` pages on `matview_supply stall > 180m`;
21/24 are not matviews, so no false page. No bake restart required.

Secondary effect this relieves: the `_HEAVY_LOCK` heavy workers (deal_discovery,
marketplace_scrape) were starving at the gate under the saturation —
`deal_discovery waited 827.0s for heavy gate` (up from ~65s) on 2026-06-09 09:54.

### Durable fix for jobs 21/24 — THREE LAYERS (deferred, gated on a consumer)

Pausing is the tourniquet, not the cure. When the alerts feature is actually
wired to users, replace it with all three layers (cheapest-first):

1. **Hourly → daily.** A 30-day and 7-day price signal does not change hour to
   hour. Daily off-peak = ~96% cut, and it's a one-line schedule change:
   `SELECT cron.alter_job(job_id => 21, schedule => '30 2 * * *');`
2. **Materialize the base.** Turn `v_item_price_daily_90d` into a matview
   refreshed once/day — we already do exactly this for `mv_daily_median_price`
   (job 17) and `category_daily_medians` (job 5). The alert functions then read
   a cheap index scan instead of re-scanning `market_hits`.
3. **Gate on a consumer.** Even cheap, it writes to `alerts_outbox`, which
   `signal_alerts_worker` (disabled) and the FE don't read. Re-enable the
   consumer FIRST, or you're producing into a void.

Until the alerts feature ships a consumer, **paused is the correct state** — a
documented decision, not silent rot.

### Class-level IO fix — Phase B thesis REVISED by EXPLAIN evidence (2026-06-09)

Captured `EXPLAIN (ANALYZE, BUFFERS)` first (per `feedback_no_fixes_on_assumptions.md`)
on the live DB before touching any query — and it **disproved the assumed fix**:

| Query (forced generic plan, mimics asyncpg) | Pruning | Planning | Execution | Cost driver |
|---|---|---|---|---|
| sanity_probe `hourly_baseline` (8-day market_hits scan) | **Subplans Removed: 8** | 6.3 ms | 1813 ms | 306 MB seq-scan of `m06` (571K/614K rows match — 93% selectivity) |
| 24h `count(*) market_hits` | **Subplans Removed: 4** | 4.4 ms | 1492 ms | seq-scan of `m06` |

**Runtime partition pruning already works** with `now()` inline under a generic
plan on this PG version (`Subplans Removed` > 0, planning ≈ 5 ms). So the
"`now()` → `$N::timestamptz`" rewrite buys ~nothing for these simple single-table
scans. (Join-shaped queries — e.g. the `learning_partition_pruning_planning_cost.md`
calibration case — can still defeat pruning; capture EXPLAIN per query, don't
assume either way.)

Two corrections to the earlier framing:
- Jobs **16/17 are MV refreshes whose definitions don't use `now()` at all**
  (`mv_item_best_comp_canon` = per-item LATERAL over `v_market_hits_canon`;
  `mv_daily_median_price` = percentile aggregation). The timestamp rewrite is
  irrelevant to them; their cost is the underlying aggregation/LATERAL.
- `market_hits` has **no standalone `seen_at` index** — only composite
  `(item_ref, seen_at)` / `(category, seen_at)` where `seen_at` is secondary,
  so bare recent-window filters can't use them → seq scan of the 613 MB / 1.23M-row
  current-month partition.

**The genuinely effective levers (capture EXPLAIN per change, none applied yet):**
1. **Reduce monitor/probe frequency.** sanity_probe's `hourly_baseline` reads
   ~306 MB/run; it does not need a 613 MB scan every hour. Biggest, cheapest win.
2. **Pre-aggregate ingest counts.** Maintain a tiny hourly `ingest_counts` rollup
   so volume-drop / count probes read a small table instead of re-scanning raw
   `market_hits`.
3. **BRIN index on `seen_at`** (tiny, ideal for append-only time-ordered data) —
   would help the narrow 1h/24h windows; EXPLAIN to confirm benefit at the actual
   selectivity before adding.
4. **Warm-tier `market_hits` >90d → S3 Parquet** (`DATA_SCALING_PLAN.md`) — shrinks
   total footprint but NOT the current-month hot partition, so it's secondary here.

Do NOT blanket-apply the `$N::timestamptz` rewrite — the evidence says it's wasted
effort for the queries measured.

---

## Job 16 outgrew the timeout, and was fixed (2026-08-12)

`hourly_refresh_best_comp` was **failing 18 of 24 runs/day** with "canceling
statement due to statement timeout". Not a stall — it grew into the ceiling:

| | Duration |
|---|---|
| 2026-05-26 (this audit) | 56.7 s |
| 2026-08-12 measured | **140.5 s** |
| DB `statement_timeout` | 120 s |

Successful runs took 116–120 s and failures died at exactly 121 s, which is what
identifies a timeout rather than an error. The matview is **72 kB** — all of the
cost is the query behind it.

The cause is the shape this audit already described (§"Two corrections"): a
LATERAL per item over `v_market_hits_canon`, where `canonical_category` was a
**correlated subquery evaluated per market_hits row**. 5 rows in
`v_items_canon` × 1,444,719 rows in `market_hits` ≈ 7.2M correlated lookups per
refresh, with no time filter, on a computed predicate no index can serve.

**Applied:** `20260812_speed_up_market_hits_canon.sql` replaces the correlated
subquery with a LEFT JOIN. `category_map.raw_category_lower` is the PRIMARY KEY
(72 rows / 72 distinct, verified), so the join returns at most one row and is
exactly equivalent — proven per-row over all 1,444,926 rows in a single snapshot:
**0 mismatches**. `CREATE OR REPLACE VIEW`, so all 7 dependents and every grant
survive untouched; `mv_daily_median_price` (job 17) reads the same view and gets
the same relief. `preflight_schema_lock` still PASSes (views aren't in the lock).

    140.5 s -> 72.7 s   (measured REFRESH on the live DB)

That was relief, not the cure — 72.7 s against a 120 s ceiling is a 47 s margin
on a table that went 56.7 s → 140.5 s in under three months. **The cure was
applied the same day** (`20260812b_best_comp_aggregate_once.sql`): stop scanning
`market_hits` once per item and aggregate it ONCE.

    140.5 s  ->  72.7 s  (view fix)  ->  7.6 s  (this)

The swap avoided `DROP … CASCADE` entirely: build the new matview alongside,
repoint the three dependents with `CREATE OR REPLACE VIEW` (in place, so their
96 grants never move), drop the old, then `RENAME` the new into its place. View
dependencies are by OID, so after the rename the dependents reference the
original name again and pg_cron job 16's command text needs no edit. All of it
in one transaction.

**Two things the dry run caught that the plan did not anticipate:**

1. **Recreating a relation RESETS its ACL.** The fresh matview picked up
   Supabase's schema DEFAULT PRIVILEGES and came out with `anon=arwdDxtm` and
   `authenticated=arwdDxtm` — rights the original never had, on a relation that
   *cannot carry RLS*, in the PostgREST-exposed `public` schema. A performance
   fix would have silently granted anonymous read. An explicit `REVOKE` is in
   the migration, and the final ACL is diffed against the original
   programmatically: 0 added, 0 removed. **Never eyeball an ACL after a
   recreate.**
2. The old matview carried **two identical unique indexes** on `(item_id)`, both
   maintained on every refresh. One now.

The definition that replaced it:

```sql
SELECT i.id AS item_id, b.hit_id
FROM v_items_canon i
JOIN (SELECT COALESCE(m.canonical_category, lower(mh.category)) AS canonical_category,
             max(mh.id) AS hit_id
      FROM market_hits mh
      LEFT JOIN category_map m ON m.raw_category_lower = lower(mh.category)
      WHERE mh.category IS NOT NULL AND btrim(mh.category) <> ''
      GROUP BY 1) b ON b.canonical_category = i.canonical_category
```

`max(mh.id)` is exactly `ORDER BY id DESC LIMIT 1` for a `NOT NULL` bigint, and
the inner join drops items-with-no-hits exactly as the LATERAL did. Equivalence
was `EXCEPT`-diffed in **both directions (0 rows each way)** against the old
definition over the same snapshot, before the swap.

Verified after applying: `REFRESH … CONCURRENTLY` **7.6 s**, `preflight_schema_lock`,
`preflight_rls_check` and `schema_drift_check` all PASS, ACL unchanged, three
dependents still resolve to `mv_item_best_comp_canon` (no `_v2` left behind).

---

## Cross-references

- `docs/PHASE_3_QUERY_REWRITES.md` — the queued rewrite plan (gates this work)
- `docs/perf-maintenance-playbook.md` — off-hours maintenance procedure
- `docs/DATA_SCALING_PLAN.md` — 12-month capacity roadmap
- `learning_partition_pruning_planning_cost.md` — pattern + first measurement
- `learning_use_direct_dsn_for_partitioned_writes.md` — pooler limits on partitions
- `learning_tune_one_knob_at_a_time.md`
- `feedback_no_fixes_on_assumptions.md`
- `learning_avoid_bake_restart_for_db_changes.md`
