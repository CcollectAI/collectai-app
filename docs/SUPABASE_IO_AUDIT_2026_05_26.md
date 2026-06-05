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

## Cross-references

- `docs/PHASE_3_QUERY_REWRITES.md` — the queued rewrite plan (gates this work)
- `docs/perf-maintenance-playbook.md` — off-hours maintenance procedure
- `docs/DATA_SCALING_PLAN.md` — 12-month capacity roadmap
- `learning_partition_pruning_planning_cost.md` — pattern + first measurement
- `learning_use_direct_dsn_for_partitioned_writes.md` — pooler limits on partitions
- `learning_tune_one_knob_at_a_time.md`
- `feedback_no_fixes_on_assumptions.md`
- `learning_avoid_bake_restart_for_db_changes.md`
