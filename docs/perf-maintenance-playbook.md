# Perf maintenance window playbook

**Why this exists:** ANALYZE on a busy production DB competes for IO with bake
workers. CREATE INDEX CONCURRENTLY on EBS-throttled volumes can take >1h on
mid-size tables. Both are safer in a maintenance window with bake paused.

**When to run:** off-hours (Sunday early morning EU time is quiet for the
matview/discogs workers). Plan ~30 min total.

## Pre-flight (5 min)

1. Note current bake worker activity:
   ```sh
   ssh collectai "sudo systemctl status collectai-bake | head -5"
   ssh collectai "sudo tail -30 /opt/collectors/bake.log | grep -E 'TimeoutError|consecutive'"
   ```
2. Snapshot stuck queries (don't terminate yet — look for patterns):
   ```sh
   scp /tmp/check_active.py collectai:/tmp/  # see scripts/snippets/
   ssh collectai "sudo bash -c '...env...; .venv/bin/python -u /tmp/check_active.py'"
   ```

## Step 1 — pause workers (1 min)

Leaves the FastAPI bake serving requests but tells the orchestrator to skip
worker iterations. Look for the `_circuit_breaker_monitor` switch in
`bake_orchestrator.py` (or just stop and restart bake at the end).

```sh
ssh collectai "sudo systemctl stop collectai-bake"
```

## Step 2 — apply ANALYZE (3-15 min)

```sh
scp /tmp/run_analyzes.py collectai:/tmp/
ssh collectai "sudo bash -c 'set -a; . /opt/collectors/.env; set +a; \
   /opt/collectors/.venv/bin/python -u /tmp/run_analyzes.py'"
```

Tables in order (smallest first; biggest last so we know how long it took):
1. `notification_history` (5 rows — instant)
2. `items` (6 rows — instant)
3. `events` (~2k rows — < 1s)
4. `category_items` (140k rows — typically 5-20s; if > 60s, the disk is throttled)
5. `price_predictions` (partitioned, all leaf partitions — typically 30-60s)

## Step 3 — verify planner picked up stats (1 min)

```sh
scp /tmp/perf_verify.py collectai:/tmp/
ssh collectai "sudo bash -c 'set -a; . /opt/collectors/.env; set +a; \
   /opt/collectors/.venv/bin/python -u /tmp/perf_verify.py'"
```

Expected:
- `notif_history unread_count`: Bitmap Index Scan on `idx_notification_history_user_unread`, planning < 10 ms, execution < 5 ms
- `category_items ILIKE`: Bitmap Index Scan on `idx_category_items_title_trgm`, execution < 100 ms
- `portfolio_cat_breakdown`: Subplans Removed > 0, planning < 50 ms, execution < 1 s

If planning time is still > 100 ms on tiny tables, that's catalog bloat —
needs `VACUUM (ANALYZE, VERBOSE) pg_class` (Supabase managed; file ticket
if persistent).

## Step 4 — restart bake (5 min)

```sh
ssh collectai "sudo systemctl start collectai-bake"
# wait until active
until ssh collectai "sudo systemctl is-active collectai-bake 2>&1" | grep -q '^active$'; do sleep 5; done
```

The first ~2 min after restart, bake's preflight gates run + workers
re-warm. Don't probe during this window.

## Step 5 — confirm workers are back (2 min)

```sh
ssh collectai "sudo tail -30 /opt/collectors/bake.log | grep -v -E 'INFO.*GET|INFO.*POST'"
```

Look for:
- `marketplace_scrape ... persisted N hits` — fresh successful batch
- No `TimeoutError` or `consecutive_error` in the last 5 min
- No Telegram pages in your channel

## Rollback / stuck

If anything went wrong:

```sh
ssh collectai "sudo systemctl restart collectai-bake"
```

This is always safe — bake recovers in ~5 min and workers self-heal on the
next iteration. Do NOT `pg_terminate_backend` worker queries; let them die
naturally on the bake stop.

## Known pitfalls (from 2026-04-30 / 2026-05-01 incidents)

- **CREATE INDEX CONCURRENTLY on category_items took 86 min** — EBS IOPS
  throttling. If it's still running after 30 min, prefer dropping the
  CONCURRENTLY (locks the table briefly but builds in seconds). 140k-row
  GIN trigram should normally take 5-15 sec.
- **`pg_terminate_backend` on worker queries triggers consecutive-error
  pages within 60s.** Never blanket-kill `pg_stat_activity`. See
  `feedback_dont_terminate_active_queries_in_prod.md`.
- **Bake restart costs 5+ min** (preflight + worker re-warm). Batch any
  code+DB changes so you only pay it once.
