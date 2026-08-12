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

### An empty answer is not a zero (2026-08-12)

`collect_supabase_logs.query()` returned `[]` on **every** failure path — curl
non-zero, timeout, revoked PAT, an HTTP error body with no `result` key — and
`out["available"] = True` was set *before the first query ran*. A source we
could not read therefore summed to `"postgres_errors": 0` and rendered as a
calm day.

It was wrong on five of the last nine days:

| Day | Reported | Actually |
|---|---|---|
| 08-04, 08-05, 08-06 | 0 Postgres errors, 0 API requests | neighbouring days logged 628–725/day |
| 08-09, 08-12 | Postgres rows present, all API counts 0 | the `edge_logs` query alone had failed |
| 08-11 | 0 Postgres errors | 761 the next morning, same constraint |

Three consecutive "green" days were three blind days, while catalog ingest was
losing every attribute-bearing row (see below).

Now: `query()` returns `None` (could not ask) as distinct from `[]` (asked,
nothing there); a total whose query failed is `None`, never `0`; `available`
is earned from the result; and a blind run raises its own `medium` finding
naming each failed sub-query. **Proved by pointing the collector at an invalid
project ref** — `available: false`, totals `None`, three named failures, the
finding present, where the identical input previously produced a green report.

Watch the seam this created: `available` is true when Postgres answered even if
the API query did not, so the digest must treat each total independently.
`t.get("api_ok", 0)` does **not** defend against this — the key exists holding
`None`, so the default never applies and `ok + e4 + e5` raises `TypeError`.
That exception is caught by the digest's own `except`, which prints to stderr
and sends nothing: the daily report would have vanished silently on exactly the
days the logs were partly blind. The renderer now prints *"counts unavailable
this run"* per section instead.

### `worker_runs` is a prod table, and a laptop can write to it (2026-08-12)

Two `high` findings — `calibration_worker` and `partition_drop_worker`, 5
errors / 9 runs each. Neither worker was broken. All five errors per worker came
from a **local machine**: `gaierror: [Errno 8] nodename nor servname provided`
(Errno 8 is Darwin's `EAI_NONAME`; Linux says `[Errno -2] Name or service not
known`) and `ModuleNotFoundError: No module named 'boto3'`. Every run prod made
in the same window was `ok`.

`record_run()` writes over the direct DSN, so a worker started by hand on a
laptop lands in the same table the health check reads, and poisons it for 24h.

- `worker_registry._async_persist_run` now stamps `metadata.host` on **every**
  row, not just error rows. It builds the JSON **server-side** with
  `jsonb_build_object` and must stay that way: `app/db.py:71` registers a jsonb
  codec with `encoder=json.dumps`, so handing a `json.dumps(...)` string to a
  `$n::jsonb` parameter encodes it twice and stores a jsonb *string* —
  `jsonb_typeof = 'string'` — after which every `metadata->>'host'` and
  `metadata->>'error_repr'` reads NULL in silence. That shipped for three
  minutes on 2026-08-12 (13 rows, repaired with `(metadata #>> '{}')::jsonb`).
  It is the same defect as `attributes_json = json.dumps(...)` two sections
  down, and it survived a rollback test that used a bare `asyncpg.connect()`
  instead of the app's pool. **Verify jsonb writes with
  `jsonb_typeof(col) = 'object'`, through a pool built by `app.db`.**
- The check counts only rows this machine recorded. Rows with no host (legacy)
  count as ours — **a legacy row must fail toward alerting, never toward
  silence.**
- A failure from another host is reported as `info`, naming the host, rather
  than dropped: a second real server must not become invisible.

**A failing worker must say WHY** (the rule this doc already sets for tcgcsv)
was not being applied by the generic check — the finding said only "5 errors / 9
runs". It now carries `metadata.error_repr`, and the pg_cron finding carries the
last `return_message`. Both new findings identify themselves at a glance:

```
worker failing: partition_drop_worker
  5 errors / 9 runs in 24h — last error: ModuleNotFoundError: No module named 'boto3'
cron job failing: hourly_refresh_best_comp
  18 failures / 24 runs — last message: ERROR: canceling statement due to statement timeout
```

### One cycle = one `worker_runs` row (2026-08-12)

Every prod run wrote **two** rows ~1ms apart (`22:09:19.751556` and
`.753306`). `bake_orchestrator` records when `run_fn()` returns, and some
`run_once()` bodies record their own outcome first
(`partition_drop_worker.py:278`, `calibration_worker.py:250`).

Not cosmetic: `partition_drop_worker.run_once()` records `error` for an
unexported partition and then returns **normally**, so the pair became one
`error` + one `ok` — a permanent 50% error rate sitting exactly on the
`>= 0.5` paging threshold, while the orchestrator considered the cycle fine.

The orchestrator now skips its own record when the worker already recorded
during this cycle — **on the success path only.** On the error paths the
orchestrator's row is the richer one (it carries `error_repr`;
`calibration_worker`'s `finally` records a bare status), so suppressing it
would trade a duplicate row for a lost cause.

### Checks that go quiet (2026-08-12)

The RLS, worker and pg_cron checks were each wrapped in `except Exception:
pass`. A renamed column or a revoked grant would delete the check from the
report — and a report with no finding is what a healthy day looks like. They
now run inside a `guard()` helper that turns any exception into a `medium`
finding. **Still unconverted** (lower stakes, display-only or already
reporting): the activity collectors and the ingest-freshness, partition-runway,
`mv_supply_trend` and `schema.lock` checks.

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

## DAC7: the seller crossing was told, and nobody else was (2026-08-09)

`_dac7_accrue` notifies the **seller** when they pass 30 sales or EUR 2,000 in a
calendar year, and notified no one else. In practice the founder would have found
out by querying the table — i.e. when a seller asked. A crossing is the moment a
decision is needed, which is exactly what spec §5c recommends alerting on: *"so
we learn we have a trader before a regulator does."*

The check is tiered, because a daily siren is how a channel stops being read:

| Condition | Verdict |
|---|---|
| Crossed, `notified_at` still NULL | `high` — §6 promises notice; that promise is unkept right now |
| Crossed and notified | `medium` — nothing is broken, but there is now a reportable seller, and that is a decision |
| ≥20 sales or ≥EUR 1,500 | `info` — warning before the decision is forced |
| Nobody in reach | healthy, **stating the ceiling**: *"busiest is 0 sales / EUR 0 against limits of 30 / EUR 2000"* |
| The check itself errors | `medium` — reporting nothing must never look like all-clear |

The approach thresholds are **derived** from the live limits (⅔ and ¾), not
hardcoded: a second copy of 30/2000 in the watchdog is one more place to drift
from what the terms say in writing.

**Proven before shipping** by inserting each scenario inside a transaction and
rolling it back, so prod kept its zero rows — all four tiers fired.

`notification_impressions`, `notification_interactions` and
`notification_outcomes` joined the allowlist on 2026-08-12, having been flagged
`medium` every day. Verified rather than assumed: all three are written by
`pool.acquire()` + raw `INSERT` in
`app/features/notification_feedback_router.py:63-127`, so every access is
asyncpg on the direct DSN and PostgREST is never in the path. The test applied
was the one this list previously failed — `user_notifications` was justified as
"served through /notifications", which reads a *different* table — so the claim
checked was not "an endpoint exists" but "**this table's own** reader and writer
bypass RLS".

`dac7_seller_year` is also on the RLS allowlist next to `subscription_events`:
RLS-on with no policy denies ALL client access, which is the intent (the table is
read only through `GET /p2p/dac7/me` on the direct DSN, never PostgREST). Without
that entry the RLS check flagged it daily, which is the false-alarm pattern this
doc already warns about.

## Two FK findings, two different causes (2026-08-12)

Both reported identically — "Postgres rejecting writes repeatedly" — and the
message alone was not enough to tell them apart. **The `detail` field is**: it
names the failing key, and Logflare has it even though the watchdog's summary
does not.

```sql
select p.detail, count(*) from postgres_logs
cross join unnest(metadata) m cross join unnest(m.parsed) p
where p.error_severity = 'ERROR' and event_message like '%_user_id_fkey%'
group by 1 order by 2 desc
```

| Finding | Failing key | Cause |
|---|---|---|
| `user_presence_user_id_fkey` ×30 | `92416ed4-…` — one uid, all 30 | a **deleted account** whose client is still signed in and heart-beating |
| `subscriptions_user_id_fkey` ×21 | `00000000-…-0000000000aa` | a **synthetic uid** reaching `GET /billing/status` |

The uid in the first exists in no table — not `auth.users`, not `profiles`, not
`items`. Both columns are `REFERENCES auth.users(id) ON DELETE CASCADE`, so the
row vanished with the account and every heartbeat since was rejected. **A JWT
outlives the account it names**, and the device cannot know until something
fails.

Fixed as two separate things, because they are two separate things:

- `20260812_heartbeat_tolerates_deleted_user.sql` — `rpc_heartbeat_v1` no-ops
  when `auth.uid()` is absent from `auth.users`. Presence is a cosmetic online
  dot; one stale device must not write 30 ERROR lines/day that are
  indistinguishable from a real constraint bug.
- `billing_router._ensure_subscription_row` — catches `ForeignKeyViolationError`
  and serves the free tier without persisting. Note what this one really
  exposed: the writer **was** our own app, and 21 daily errors appeared in the
  Postgres log and **nowhere in `bake.log`**. The DEPLOYMENT.md diagnostic
  ("an error Postgres reports that your application log does not contain means
  the writer is not the app") has a second reading — it can also mean the app
  never logged that path. It now logs the uid.

Neither is silenced in the watchdog. Both stop happening at the source, which is
the only kind of fix that leaves the check honest.

## Related audits

- `server/scripts/audit_orphan_tables.py` — tables read by code that nothing writes
- `server/scripts/audit_column_drift.py` — reader and writer on different columns

Both are advisory (always exit 0) and are **not** wired into the bake preflight
chain: they report a backlog, and a blocking gate would wedge every deploy until
that backlog is zero. Flip `--strict` on once the findings list is empty.
