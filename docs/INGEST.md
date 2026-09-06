# Sparrow Collect Nightly Ingest Pipeline

The ingest pipeline appends datapoints (raw observations) and produces normalized training candidates for the ML pricing models.

## Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Sources   │ -> │  Normalize  │ -> │  Taxonomy   │ -> │   Writers   │
│ (eBay, App) │    │  + Dedupe   │    │   Mapper    │    │ (S3 + PG)   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## Design Principles

1. **Raw data is immutable** - Never delete raw observations. Store bulk in S3.
2. **Taxonomy versioning** - Every record includes `taxonomy_version` for safe remapping.
3. **Hash-based deduplication** - Skip duplicates based on content hash.
4. **Dry-run mode** - Test without writing to verify expected counts.
5. **Cost-optimized split** - Postgres stores pointers + curated; S3 stores bulk raw.

## How to Run

### Local Development

```bash
# Dry-run (no writes)
python scripts/ingest/run_nightly.py --dry-run

# With limits
python scripts/ingest/run_nightly.py --dry-run --max-items=100

# Real run (requires credentials)
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="your-key"
python scripts/ingest/run_nightly.py --max-items=500
```

### GitHub Actions

The pipeline runs automatically at 03:00 UTC via `.github/workflows/nightly-ingest.yml`.

Manual trigger:
1. Go to Actions → "Nightly Ingest Pipeline"
2. Click "Run workflow"
3. Optionally enable dry-run or set max items

## Pipeline Stages

| Stage | Description |
|-------|-------------|
| 0 | Lock + generate run_id for idempotency |
| 1 | Gather inputs from sources (app_signals, csv) |
| 2 | Normalize to `RawObservation` schema |
| 3 | Hash-based deduplication |
| 4 | Taxonomy mapping → `category_id`, `subtype_id` |
| 5 | Write raw bundle to S3 (partitioned JSONL) |
| 6 | Write pointers + candidates to Supabase |

## Data Model

### Tables

| Table | Purpose |
|-------|---------|
| `ingest_runs_v1` | Tracks each pipeline run |
| `raw_observation_pointers_v1` | Pointers to S3 raw data + taxonomy |
| `training_candidates_v1` | Normalized candidates for training |
| `user_feedback_events_v1` | User edits/overrides for calibration |

### Views

| View | Purpose |
|------|---------|
| `v_ingest_stats_daily` | Daily ingest statistics |

## Taxonomy Mapping

The mapper assigns `category_id` and `subtype_id` based on pattern matching.

Current categories (v1.0):
- pokemon, mtg, funko, warhammer, lorcana
- flesh_and_blood, gunpla, hot_wheels
- designer_toys, sports_cards

### How to Add a Category

1. Edit `src/ingest/taxonomy_mapper.py`
2. Add patterns to `CATEGORY_PATTERNS` dict
3. Optionally add subtypes to `SUBTYPE_PATTERNS`
4. **Important**: When taxonomy changes significantly, increment `TAXONOMY_VERSION` in `src/ingest/types.py`

## How to Remap Taxonomy

When taxonomy evolves:

1. Update patterns in `taxonomy_mapper.py`
2. Increment `TAXONOMY_VERSION` in `types.py` (e.g., `v1.0` → `v1.1`)
3. Run remapping job:

```bash
# Future: dedicated remap script
python scripts/ingest/remap_taxonomy.py --from-version=v1.0 --to-version=v1.1
```

The remapper:
- Reads raw observations from S3 bundles
- Applies new taxonomy mapping
- Writes new pointer rows with updated `taxonomy_version`
- Creates new training candidates
- Does NOT delete old data (supports rollback)

## Which code the nightly run actually uses

`nightly-ingest.yml` (cron `0 3 * * *`) runs **the branch the workflow is on** —
it does **not** pick up anything rsynced to EC2 by `scripts/deploy_to_ec2.sh`.

As of 2026-07-29 that branch was `feature/all-enhancements`, ~4 weeks behind the
active working branch, and was still discarding every attribute-bearing catalog
row because it lacked the 2026-07-25 `attributes_json` fix (662 rejected writes
per night, `category_items_attrs_is_object`). The pipeline reported success
throughout: it logs the rows it *attempted*, not the rows Postgres accepted.

**Confirmed unchanged on 2026-08-12** (680 rejections in 24h). The reason it
never resolved: `schedule:` workflows run the repo's **default branch**, and the
default branch *is* `feature/all-enhancements`. See the expanded section in
`docs/DEPLOYMENT.md` for the two ways out.

**Unchanged from 2026-08-12 to 2026-08-29** — the branch's last commit was
2026-08-12, and PR #4 (`fix/ingest-within-batch-dedupe`) had been open and
unmerged since 2026-08-21, as had PR #3. It was never blocked on code.

✅ **Closed 2026-08-29.** The default branch is now
`feat/marketplace-and-target-hit`, which carries the dedupe, so the next
scheduled run picks it up. See `docs/DEPLOYMENT.md`. Note the drift has *moved*
rather than vanished: the default is now a working branch, so anything unpushed
still does not run — keep using the `gh run list` check below, with
`feat/marketplace-and-target-hit` as the expected ref.

### The three ways a catalog batch is rejected (measured 2026-08-28)

Actions run `33181755459` logged **107 failed catalog batches** — up to ~21k
catalogue rows dropped — and still reported **success**, because
`upsert_catalog` logs the HTTP error and moves to the next batch. The job's exit
code has never reflected write failures. Attribution came from the client IP in
`edge_logs`: `4.154.215.8` is Azure (an Actions runner), not EC2
(`51.21.210.195`) and not a laptop.

| n | rejection | cause | state |
|---|---|---|---|
| 15 | `500 21000 ON CONFLICT DO UPDATE command cannot affect row a second time` | a batch carried the same `(category, item_key)` twice | fixed 2026-07-29 on the working branch; **still absent from the branch that runs** |
| 42 | `400 PGRST102 All object keys must match` | `to_row()` adds `image_url` / `barcode` / `attributes_json` **conditionally**, so one batch carried several key sets | fixed 2026-08-29 — `upsert_catalog` now groups rows by key set before batching |
| ~50 | `Cannot send a request, as the client has been closed.` | a sibling pipeline called the module-global `close_http_client()` while other threads were still writing | fixed 2026-08-29 — `SupabaseIngest.client` is a property that re-resolves per call |

Three rules fall out of this, and the first two are the same rule at different
layers:

1. **A bulk PostgREST insert is ONE statement.** One duplicate conflict target,
   or one row with a different column list, takes the whole batch down. Both
   need normalising *before* the POST, never after the error.
2. **Do not pad rows to a common key set.** The request carries
   `Prefer: resolution=merge-duplicates`, which updates the columns present in
   the payload and leaves absent ones alone — so padding a row that has no
   image with `image_url: None` would **blank an image already in the
   catalogue**. Group by key set instead. Sending fewer columns is always safe;
   sending NULL is not. Same trap as the `price` / `price_eur` backfill in
   `DATA_SCALING_PLAN.md` §10.
3. **A process-global resource must not be closed by one of N concurrent
   users.** `import_all.py` runs pipelines in a `ThreadPoolExecutor`; any
   pipeline that imports `close_http_client` can strand every other thread. The
   fix is to stop caching the client, not to audit the callers — there are six
   of them and the next new pipeline would have been the seventh.

**All four PostgREST bulk writers were enumerated before declaring this fixed**,
rather than fixing the two the log happened to name. A batch writer needs both
properties; only one writer was missing one:

| writer | table | within-batch dedupe | stable key set |
|---|---|---|---|
| `import_common.upsert_catalog` | `category_items` | ✓ 2026-07-29 | ✗ → **fixed 2026-08-29** |
| `import_common.upsert_market_hits` | `market_hits` | n/a — one dict literal | ✓ |
| `import_tcgcsv.upsert_catalog_rows` | `category_items` | ✓ `seen` set, per call | ✓ |
| `newsletter_scraper._upsert_events` | `events` | ✓ | ✓ |

Note the two catalogue writers solve the key-set rule **differently on purpose**.
`newsletter_scraper._event_to_row` pads every field to `None`; `upsert_catalog`
groups instead. Padding is safe where one scraper owns the whole row, and unsafe
on `category_items`, which several pipelines enrich — there, a `None` blanks a
column another pipeline populated.

The checker is `server/tests/test_import_catalog_writer.py`. Its `FakePostgrest`
encodes the **server's** rules rather than our code's shape, and both fixes were
mutation-tested: restoring the cached client reproduces the exact
`client has been closed` error, and collapsing the key-set grouping reproduces
`PGRST102`.

### The run now FAILS when it drops rows (2026-08-29)

The three bugs above were each a few lines. What made them expensive was that
`nightly-ingest` **exited 0 while dropping 107 batches**, so nobody looked for
seven weeks. Fixing the causes without fixing the silence just moves the cost to
the fourth cause.

`import_all` runs each pipeline in-process via `importlib`, and every pipeline
builds its **own** `IngestStats` — so nothing upstream could ever see a write
failure. The tally is therefore a process-global in `import_common`, at the
writer chokepoint every catalog and market-hit write already passes through:

```python
record_write_loss(rows_lost, failed_batches)   # called BY the writers
write_loss_summary()  -> {"rows_lost": int, "failed_batches": int}
write_loss_exit_code() -> 1 if any row was fetched and then not written
```

`import_all.main()` calls `reset_write_losses()` at the start and exits 1 if
`rows_lost > 0`. A process-global rather than a parameter threaded through ~50
pipelines, for the same reason `client` became a property: the next new pipeline
is the one that forgets.

**What it deliberately does NOT fail on.** Only rows we *held and then lost*
count. `api.pokemontcg.io` returned 500 twenty-plus times in that same run;
failing the nightly on third-party weather is how a red build becomes something
people scroll past. Upstream fetch failures are logged and do not gate.

Wired into all three writers — `upsert_catalog`, `upsert_market_hits`, and
`import_tcgcsv.upsert_catalog_rows`. The last is **not** reachable from
`import_all` (tcgcsv is absent from its tier lists) so it does not gate the
nightly; it is recorded anyway, because leaving a known instance of a class you
just fixed is how the class returns — and it had been logging its losses at
WARNING, one level below what anyone greps for.

Verified, not assumed:

- The tally is written from a `ThreadPoolExecutor` (`--parallel N`), so it takes
  a lock. Proven under contention: 32,000 concurrent increments, zero lost.
- `nightly-ingest.yml` runs `python -m pipelines.import_all` as the **last**
  command of its `run:` block with no `continue-on-error`, so the exit code
  really does reach GitHub. A gate whose exit code is swallowed is not a gate.
- Both recordings mutation-tested: removing either writer's
  `record_write_loss` turns the gate green while rows are visibly lost.
- The same step's `pip install httpx boto3 || true` was removed — it masked a
  failed install into an `ImportError` three steps later.

### The same class, swept across the other 11 workflows (2026-08-29)

Having fixed the nightly ingest, the obvious question was whether any other
scheduled job reports success while doing nothing. **One did, and a second is
still open.**

`gh run list` showed 8/8 `success` for every scheduled workflow — which is
exactly the reading that is compatible with both "ran fine" and "never ran".
The discriminating query is the STEP list, not the conclusion:

```bash
rid=$(gh run list --workflow=<w>.yml --limit 1 --json databaseId -q '.[0].databaseId')
gh run view "$rid" --json jobs -q '.jobs[].steps[] | "\(.conclusion)\t\(.name)"'
```

A job whose "Check secrets" step **succeeded** and whose every other step is
`skipped` has run zero lines of work and reported success.

| workflow | verdict |
|---|---|
| `nightly-eval` | ⛔ **never ran** — schedule disabled 2026-08-29 |
| `nightly-train-eval-gate` | ⚠️ runs, but its gate step has never gated, and its **feedback-export step has never run at all** — see below |
| `nightly-training`, `nightly-prune`, `ingest-ebay` | genuinely run |
| `sanity-e2e` | ⚠️ ran and failed on EVERY push — see below (fixed 2026-08-30) |

**`nightly-eval` had two independent fatal bugs.** `HAS_SECRETS` gated on
`secrets.S3_DATA_BUCKET` — unset, and never referenced by the workflow — so
every `if: env.HAS_SECRETS == 'true'` step skipped. And the run step invokes
`eval_mae_and_gate.py` with no arguments while `--artifact-prefix` is
`required=True`. Fixing only the gate would have traded silence for a nightly
argparse traceback, so the schedule is disabled and the reasons are written in
the file. **Turning a silent lie into a loud one is not progress.**

**`nightly-train-eval-gate` still trains models nightly and gates none of
them.** Its "Evaluate & Gate" step sets `working-directory: server`, the script
lives at repo root, so `[ -f scripts/eval_mae_and_gate.py ]` is false and it
logs `Eval script not found, skipping gate check` — successfully. Confirmed in
run `33244113380`. Repointing the path is not enough: it then passes a
positional argument the script's argparse does not accept. Six callers invoke
this one script three mutually incompatible ways (`nightly_multi.sh:38` has the
only correct form), and two of them wrap it in `|| true`.

The generalisable rule, and the reason this sits in a doc rather than a commit
message: **a green checkmark is a claim about the job's exit code, never about
whether it did anything.** For any job that can skip itself, the check is
"which steps actually executed", and that question has to be asked on purpose.

### A step can execute, log, exit 0 — and still not have run (2026-09-05)

The sweep above asked *which steps executed*. That question is necessary and
not sufficient: `nightly-train-eval-gate`'s **"Export user feedback for
retraining"** step executes every night, prints two log lines and exits 0.
It has never done anything.

```
DB_DSN:                                              <- the step's own env dump
[WARNING] DB_DSN not set — skipping feedback export (no users yet, not critical)
[INFO] SUMMARY: exported=0, taxonomy=0, skipped=1, total=0
```

`gh secret list` settles it: **there is no `DB_DSN` secret on the repo.**
`${{ secrets.DB_DSN }}` interpolates to empty, the script takes its own
early-return, and `exported=0` reads exactly like "there was no feedback".
There was: six rows, the oldest from **2026-07-22**, all still
un-incorporated.

Two things were wrong and both are now fixed:

- **The message was written before there were users.** "no users yet, not
  critical" is a claim about 2026-04; it survived into a repo with 30 users
  and live feedback. It now logs at ERROR, says the export **DID NOT RUN**,
  and the CLI exits **2** — the same precedent as this workflow's own
  `Check secrets` step, which already exits 1 because *on a scheduled trigger
  a missing secret is a misconfiguration, not a quiet no-op*.
- **A real defect was hiding underneath the one that hid it.** The item
  lookup was `WHERE id = ANY($1::text[])` against a `uuid` column, which
  raises `operator does not exist: uuid = text` the first time a price
  feedback row gives it an item to look up. Nobody had ever reached that
  line. Now `$1::uuid[]`; a `--dry-run` against prod finds the 6 rows and
  builds 1 lorcana training row.

### ✅ CLOSED the same day — and setting the secret found three more defects

`DB_DSN` was set (the **pooler** value: `db.<ref>.supabase.co` has no A
record, IPv6 only, and GitHub runners are IPv4 — the direct DSN would have
failed from CI for an unrelated reason and looked like the fix was wrong).

Then the step ran for the first time in its life, and **failed three more
times, each one layer deeper.** Every one of them was a type in the write
half of a file that had never executed past line 190:

| run | error | cause |
|---|---|---|
| 1 | `TypeError: Object of type UUID is not JSON serializable` | `"feedback_id": row["id"]` — an asyncpg UUID inside a `json.dumps`'d record |
| 2 | `operator does not exist: uuid = bigint` | `WHERE id = ANY($3::bigint[])` on a `uuid` column |
| 3 | ✅ **success** — `Wrote 1 rows`, `Marked feedback as incorporated: UPDATE 6` | |

Verified in prod after run 3: `still_pending = 0`, `incorporated = 6`,
`incorporated_run_id = export_20260905_202442_ba9e1579`. Six rows that had
been stuck since 2026-07-22 are through, and one lorcana training row exists.

⚠️ **The real lesson is about `--dry-run`, not about types.** I ran
`--dry-run` against prod between each of these and it went green every time,
because the dry-run branch skipped `json.dumps` AND skipped the UPDATE. **A
dry-run that skips the operation cannot verify the operation** — it verifies
the half of the code that was already working. Both are fixed at the source:
the export now serialises in both modes, and the dry-run **executes** the
UPDATE inside `conn.transaction()` and unwinds with a sentinel exception, so
the statement is genuinely prepared and run and nothing is committed. Proof:
dry-run now prints `UPDATE 6 (statement executed and rolled back)` and all
six rows remain `incorporated_at IS NULL` afterwards.

Ten log calls in the same file also formatted that UUID id with `%d`, every
one of them on a failure path — `"Skipping row %d"` would have raised
`%d format: a number is required, not UUID` **instead of reporting the error
it was written to report.** All now `%s`.

**The rule: a dry-run must do everything except the side effect.** Printing
"would do X" is not a test of X.

**The rule this adds:** a step that can no-op itself needs its no-op to be
distinguishable from its success in the log line a human actually reads.
"Which steps ran" is the first question; "and did the one that ran do
anything" is the second.

### First run on the corrected branch: 107 batches -> 14, and the gate fired

The 2026-08-30 nightly was the first to run on the repointed default branch.
Measured against `33181755459` (08-28, old code):

| class | 08-28 | 08-30 |
|---|---|---|
| `PGRST102` all keys must match | 42 | **0** |
| `client has been closed` | ~50 | **0** |
| `21000` within-batch duplicate | 15 | **0** |
| failed batches | **107** | **14** |

And the write-loss gate did its job — the run went **red** instead of silently
green:

```
Rows LOST: 2412 across 14 failed batch(es) — these were fetched and then not written
2412 rows were dropped by the writers — exiting with code 1.
```

⚠️ A `grep -c 21000` on that run returns 1. It is a FALSE POSITIVE — an mtg
progress line reading `| page 120 | (21000)`. Read the match, do not count it.

### The `client has been closed` fix regressed, and I misdiagnosed the cause (2026-09-05)

`nightly-ingest` was red on 09-03, 09-04 and 09-05. I first reported the cause
as *"upstream api.pokemontcg.io 5xx, not our code"* — because those errors
dominate the log by count. **That was wrong**, and the exit line says so:

```
Upsert catalog batch 3/5 (200 rows LOST) failed:
  Cannot send a request, as the client has been closed.
Rows LOST: 2254 across 13 failed batch(es) — exiting with code 1
```

The most numerous error is not the one that failed the run. **Read the exit
line, not the error histogram** — the same shape as the `grep -c 21000` false
positive noted above.

**The 08-29 fix had regressed** — or rather, it was never complete. Making
`SupabaseIngest.client` a property that re-resolves per call narrows the race;
it cannot close it, because a property cannot fix time-of-check/time-of-use:

```
thread A: self.client          -> returns a LIVE client
thread B: close_http_client()  -> closes that very object
thread A: client.post(...)     -> RuntimeError, 200 rows lost
```

And `_RETRYABLE_POST = (httpx.TransportError,)` does not catch it, because
httpx raises a bare `RuntimeError` for a closed client. So one sibling's
tidy-up cost 200 rows with no retry at all.

Fixed by ownership rather than by fixing six call sites: `hold_http_client()`
makes a sibling's close a no-op for the duration of an orchestrated run, and
only `release_http_client()` closes for real. `get_http_client()` is now
locked too (two threads could each build a client, leaking one). The retry
also re-resolves a closed client and treats *only* that RuntimeError as
retryable — any other one still raises.

### ✅ CONFIRMED on the 2026-09-06 nightly

First run carrying the fix (`34019203455`, sha `c848c7b`):

```
Rows LOST: 0                        (was 2,254 on each of 09-03/04/05)
'client has been closed': 0         (was 13 failed batches)
circuit-breaker trips: 79
-> success                          (was failure, four nights running)
```

**79 circuit trips is the design working, not a new fault.**
`api.pokemontcg.io` is still returning 5xx, and the run now abandons it in
bounded time instead of grinding three attempts through every set. The Pokémon
catalogue still is not refreshing — that is their outage — but it no longer
costs a red run or 2,254 dropped rows elsewhere.

Verify it yourself with `./scripts/check_nightly_ingest.sh`, which names the
run and sha it is judging and refuses to give a verdict on one that predates
the fix.

### The read side: the opposite retry rule, and an outbound budget

The pokemontcg 5xx were real even though they were not the failure. Three
defects in `fetch_json`, which every importer shares:

| defect | consequence |
|---|---|
| every status retried, including 4xx | a 404 burned 3 attempts to reach the same answer |
| flat `sleep(delay)` | 3 seconds total against a real incident, synchronised across parallel pipelines |
| a run of 429s `continue`d off the end of the loop | returned **`None`**, and every caller does `data.get(...)` on it |

⚠️ **Its rule is deliberately the inverse of `_post_with_retry`'s.** That
function retries no HTTP response because PGRST102/21000 are Postgres's
verdict on our exact payload. Here the response is a third party's and the
request is an idempotent GET, so a 5xx is weather and a 4xx is a verdict.
Both rules are written in both docstrings so neither gets "tidied" into the
other.

**And a budget, because we have been banned before.** tcgcsv.com blocked this
application for overuse on 2026-07-31 and that catalogue is still frozen.
Retrying harder into a struggling free API is how that happens twice, so
after `INGEST_HOST_FAIL_LIMIT` (default 8) consecutive 5xx from one host every
further call to it fails fast for the rest of the run — no socket, no retry.
A single success clears the streak.

Proved against a `git worktree` baseline rather than asserted:

| behaviour | pre-fix | fixed |
|---|---|---|
| attempts on a 404 | **3** | **1** |
| an all-429 run returns | **`None`** | raises `RuntimeError` |

12 new tests; `4051 passed` on the full suite (the 12 errors are pre-existing
and identical on the baseline worktree).

### Prod auth refills itself with fixtures, because CI runs against prod (2026-09-06)

Purging 24 synthetic accounts took prod from **30 users / 87 items to 6 / 17**.
Re-running the same purge **minutes later already found four more**, including
a recreated `ci-test@collectai.app` and two fresh `e2e_*@example.com`.

That is not drift — it is `sanity-e2e`, which runs on `push: branches: ["**"]`
and creates real accounts in **production** GoTrue on every push. The same fact
is noted above as the cause of self-inflicted `/auth/v1/admin/users` 5xx; this
is its other consequence.

**Why it matters more than it looks.** Before the purge, ~90% of `items` were
fixtures with names like `QA Test Card`, `E2E Upload Test`,
`DEMO Charizard Base Set Holo`. Every product metric computed over that table
was measuring our own test rows, and three successive strategic conclusions
were drawn from them before the population was checked. **A row count cannot
tell you whether the rows are real** — the tell was in the names.

After the purge the honest picture is: **one external user, holding one item.**

`server/scripts/purge_test_accounts.py` makes the mop repeatable (dry-run by
default, PROTECTED list asserted twice so `apple-review@sparrowcollect.com`
can never be caught by a pattern). **But the tap is CI**, and the real fix is
one of:

- point `sanity-e2e` at a non-production Supabase project, or
- narrow its trigger from `["**"]` to the default branch, or
- have it clean up on failure as well as success.

Not done here — it is a CI-topology decision, not a patch. Recorded so the
next person purging accounts knows they are treating a symptom.

⚠️ Two traps when purging: a user owning `marketplace_listings` rows fails with
HTTP 500 until the SECURITY DEFINER migration lands, and accounts with a NULL
`created_at` are invisible to GoTrue's admin listing entirely.

### The nightly-ingest cron comment is ~4h out (noted 2026-09-05)

`.github/workflows/nightly-ingest.yml` says `cron: "0 3 * * *"` with the
comment *"Run at 03:00 UTC every day (after training pipeline)"*. The last
three actual starts:

```
2026-09-05T07:15:27Z   2026-09-04T07:34:26Z   2026-09-03T07:33:46Z
```

Consistently **~4h15m late** — GitHub queues scheduled workflows on the free
tier and delivers them when capacity allows. Not a bug to fix, but two things
follow from it:

- **The watchdog (09:00 Europe/Paris = 07:00 UTC) runs BEFORE the ingest
  finishes**, so a watchdog report never reflects that morning's ingest.
- Do not read "it hasn't run at 03:05" as a failure.

Same family as [[learning_third_party_rate_bans_and_schedule_drift]]: the
stated schedule is a comment, not a constraint.

### The API key hypothesis was wrong (tested 2026-09-05, same evening)

I suggested the nightly's 5xx might be down to running **keyless** —
`POKEMONTCG_API_KEY` is set on EC2 but was not a repo secret. The secret is
now set, but **the measurement does not support the reason I gave for it.**

Interleaved from EC2, five pairs, two seconds apart, same URL:

```
pair 1:  with-key=200   keyless=500
pair 2:  with-key=500   keyless=200
pair 3:  with-key=500   keyless=200
pair 4:  with-key=500   keyless=500
pair 5:  with-key=500   keyless=200
         with-key 200s = 1/5 | keyless 200s = 3/5
```

Two conclusions, and neither is the one I predicted:

1. **`api.pokemontcg.io` is broadly unhealthy right now** — 500s and 502s on
   *both* paths, including `/sets`. The nightly's failures are genuine
   upstream weather, not a missing credential.
2. **Keyless did BETTER in this sample**, 3/5 against 1/5. That hints the key
   may be stale or rate-limited, but **n=5 cannot establish it** and I am not
   going to claim it does. It is a hint, not a finding.

So the key is not the fix. The thing that actually makes this survivable is
the backoff + circuit breaker above: the run now gives up on a dead host fast
instead of grinding through 3 attempts per set. If the key turns out to be
stale, `gh secret delete POKEMONTCG_API_KEY` costs nothing — the API works
without one.

**The lesson is the ordering.** I proposed a config change on a plausible
mechanism ("keyless from shared runner IPs") and only measured afterwards. The
measurement inverted it. A one-command test before the suggestion would have
saved the round trip — this is [[feedback_no_fixes_on_assumptions]] in a place
where the fix looked too cheap to bother verifying.

### The 14 that remain were transport, not logic

```
12x  Server disconnected without sending a response
 1x  The read operation timed out
 1x  [SSL: WRONG_VERSION_NUMBER] wrong version number
```

The classic stale keep-alive: Supabase closes an idle pooled connection, httpx
reuses it, the write dies. The writer had **no retry**, so one blip cost 200
rows permanently. `_post_with_retry()` now retries transport failures with
exponential backoff (`INGEST_POST_ATTEMPTS`, default 3).

**Retrying is safe HERE and not in general.** These upserts are
`ON CONFLICT ... DO UPDATE`, so a replay is a no-op. `DATA_SCALING_PLAN.md` §10
records the opposite: retrying a `market_hits` load duplicated 3,000 rows
because the conflict clause could not fire against a generated PK. **Check
idempotence before copying this pattern.**

**An HTTP response is never retried, however bad.** `PGRST102` and `21000` are
the server's judgement of this exact payload — they fail identically on replay,
three times as slowly, and hide nothing. Only the *absence* of a response is
retried.

There was a second reason to do this now: the gate makes the nightly red on any
dropped row, so without a retry it would redden on ordinary blips and train
everyone to ignore a gate built the day before.

⚠️ **Mutation-testing found two of my own tests non-discriminating.** Widening
the retryable tuple to bare `Exception`, and deleting the `break` before the
final sleep, both left every test green — the first because the "deterministic
rejection" case uses an HTTP *response* rather than an exception, the second
because the `for` loop already bounds attempts so counting them cannot see it.
Fixed by asserting on a non-transport exception, and by counting SLEEPS rather
than attempts. **A mutation that survives means the test is wrong, not that the
code is fine.**

### "Fails visibly — honest" was too generous (2026-08-30)

The line above used to read *"runs, and fails visibly — honest"*, written after
seeing it fail once. It failed on **every push**, and a gate that always fails
is not honest — it is noise that cannot signal anything.

Chasing it found a defect far outside CI. `GET /auth/v1/admin/users?email=…`
returns **HTTP 500 "Database error finding users"** — GoTrue has no email
filter on that endpoint. Measured:

```
GET /admin/users?email=x     -> 500
GET /admin/users?per_page=8  -> 200
GET /admin/users?per_page=9  -> 500   <- and this is the real find
```

`per_page ≤ 8` worked and `≥ 9` did not, with 31 users. Paging one at a time
showed **only page 2 failing**. Five rows held `NULL` in `confirmation_token`,
`recovery_token`, `email_change_token_new` and `email_change`; GoTrue scans
those into Go `string` fields and a NULL raises. All five were seed/test
accounts inserted by direct SQL that bypassed GoTrue's defaults — which is why
real signups were unaffected.

**Causation was proven before touching anything**: bad rows were entirely
contained in the one failing page, and no bad row appeared on any of the three
passing pages. Fixed with `COALESCE(col, '')` on the token columns; all four
pages then returned 200.

**The blast radius was never CI.** The same 500 breaks the Supabase dashboard's
Users page and any admin tooling that lists users, and it generated 32
`/admin/users` 5xx in a single day — which had become the *majority* of the
watchdog's "API returning 5xx" HIGH. A red test was the only thing pointing at
it.

Two things worth carrying:

- **A permanently-red gate hides the thing it was built to find.** This is the
  `ci-min` disease one day later, in a different workflow.
- ⚠️ **The workflow's own 5xx were self-inflicted noise.** `sanity-e2e` runs on
  `push: branches: ["**"]`, so ten pushes in a day meant ten hard-delete /
  recreate cycles against prod auth. Before reading a spike in
  `/auth/v1/admin/users` as a product regression, check how many times you
  pushed.

⚠️ Remaining, not fixed: `e2e-buyer@test.local` has a **NULL `created_at`**, so
GoTrue omits it — the admin API returns 30 of 31 users. Harmless (a leftover
test account, no longer 500s) but it means *listable* and *exists* are not the
same set.

### sanity-e2e: three real defects found, and it is STILL red (2026-08-30)

Chasing one permanently-red workflow surfaced three genuine production defects.
It is honest to record that the workflow did not go green.

**Fixed and verified:**

1. `GET /auth/v1/admin/users?email=…` returns **500** — GoTrue has no email
   filter there. The script used it for every lookup, so a 500 body carried no
   id and the run died at *"cannot resolve user id"*. Now pages and matches
   client-side; verified against prod for a page-1 user, a page-4 user, and an
   address that does not exist.
2. **Five rows with NULL token columns** (`confirmation_token`,
   `recovery_token`, `email_change_token_new`, `email_change`) broke user
   listing entirely — GoTrue scans them into Go `string`s. `per_page ≤ 8`
   worked, `≥ 9` did not; only the page containing those rows failed. This also
   broke the **Supabase dashboard's Users page** and produced 32 `/admin/users`
   5xx in a day. `COALESCE(col,'')` fixed it; all pages now 200.
3. **Ten FKs to `auth.users` with NO ACTION** blocked `DELETE FROM auth.users`.
   Nine now CASCADE; `sponsor_companies` is deliberately excluded (deleting a
   company because its admin left is the wrong semantics) and the migration
   asserts it is the only one left.

**Still failing**, and the useful part is why my verification was wrong:

I proved the delete worked by running `DELETE FROM auth.users` in a rolled-back
transaction — as a **superuser**. GoTrue runs as `supabase_auth_admin`. The
Postgres log shows `permission denied for table marketplace_listings`.
`SET LOCAL ROLE supabase_auth_admin` is itself denied from the app DSN, so it
could not be reproduced from the server.

⚠️ **Verifying as the wrong principal is not verifying.** "It works when I run
it" and "it works when the caller runs it" are different claims, and a superuser
psql session can prove neither one about a service role.

#### What the FK theory got wrong (corrected 2026-08-30)

The first read was "another NO ACTION FK". It is not. Measured:

| fact | value |
|------|-------|
| `marketplace_listings_user_id_fkey` | **already `ON DELETE CASCADE`** |
| owner of `public.marketplace_listings` | `postgres` |
| RLS on that table | **enabled** |
| `supabase_auth_admin` grants on it | **NONE** |
| non-internal triggers on `auth.users` | one, `AFTER INSERT` — not the delete path |

So the cascade is wired correctly and the delete still fails, which makes this a
**privilege** question, not a constraint question. Note the ambiguity that
remains: PostgreSQL runs RI cascade actions with the referencing table's owner's
privileges, which argues the cascade should succeed regardless of
`supabase_auth_admin`'s grants — yet the log names exactly that table. Those two
facts do not currently reconcile, and **that gap is the reason this is not
being patched by guessing a `GRANT`.**

#### ✅ SOLVED AND VERIFIED 2026-09-06 (evening)

`supabase/migrations/20260906_sync_item_for_sale_security_definer.sql` applied
via the SQL Editor. `sync_item_for_sale()` is now SECURITY DEFINER with
`search_path=public, pg_temp` pinned.

**Four checks, not one** — and the earlier premature "SOLVED" in this file is
exactly why:

| check | result |
|---|---|
| `prosecdef` / `proconfig` | `t` / `{"search_path=public, pg_temp"}` |
| **delete a user who OWNS a listing** (500 since 08-30) | **HTTP 200**, user and listing both cascaded |
| trigger still maintains the derived column | inserting a live listing set `items.for_sale = t` |
| **cross-user guard** — attacker lists the victim's item | victim's `for_sale` stayed **`f`** |
| `sanity-e2e` | **completed success** — first green since 2026-08-30 |

That third row is the reason variant B was chosen over a bare
`ALTER ... SECURITY DEFINER`: without the `user_id = owner_id` scoping, that
last test would have flipped another member's item to for-sale, because the
`marketplace_listings` INSERT policy constrains who owns the LISTING and says
nothing about `item_id`.

⚠️ The underlying weakness is still there: **a user can still create a listing
pointing at someone else's item.** The trigger no longer acts on it, but the
row is accepted. Constraining `item_id` to items you own belongs at the table
level and deserves its own pass — see the note at the end of the migration.

#### (history) NOT SOLVED — this section claimed "SOLVED" and was wrong

**Read this before the section below, which I wrote and pushed prematurely.**

What is genuinely established stands: the delete fails **only when the user has
`marketplace_listings` rows**, proven 20-vs-4 and by a controlled before/after
on one user. That part is solid.

**What was wrong was the fix.** I inferred "therefore
`supabase_auth_admin` is missing DELETE on that table", applied

```sql
GRANT DELETE ON public.marketplace_listings TO supabase_auth_admin;   -- did NOT work
```

verified the privilege flipped `false → true`, and then tested it properly: a
fresh user with exactly one listing, deleted without clearing anything first.
**Still HTTP 500, still `permission denied for table marketplace_listings`.**
The grant has been **REVOKED**; prod is back to baseline.

⚠️ My first attempt at that test was itself invalid — the item id captured
psql's `INSERT 0 1` status line, so the listing insert failed and the user had
**zero** listings when deleted. It returned 200 and I nearly recorded that as
proof the grant worked. The rerun asserts the precondition (`listings >= 1`)
and aborts if it is not met. **A test whose precondition silently failed is
worse than no test.**

So `DELETE` is necessary-but-insufficient at best, and the mechanism is still
not understood. **Do not add more grants by trial and error** — that is exactly
the "never grant to make an error go away" the rule below forbids. The open
questions: whether the cascade also needs `SELECT`, whether RLS on the table is
involved (`supabase_auth_admin` has no `BYPASSRLS`), and whether a trigger or a
second cascade hop is the actual failing statement.

#### ~~SOLVED 2026-09-06~~ — the evidence that IS good: `marketplace_listings` rows

**The blocker is not a mystery any more, and the diagnostic script was never
needed.** It fell out of the test-account cleanup as a natural experiment:
deleting 24 synthetic accounts, **20 succeeded and 4 failed** — and the 4
failures were exactly the 4 accounts that had `marketplace_listings` rows
(3, 6, 6 and 7 of them). Every account with zero listings deleted fine.

Then the controlled before/after, on one user
(`20503ad2-c62d-4700-810b-36da247bbf28` — the very id
`scripts/diagnose_gotrue_delete.sql` targets):

```
DELETE /auth/v1/admin/users/20503ad2-…   -> HTTP 500   (6 listings present)
DELETE FROM marketplace_listings WHERE user_id = …     (6 rows)
DELETE /auth/v1/admin/users/20503ad2-…   -> HTTP 200, user gone
```

Same user, same call, one variable changed. The other three failures then
deleted cleanly by the same route (7, 6 and 3 listings cleared).

**So `<X>` is `marketplace_listings`**, exactly as the Postgres log said all
along. ⚠️ But the obvious fix below was TRIED AND FAILED — see the correction
above:

```sql
GRANT DELETE ON public.marketplace_listings TO supabase_auth_admin;
```

⚠️ Still a production privilege change and still Merle's call — but the
discriminating output the section below demanded now exists, obtained without
`SET ROLE` at all.

**Why the earlier "it can't be privileges" reasoning was wrong.** 2026-09-05
established that `supabase_auth_admin` can DELETE on **zero** of the 44 tables
with an FK to `auth.users`, and concluded that since a stock Supabase project
is the same and deletes users fine, grants could not be the cause. The missing
step: **a cascade only needs the privilege on a table that actually has rows to
delete.** For 20 of these accounts every one of those 44 tables was empty, so
the missing grants never mattered. `marketplace_listings` was simply the only
one carrying rows. "No grants anywhere" and "deletes work" are perfectly
consistent right up until a user owns something.

#### ⛔ CORRECTION (2026-09-05): the SQL Editor cannot run it either

Everything below this heading was written on the assumption that *"the SQL
Editor connects as `postgres` and may assume the role"*. **The second half of
that sentence was never tested, and it is false.**

Measured via the Management API's `/database/query` endpoint — which is the
same execution path as the SQL Editor and reports `current_user = postgres`:

```
BEGIN; SET LOCAL ROLE supabase_auth_admin; ...
  -> ERROR 42501: permission denied to set role "supabase_auth_admin"
```

`postgres` on a managed Supabase project is **not a superuser**
(`rolsuper = false`; only `supabase_admin` is) and its role memberships are
`anon, authenticated, authenticator, collector_bot, pg_create_subscription,
pg_monitor, pg_read_all_data, pg_signal_backend, service_role,
supabase_functions_admin, supabase_privileged_role` — **`supabase_auth_admin`
is not among them.** No amount of clicking in the SQL Editor changes that.

(The endpoint *does* honour `ROLLBACK` — proved with a `set_config` round-trip
before anything else was run — so the safety design of the .sql file is sound.
It is the role assumption that fails, not the transaction.)

#### What the read-only test showed instead, and why "grant on that table" was wrong

`SET ROLE` is not needed to ask the privilege question. `has_table_privilege`
answers it for any role, from any session:

```sql
SELECT c.relname, con.confdeltype, pg_get_userbyid(c.relowner) AS owner,
       c.relrowsecurity AS rls,
       has_table_privilege('supabase_auth_admin', c.oid, 'DELETE')
  FROM pg_constraint con
  JOIN pg_class c  ON c.oid = con.conrelid
  JOIN pg_class rc ON rc.oid = con.confrelid
  JOIN pg_namespace rn ON rn.oid = rc.relnamespace
 WHERE con.contype = 'f' AND rn.nspname = 'auth' AND rc.relname = 'users';
```

Result across all **44** FK references to `auth.users`:
**`supabase_auth_admin` can DELETE on ZERO of them.** Owner is `postgres` and
RLS is on for every single one.

So `marketplace_listings` is **not special.** It is simply the table the
cascade reached first. The plan recorded below — *"grant on that table,
re-run, repeat"* — would mean granting on forty-four tables one at a time,
which is not a fix, it is a schema-wide privilege change discovered by
brute force.

⚠️ **And that makes the "does not reconcile" gap sharper, not softer.** A stock
Supabase project also does not grant `supabase_auth_admin` on user tables, and
GoTrue deletion works there. So "no grants" is the NORMAL state and cannot by
itself be the cause. Something else about this project is different, and it has
not been identified yet. **Still do not guess a `GRANT`.**

**The remaining discriminating test** needs the role to be assumable at all.
The only way to get there is a temporary, reversible membership —
`GRANT supabase_auth_admin TO postgres;` (postgres has `rolcreaterole`), run
the diagnostic, then `REVOKE`. That is a privilege change to production auth
and is **Merle's call, not a thing to do quietly.**

#### (superseded) The one discriminating test — run it in the Supabase SQL Editor

`scripts/diagnose_gotrue_delete.sql` does the thing no session on the EC2 box
can: `SET LOCAL ROLE supabase_auth_admin`, issue GoTrue's own `DELETE`, and
`ROLLBACK`. The SQL Editor connects as `postgres` and may assume the role; the
app DSN may not. It is safe — nothing outside a rolled-back transaction.

Two outcomes, two different fixes:

- **`DELETE 1`** → privileges are fine and the 500 is coming from somewhere else
  (a GoTrue-side error, or a different table). Do **not** grant anything; go
  back to the Postgres log with the `error_id`.
- **`permission denied for table <X>`** → `<X>` is the real blocker, and it may
  not be `marketplace_listings`. Grant on *that* table, re-run, repeat until it
  returns `DELETE 1`. Never grant on the whole schema to make an error go away.

Until that output exists, any `GRANT` here is a guess dressed as a fix.


**The cost of a permanently-red gate** is the theme here: it had been failing on
every push for long enough that nobody read it, and it was sitting on top of a
defect that broke the Supabase dashboard for everyone. `ci-min` was the same
disease the day before.

Before trusting a fix to a pipeline in this directory:

```bash
gh run list --workflow=nightly-ingest.yml --limit 3   # which ref ran
git show origin/<that-ref>:server/pipelines/<file>.py | grep <the fix>
```

See the three-way-drift table in `docs/DEPLOYMENT.md`.

## Safety Guards

| Guard | Flag | Description |
|-------|------|-------------|
| Dry-run | `--dry-run` | No writes, prints expected counts |
| Max items | `--max-items=N` | Cap rows per run (default: 1000) |
| Dedupe | (automatic) | Skip duplicates by content hash |
| Structured logging | (automatic) | `ingest_runs_v1` record for each run |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Service role key |
| `INGEST_S3_BUCKET` | No | S3 bucket for raw bundles |
| `INGEST_LOCAL_DIR` | No | Local fallback dir (default: `/tmp/collectai_ingest`) |
| `AWS_ACCESS_KEY_ID` | If S3 | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | If S3 | AWS credentials |

## Monitoring

### Check recent runs

```sql
SELECT run_id, started_at, status, processed_count, error_count
FROM ingest_runs_v1
ORDER BY started_at DESC
LIMIT 10;
```

### Daily stats

```sql
SELECT * FROM v_ingest_stats_daily LIMIT 7;
```

### Check taxonomy distribution

```sql
SELECT
    taxonomy_version,
    category_id,
    COUNT(*) as count
FROM raw_observation_pointers_v1
GROUP BY taxonomy_version, category_id
ORDER BY count DESC;
```

## Troubleshooting

### "No Supabase credentials"

Set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` environment variables.

### "S3 upload failed"

- Check AWS credentials
- Or let it fall back to local storage (fine for dev)

### High skip count

Duplicates are being filtered. This is normal if re-running on the same data.

### Low mapping confidence

Check taxonomy patterns - may need to add more patterns for edge cases.

## File Structure

```
scripts/ingest/
├── run_nightly.py       # Main entrypoint
├── ebay_ingest.py       # eBay-specific ingest (existing)
└── reddit_ingest.py     # Reddit-specific ingest (existing)

src/ingest/
├── __init__.py          # Module exports
├── types.py             # RawObservation, TrainingCandidate schemas
├── taxonomy_mapper.py   # Category/subtype mapping
├── s3_writer.py         # S3 bundle writer
└── supabase_writer.py   # Supabase table writers

.github/workflows/
└── nightly-ingest.yml   # GitHub Actions workflow

supabase/migrations/
└── 20260202_ingest_pipeline_tables.sql  # Table definitions
```
