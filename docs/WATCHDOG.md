# Production Watchdog

`server/scripts/watchdog.py` — one read-only report answering three questions:

1. **Activity** — what did users actually do in the window?
2. **Healthy** — which loops are demonstrably working (writer *and* reader)?
3. **Bugs** — what is silently failing right now?

Every finding carries a Supabase/GitHub link and a paste-able `verify` string,
so nothing has to be taken on trust. The script never writes to the database.

## Why it exists

The 2026-07-24/25 audit found ~14 features that were fully built and silently
dead. Every one had the same shape: a writer and a reader that were never
connected, plus a construct that turns "not connected" into an empty result
rather than an error — a bare `except: pass`, Pydantic/Zod dropping an
undeclared field, a CHECK constraint narrower than the code, a `LEFT JOIN`
yielding NULL. Nothing ever went red, so a dead feature looked merely unused.

The watchdog makes that distinction mechanical and daily.

## Schedule

```
0 9 * * *  /opt/collectors/scripts/watchdog_daily.sh >> /opt/collectors/logs/watchdog.log 2>&1
```

Server timezone is **Europe/Paris**, so this is 9am local. The wrapper writes
`/opt/collectors/logs/watchdog-YYYYMMDD.json` (30-day retention) and sends a
Telegram digest. Day-over-day deltas come from the previous day's file.

## Usage

```bash
cd /opt/collectors/server
set -a; . /opt/collectors/.env; set +a
PYTHONPATH=/opt/collectors/server /opt/collectors/.venv/bin/python scripts/watchdog.py \
  --hours 24 --out /tmp/wd.json --summary
```

| Flag | Effect |
|---|---|
| `--hours N` | window (default 24) |
| `--out FILE` | write the full JSON report |
| `--summary` | human-readable digest to stdout |
| `--digest` | always send the Telegram summary, even when green |
| `--telegram` | send only when a high-severity finding exists |

Green days send **silently** (`disable_notification`) with a ✅ title. A daily
report prefixed with a siren trains you to ignore the channel, which defeats the
purpose.

## Sources

1. **Postgres tables** — users, collection, demand signals, engagement,
   no-results searches, plan/paying-customer usage.
2. **systemd journal** (`collectai-bake.service`) — errors bucketed by
   normalised pattern (UUIDs/timestamps/numbers collapsed so the same message
   groups).
3. **Live health checks** — CHECK-constraint vs code drift, RLS gaps,
   worker/cron failure rates, ingest freshness, partition runway,
   `schema.lock` staleness.
4. **Supabase Logflare** — `postgres_logs`, `edge_logs`, `auth_logs` via the
   Management API.

### Source 4 is the important one

Anything Postgres rejects, or any request that fails at PostgREST/GoTrue, never
reaches the EC2 journal. On the first run the journal reported **0 errors** for
a window in which Supabase logged **680**, including:

- 598/day `category_items_attrs_is_object` violations (catalog ingest)
- 30/day `ON CONFLICT DO UPDATE cannot affect row a second time`
- 13/day `daily_vals.category must appear in the GROUP BY clause`
- 8/day `rpc_list_personalized_events_v1 does not exist`

**When a screen looks empty, check whether its writes are being REJECTED before
concluding the feature is unused.**

### Management API credential

The PAT lives where the Supabase CLI puts it:

```
~/.supabase/access-token        # on EC2 — starts with sbp_
```

`SUPABASE_ACCESS_TOKEN` in `/opt/collectors/.env` is a **different value and
401s** — do not assume the capability is unavailable because that one fails.
The script checks the CLI path first, then falls back to the env var, and only
reports "unavailable" when both are absent.

To mint a new one: <https://supabase.com/dashboard/account/tokens>

## Report shape

```jsonc
{
  "generated_at": "...", "window_hours": 24,
  "activity":         { "users": {...}, "demand_signals": {...}, "collection": {...},
                        "engagement": {...}, "searches_with_no_results": [...] },
  "supabase_logs":    { "totals": {...}, "postgres_errors": [...],
                        "api_status_codes": [...], "api_failing_paths": [...], "links": {...} },
  "paying_customers": { "subscriptions": [...], "signals_by_plan": [...],
                        "collection_by_plan": [...] },
  "logs":             { "errors": [...], "warnings": [...], "tracebacks": 0 },
  "what_went_well":   [ { "check": "...", "detail": "..." } ],
  "bugs":             [ { "severity": "high|medium|info", "title": "...",
                          "detail": "...", "link": "...", "verify": "...",
                          "suggested_fix": "..." } ],
  "counts":           { "healthy": 21, "bugs_high": 0, "bugs_medium": 0 }
}
```

## Checks must know the schedule they police (2026-08-04)

The partition check flagged **"no partition for next month"** on
`price_predictions` and `price_history` as `medium`, every day. It was wrong.

Next month's partitions are created by **pg_cron job 32, `0 2 25 * *`** — 2am on
the 25th. On the 4th of a month there is legitimately no partition for next
month, and there won't be for another three weeks. The check fired daily from
the 1st to the 24th, on every partitioned table: ~24 days of false alarms a
month. That is how a watchdog stops being read, and it devalues the one finding
in the same report that *was* real.

The check is now schedule-aware:

| Condition | Verdict |
|---|---|
| **Current** month's partition missing | `high` — rows are landing in `_default` right now |
| Next month's missing **and** day ≥ 25 | `medium` — job 32 should already have run |
| Next month's missing and day < 25 | healthy: *"y2026m08 present; y2026m09 due from pg_cron job 32 on the 25th"* |

Result on the 2026-08-04 run: `bugs_medium` 2 → 0, `what_went_well` 32 → 34.

`market_hits` looked different (it already had `y2026m09`) purely because a
migration created it ahead of the cron — not because the other two were broken.
Chasing that apparent inconsistency is what surfaced the real defect: the check,
not the data.

**The general rule:** a check on a scheduled artefact must encode the schedule.
"Absent" is only a bug once the thing that creates it should have run.

## A failing worker must say WHY, not just that it failed

`tcgcsv_worker` had been erroring since 2026-08-01 with:

```
tcgcsv import failed: None market_hits errors, None hits, None upserted
```

Three `None`s and no cause. The counters aren't in the summary on an early bail
— that path returns `{"ok": False, "reason": "no categories"}` — so the message
interpolated fields that were never set, and the actual reason sat unread in
`bake.log`.

`_get_json` in `server/pipelines/import_tcgcsv.py` returns `None` on any HTTP
failure and only `logger.warning`s the status, so nothing reached
`worker_runs.metadata`. It now records the last transport failure (url, status,
body) and the worker leads its error with it. Verified against the live
endpoint:

```
tcgcsv import failed: no categories HTTP 403 on https://tcgcsv.com/tcgplayer/categories
  — Your application has flagged for overuse and has been blocked. Please reach out
    on discord or send an email to cptspacetoaster@gmail.com to begin an appeal.
```

The remedy is now in the alert itself. This finding stays `high` and keeps
paging — it is genuinely broken and needs an appeal email — but an operator no
longer has to SSH in to learn that.

## Related audits

- `server/scripts/audit_orphan_tables.py` — tables read by code that nothing writes
- `server/scripts/audit_column_drift.py` — reader and writer on different columns

Both are advisory (always exit 0) and are **not** wired into the bake preflight
chain: they report a backlog, and a blocking gate would wedge every deploy until
that backlog is zero. Flip `--strict` on once the findings list is empty.
