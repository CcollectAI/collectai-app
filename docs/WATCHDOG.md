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
| `--hours N` | window (default 24). **Keep it ≤24** — Logflare answers longer windows partially; >24 self-declares the counts as partial |
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

## The coverage canary was wrong in both directions (2026-08-15)

It reported **pokemon at 21.3%** against a true **96.1%**, and said nothing at
all about **lorcana, digimon and one_piece_tcg sitting at 0%** — roughly 24,400
catalogue rows with no price. A monitor that pages on your healthiest category
and stays silent on your broken ones is worse than no monitor: the false HIGH
teaches you to ignore it, and then it cannot warn you about the real one.

Three defects, all in ~40 lines:

**1. The sample was still biased.** Stratifying by `source` was added to fix an
unordered-`LIMIT` bias, but the inner query kept `LIMIT $3` with **no
`ORDER BY`** — so it applied the same "oldest physical rows" bias once per
source instead of removing it. Pokémon has one dominant source, so it kept
reading the same unpriceable head of the table. Now `ORDER BY random()`.

**2. The category list was hand-maintained.** `[("mtg",80),("pokemon",80),
("yugioh",60)]` could not see a category nobody had remembered to add — which
is exactly what happened when tcgcsv was 403-blocked on 2026-07-29 and took
lorcana/digimon/one_piece to zero. The list is now derived: every category with
≥500 catalogue rows, floor 60% (80% for mtg/pokemon).

**3. Below-floor is three different findings.** Deriving the list produced **54
HIGHs**, ~40 of them the known structural gap where no sold-comp source exists
at all. Paging daily on a permanent condition mutes the monitor just as
effectively. Valuation only consumes SOLD comps, so their presence is the
discriminator:

| condition | meaning | severity |
|---|---|---|
| sold comps arriving now, coverage low | keying/crosswalk fault — the data is there and the catalogue cannot reach it | **HIGH** |
| sold comps in the 30–90d window, none now | **the source died** — a regression with a date | **HIGH** |
| never any sold comps | structural: `ebay_caller.sold_comps()` returns `[]` | **ONE aggregated MEDIUM** with the totals |

That last row is now a single finding naming 46 categories and 68,181 rows,
rather than 46 separate pages. Nothing is hidden — the scale is stated once.

**Verification:** re-run against live and compare to a direct measurement.
Pokémon must come back ~96%, lorcana ~0%. A canary is a measurement; check it
against the thing it claims to measure before trusting it.

## `sold_now > 0` is not evidence the crosswalk is broken (2026-08-21)

The canary classified any below-floor category with at least ONE sold comp as
*"the data is there and the catalogue cannot reach it — a keying or crosswalk
fault"*. On 2026-08-21 that produced **five false HIGHs out of eight**.

The measurement that settled it — distinct items with a sold comp in 30d, next
to items actually priced:

| category | catalogue | priced | distinct items with a comp |
|---|---|---|---|
| funko | 940 | 60 | **60** |
| retro_games | 1,114 | 58 | **58** |
| nintendo_merch | 1,115 | 32 | **32** |
| retro_handhelds | 1,111 | 4 | **4** |
| one_piece_tcg | 7,675 | 1 | **1** |

Every one of those is an exact match. **Every comp that arrived was already
used.** Nothing was broken; there were simply almost no comps. one_piece_tcg
was paging daily on the strength of a single sold comp against 7,675
catalogue rows.

The claim only holds when comps arrive **for catalogue rows that stay
unpriced**, so that is now what gets counted — with the same window and the
same definition of "priceable" as the coverage number above, so the two cannot
disagree:

| condition | meaning | severity |
|---|---|---|
| `orphaned >= max(50, 1% of catalogue)` | comps land ON catalogue rows that stay unpriced — crosswalk fault | **high** |
| sold comps in 30–90d, none now | the source died | **high** |
| below floor, `orphaned == 0` | crosswalk INTACT — aggregated | **one info** |
| never any sold comps | structural gap | **one medium** |

`orphaned` and `unmatched` are different findings and the info line says which:

- **orphaned** — a comp landed on a catalogue row and it is still unpriced.
  lorcana: **2,671** items, and it correctly remains the one HIGH.
  ⚠️ **The count was right and the CAUSE named here was wrong** — it was not
  the crosswalk. See "An orphaned comp is not proof of a crosswalk fault"
  (2026-08-26) below.
- **unmatched** — a comp landed for a key with **no catalogue row at all**.
  yugioh: **13,838 of 14,054**. The crosswalk is fine; the *catalogue* is
  missing the items. Calling that "too few comps" would have been a false
  sentence about a category with 587,276 of them.

Result on the same window: `bugs_high` 8 → 2, and the surviving two are real.

## An orphaned comp is not proof of a crosswalk fault (2026-08-26)

The lorcana HIGH above paged for five days straight saying *"the data is there
and the catalogue cannot reach it — a keying or crosswalk fault, not a sourcing
one"*, and pointed at `build_catalog_price_crosswalk.py`. Every number in it was
correct. The sentence explaining them was not.

What the measurements actually said:

| measured | value |
|---|---|
| lorcana catalogue | 9,814 (tcgcsv 6,172 / lorcast 2,847 / seed 795) |
| `catalog_price_refs` rows for lorcana | 5,416 — **all** tcgcsv keys, built 2026-08-15 12:10:44 and never since |
| lorcast sold comps in 30d | 5,420, written 2026-08-15 12:09:26**–12:09:28** |
| rows in `price_predictions` for lorcana, **ever** | **0** |

Zero predictions against 5,420 sold comps is not a crosswalk symptom — a
crosswalk fault would show comps arriving and predictions failing to *match*,
not failing to *exist*. The comps never reached valuation at all:

```
valuation_worker.run_once()
  SELECT COALESCE(price_eur, price) AS price   <- what it VALUES on
   WHERE processed = false ... AND price IS NOT NULL   <- what it FILTERS on
```

`scripts/load_lorcana_direct.py` listed `price_eur` in its INSERT and not
`price`, so every one of the 5,420 rows carried a usable EUR price, was
`processed = false`, and was **structurally unreachable**. No error, no log
line, no failing worker: the queue simply never returned them.

`price` is the price in its **original currency** and `price_eur` the EUR
normalisation (`marketplace_agent.py:887` binds raw_price / raw_currency /
price_eur in that order). They are equal on 3,065,233 of 3,067,191 recent rows
purely because `currency` is almost always EUR — the 1,958 that differ are all
USD. So "price and price_eur are the same thing" is true of the data and false
of the schema, which is why the omission looked harmless.

**Enumerated mechanically before fixing anything** — the queue's own predicate,
asked of the whole table rather than of lorcana:

```sql
SELECT split_part(item_ref,':',1), provider, count(*)
  FROM market_hits
 WHERE processed = false AND seen_at > now() - interval '90 days'
   AND item_ref IS NOT NULL AND (is_listing IS NOT TRUE)
   AND price IS NULL AND price_eur IS NOT NULL
 GROUP BY 1,2;
-- 5,420 rows. ALL lorcana/lorcast. Nothing else in 2,796,800 sold rows.
```

Three things follow, and the third is the one that matters:

1. **The writer is fixed, not the reader.** Relaxing the filter to
   `COALESCE(price_eur, price) IS NOT NULL` would de-align the partial index
   `idx_market_hits_valuation_queue`, whose predicate mirrors it — the query's
   own comment records that a seq scan there previously hit the 30s pooler cap
   and blew the 1800s bake cycle. `docs/DATA_SCALING_PLAN.md` §6 rule 1 is
   "default state = refuse to add an index", and §10 already prescribes the
   remedy for this exact shape: *"Writer bugs hide in INSERT column lists …
   add to the list + backfill"*, with a post-write assertion.
2. **Backfilled** in `20260826_backfill_lorcast_price_from_price_eur.sql`,
   scoped `currency = 'EUR'` so it is a restatement and not a currency error,
   and the migration RAISEs if any row is left behind — a backfill that no-ops
   must not report success.
3. **A new check, "valuation queue visibility"**, asks the queue's predicate of
   the whole table every day. The coverage canary measures the OUTPUT; this
   measures the INPUT, and for eleven days the two disagreed with nothing to
   reconcile them. `high` when the set is non-empty, naming category, provider
   and the oldest row.

### ✅ CLOSED the same day — lorcast is a scheduled worker now

This section originally ended by recording that **lorcast was a one-shot**: no
bake manifest entry, no pg_cron job, 5,420 comps written in a two-second window
on 08-15 by a script run by hand. That gave the category two dated deaths —
**2026-09-14**, when the comps leave the canary's 30-day window and lorcana
flips to *"sold-comp source DIED"* (a true sentence about a source that was
never alive), and **~2026-10-01**, when `market_hits_y2026m08` is dropped
(`PARTITION_RETENTION_MONTHS_MARKET_HITS=1`, `PARTITION_DROP_ENABLED=true`)
and takes every lorcana comp with it.

**Both deadlines are gone.** `workers/lorcast_worker.py` runs daily
(`SCHEDULES["lorcast_worker"] = 24 * 3600`), on the direct DSN, gated by
`_HEAVY_LOCK`. The sentence is edited rather than annotated, because a blocker
closes when the claim is edited and not when the work is done.

Three things that only showed up because it became a worker rather than staying
a script, none of which the original file was wrong to have:

1. **`logging.basicConfig` at module scope.** Harmless in a CLI; in a worker it
   reconfigures the ROOT logger for the whole server process as a side effect
   of importing one module. It moved into the CLI's `main()`.
2. **A synchronous fetch on the event loop.** `fetch_all_cards()` is blocking
   urllib, one round trip per set. Called directly it would stall every other
   worker *and* the API this process serves, for the length of the fetch. Now
   `await asyncio.to_thread(fetch_all_cards)`.
3. **No post-write assertion.** The defect this whole section is about leaves no
   error behind, so the worker now re-counts its own rows for
   `price IS NULL AND price_eur IS NOT NULL` and raises if any survive. A daily
   writer needs the check at the writer; the watchdog's table-wide version is
   the backstop, not the first line.

The write logic lives in **one** place. `scripts/load_lorcana_direct.py` is a
thin CLI over the same `run_once`, kept because a manual re-run is genuinely
useful, and it must never grow a second copy of the SQL.

Verified against prod on 2026-08-26: 2,847 cards → 2,847 catalogue rows and
5,420 price rows in ~4s, exit 0, `price` populated on every row, and the
table-wide invisible-set checker still 0.

⚠️ **The worker does not run until the bake restarts.** Registering it changes
code the running service imported at startup. Do NOT restart without running
the nine preflight gates manually first.

### Two other findings in the same report, checked rather than believed

- **"column drift: 1 reader/writer column mismatch"** was **false**, and had
  been paging `high` daily since 2026-08-22. `market_hits.seller_rating` and
  `seller_score` are **both** 0 non-null out of 3,073,177 rows; no INSERT in
  `server/` lists either. The "reader" is a key in Firecrawl's extraction JSON
  schema and the "writer" is a field on a Pydantic *response* model — neither
  touches SQL. `audit_column_drift.py` graded `HIGH if ro_n == 0` without
  requiring `wo_n > 0`, so a pair where neither side is written scored as
  drift, under a headline asserting that one of them *was* written. HIGH now
  requires a live writer; both-dead is a separate `DEAD_PAIR` grade the
  watchdog does not page on. The finding also never said WHICH columns — the
  same "a failing worker must say WHY" defect this doc fixes elsewhere — so it
  now reads them from `--json` and names them.
- **"watchdog could not read part of the Supabase logs"** was real, and its
  `suggested_fix` — *"Refresh the Management API PAT"* — was a wrong diagnostic
  stated as fact. The PAT is a valid `sbp_` token and `postgres_logs` answered
  with it **in the same run**; only `edge_logs` was failing, and it fails
  *intermittently*: 2 of 10 identical requests succeeded within one minute,
  and 4 more failed at 25s spacing after a 60s cooldown, so it is not rate
  limiting either. Each sub-query now retries 3× with backoff, and the finding
  says the credential is exonerated whenever another query on the same token
  answered.

  **This one had teeth.** `api_status_codes` is where "API returning 5xx" comes
  from, so on 08-25 and 08-26 that `high` finding silently vanished from the
  report — while a successful manual query over the same 24h window returned
  **16 5xx**, comfortably over the `>= 10` threshold.

  **The 2026-08-12 `[]`-vs-`None` fix worked and did not prevent this.** The
  total correctly read `None`. The alert consuming it did not:

  ```python
  if ((sblogs.get("totals") or {}).get("api_5xx") or 0) >= 10:   # None -> 0 -> False
  ```

  `or 0` turns UNKNOWN into "fine". A missing *total* is visible in the JSON; a
  missing *bug* is indistinguishable from a healthy day. **Fixing the number is
  not fixing the alert built on the number** — verify at the consumer, not just
  at the collector, and grep for `or 0` on anything that can legitimately be
  `None`. (Swept: this was the only such consumer; the digest renderer already
  prints "counts unavailable this run" per section.)

  The finding is now three-state — `high` on a real count, a `medium` saying
  **"API 5xx rate is UNKNOWN this run"** when the source was blind, silence
  only when the source answered and the count was low. Retry is a mitigation,
  not a guarantee: the live run that confirmed this had all **3 attempts** fail,
  and the report said UNKNOWN instead of saying nothing.

## A digest that fails to send is worse than a digest that says nothing

`send_ops_alert(body[:3800])` was a raw character cut applied to **markup**.
When the cut landed between `<code>` and `</code>` Telegram rejected the whole
message:

```
400 ... can't parse entities: Can't find end tag corresponding to start tag "code"
```

and the entire daily report was lost. Silently — the send sits inside a
`try/except` that prints to stderr, which nothing reads.

Note *when* it fails: the longer the report, the likelier the cut lands inside
a tag. **Delivery failed in proportion to how much the watchdog had to say.**

Two defences, because either alone still loses reports:

- `_trim_html()` cuts on a line boundary and closes whatever tags are still
  open. Pinned by `server/tests/test_watchdog_digest_trim.py`, which includes a
  test asserting the **old** slice really does leave `<code>` unbalanced — a
  fixture that stops reproducing the bug fails the suite.
- `telegram_ops.send_ops_alert()` retries once as **plain text** on a
  `parse entities` rejection. A digest with the tags stripped beats no digest.

## Logflare answers long windows PARTIALLY, and says nothing about it

The same query, three windows, on 2026-08-21:

| window | `ON CONFLICT` errors | other findings |
|---|---|---|
| 6h | 15 | deal_ratings |
| 24h | 15 | user_blocks ×15, settings_json ×6, shipping ×6, … |
| **72h** | **14** | **none of the above** |

A superset window returning **fewer** rows than its own subset is proof the
answer is truncated, not smaller. `docs/WATCHDOG.md` advertised `--hours 168`,
which therefore produced a confidently wrong report.

`--hours > 24` now adds an entry to the `unavailable` list saying the counts
are partial. It does not silently pass them off as totals — the same rule this
doc already sets for `[]` vs `None`.

**Use ≤24h for anything you intend to act on.**

## A probe must not manufacture the alarm it detects

`audit_orphan_tables.py` ran `SELECT COUNT(*) FROM public."<tbl>"` over table
names harvested from source. `deal_ratings` was dropped with the Deal Desk on
2026-08-09 but survives in a **comment** in `p2p_offers_router.py`, so the
audit probed it every run. The local `except` swallowed the error; Postgres
still logged an `ERROR`, which the watchdog then reported as a rejected write.

Now guarded with `to_regclass`, which returns NULL instead of raising — and
keeps "missing" (`None`) distinguishable from "empty" (`0`).

This is the same defect class as the `check-unrendered` gate counting a
component named only in a `//` comment: **a comment is not a reference.**

## Related audits

- `server/scripts/audit_orphan_tables.py` — tables read by code that nothing writes
- `server/scripts/audit_column_drift.py` — reader and writer on different columns

Both are advisory (always exit 0) and are **not** wired into the bake preflight
chain: they report a backlog, and a blocking gate would wedge every deploy until
that backlog is zero. Flip `--strict` on once the findings list is empty.
