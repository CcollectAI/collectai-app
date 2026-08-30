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
| `nightly-train-eval-gate` | ⚠️ runs, but its gate step has never gated |
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
