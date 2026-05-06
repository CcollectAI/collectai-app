# Sparrow Collect — Data Bake Playbook

> Single-page operator guide. If you read nothing else, read this.

The pre-launch **data bake** runs the backend + workers on EC2 for **7-14 days** so the database accumulates marketplace hits, price predictions, and model calibration data. By the time the app goes to TestFlight / App Store, every scan returns real, calibrated values from day one instead of cold-cache placeholders.

---

## Status (2026-04-09)
- ✅ Catalog **already loaded**: 87,511 `category_items` rows across 37 categories
- ✅ market_hits: 79,449 rows (79,448 with `item_ref` backfilled from `normalized_key` — R46.20)
- ✅ **price_predictions: 3,469 rows / 2,211 distinct items** (valuation pipeline verified live)
- ✅ **price_history: 2,198 rows** (newly populated)
- ✅ Schema drift check (`scripts/schema_drift_check.py`) PASS — 10 critical tables, 98 columns
- ✅ All 20 R46.x bake-blocker fixes applied (R46.3 → R46.20, see `memory3.md`)
- ✅ Valuation pipeline verified end-to-end: market_hits → valuation_worker → price_predictions
- ⏳ EC2 host not yet provisioned — once it exists, run `bake_start.sh` to start the workers
- ⏳ mtg + retro_pokemon import retry (2/39 pipelines failed during bulk run)
- ⚠️ **trg_price_history_latest is DISABLED** for the bake (would write nulls into item_latest_price_mat which has a NOT NULL primary key on item_id). Re-enable after first real users sign up. See R46.19 in memory3.md.

## TL;DR — start the bake

```bash
ssh ubuntu@51.21.210.195
cd ~/CcollectAI
git pull
./scripts/bake_start.sh                     # safe default — won't apply migrations or reimport
./scripts/bake_start.sh --apply-migrations  # if alembic shows pending migrations
./scripts/bake_start.sh --force-reimport    # if you need to rebuild catalog from scratch
```

Then check from your laptop daily:

```bash
./scripts/bake_status.sh    # one-screen health snapshot via /admin/bake-summary
./scripts/bake_tail.sh 200  # last 200 log lines via SSH
./scripts/bake_stop.sh      # clean shutdown when bake is done
```

A **Telegram message** also fires once at startup and at every 75/90/100% spend threshold (configured in Round 41).

---

## What "ready" looks like

After 7-14 days the bake is "done" when `bake_status.sh` shows:

- `catalog_items_total >= 40,000` (catalog seeded)
- `market_hits_total >= 50,000` and `market_hits_24h > 1,000` (workers active)
- `price_predictions_total >= 5,000` (valuation worker producing q10/q50/q90)
- `alert_history_24h > 0` (price monitor firing)
- All workers green (last_status = "ok", not "overdue")
- Spend at < 50% of budget (so launch traffic has headroom)
- 0 warnings

---

## The 7 gotchas — and what the script does about them

| # | Gotcha | Safeguard in `bake_start.sh` |
|---|---|---|
| **G1** | **Migration drift** — prod DB out of sync with `supabase/migrations/` | Refuses to `alembic upgrade head` unless `--apply-migrations` is passed. Greps for `DROP TABLE/COLUMN/SCHEMA/DATABASE` without `IF EXISTS` and aborts if found — eyeball them manually first. |
| **G2** | **Memory pressure** during catalog import (~46k items, 5-15 min, OOM risk on `t3.small`) | Calls `free -m`, warns + 5s pause if `<4GB` total RAM. Recommend `t3.medium` or larger before launch. |
| **G3** | **Catalog import is not idempotent** in all 58 pipelines — re-running can create duplicates | Counts `catalog_items` first. Skips import if `>= 1000` rows. Use `--force-reimport` to `TRUNCATE catalog_items CASCADE` then re-run cleanly. |
| **G4** | **Missing API credentials silently no-op** — eBay, TCGPlayer, StockX, etc | Enumerates all configured paid sources and logs the active list. Bake still works on the always-on free sources (Crawl4AI, eBay-html, Mercari-US, Vinted, Mavin.io, Google Shopping). |
| **G5** | **Spend ramps fast** in first 48h of cold cache | Confirms `MONTHLY_BUDGET_EUR` is set (default €150). Telegram alerts at 75/90/100% are wired in `spend_tracker.py` (R41). Circuit breaker auto-pauses paid providers at 100%. |
| **G6** | **Stale Ridge model** — predictions drift if `model_retrain_scheduler` isn't running | Forces `MODEL_RETRAIN_ENABLED=true` so the model auto-retrains weekly during the bake. |
| **G7** | **Postgres connection pool exhaustion** — 5 schedulers + uvicorn workers + admin queries | Bumps `DB_POOL_MAX=30` (default is 20) for the bake. Override with the env var if you've already raised it. |
| **G8** | **Schema drift between code and DB** — over months of dev, code expects columns the DB doesn't have. PostgREST returns `PGRST204: column not found` and asyncpg returns `column does not exist`, causing **silent write failures** that look like the bake is "running fine" but no rows actually land. | Runs `scripts/schema_drift_check.py` before catalog import. Aborts the bake if any of the 10 bake-critical tables is missing any column the code is known to write. Run with `--fix-suggest` to print ALTER TABLE statements. |

---

## Daily monitoring loop

**You should spend ≤ 5 min/day on the bake.**

1. Check Telegram for any 75/90/100% spend alerts overnight. None? Great.
2. Run `./scripts/bake_status.sh` from your laptop. Expect green, growing rows, no warnings.
3. If a worker shows `last_status: "error"` → `./scripts/bake_tail.sh 500 | grep ERROR`
4. Once a week, eyeball `market_hits_24h` is still > 1000 (proof workers haven't silently stalled).

---

## Common failure modes + fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| `market_hits_24h = 0` after day 2 | All workers crashed or paused | `./scripts/bake_tail.sh 500`, look for stack traces; restart with `./scripts/bake_stop.sh && ./scripts/bake_start.sh` |
| Spend hit 100% before day 7 | Cold cache hit a paid provider too hard | Telegram circuit breaker already paused it. Bake continues on free sources. Bump budget if needed: `curl -X POST -H "X-Ops-Key: $OPS_API_KEY" http://51.21.210.195:8000/admin/spend-budget -d '{"budget_eur": 250}'` |
| `catalog_items_total = 0` | Import failed or DB empty | `./scripts/bake_start.sh --force-reimport` |
| `pool exhausted` in logs | Workers competing for DB connections | Stop bake, edit `.env` → `DB_POOL_MAX=40`, restart |
| Healthz returns 503 after start | Module import error (e.g. R43-style decorator bug) | `./scripts/bake_tail.sh 200`, fix in code, redeploy |

---

## Stopping the bake (when ready to launch)

```bash
./scripts/bake_stop.sh                    # stops uvicorn + workers cleanly
# Don't reset spend counters — they roll over monthly automatically
```

The accumulated DB data **stays** — that's the whole point. Workers can be restarted at any time after launch with the same `bake_start.sh` script (it's idempotent).

---

## Endpoints used

All require `X-Ops-Key: $OPS_API_KEY` header.

- `GET /admin/bake-summary` — single-call snapshot used by `bake_status.sh`
- `GET /admin/worker-health` — per-worker run history
- `GET /admin/spend-summary` — current month spend vs budget
- `POST /admin/spend-budget` — bump the cap on the fly
- `POST /admin/spend-pause` — pause/resume a single provider
- `GET /healthz` — liveness check (no auth)

See `server/app/features/admin_health_router.py` for full schema.

---

## Files

- `scripts/bake_start.sh` — startup with all 7 gotcha guards (idempotent)
- `scripts/bake_status.sh` — laptop-side health snapshot
- `scripts/bake_tail.sh` — quick log peek via SSH
- `scripts/bake_stop.sh` — clean shutdown
- `bake.log` — full bake log (created on first run, appended thereafter)
- `bake.pid` — current bake uvicorn pid (created on first run)

---

_Round 46 (2026-04-08). See memory3.md for context._
