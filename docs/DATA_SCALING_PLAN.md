# Data Scaling Plan — 12-Month Horizon

**Author:** R50m session (2026-04-19)
**Trigger:** `market_hits` hit 528k rows with 24 indexes; PostgREST batch upserts started timing out at the Supabase pooler 30s cap, stalling the ingest pipeline.

This document is the answer to the question: "we will have unbelievably large amounts of data in 12 months — how do we architect for it now so we don't rebuild it later?"

---

## 1. Current state (2026-04-19)

| Table | Rows | Growth | Reads |
|---|---|---|---|
| `market_hits` | 528k | ~30k/week from scrapers | hot: valuation, calibration, deal discovery. cold: model training |
| `price_predictions` | 99k (last 7d) | ~14k/day | hot: app reads per item |
| `category_items` | 140k | mostly static | hot: catalog browse, matching |
| `items` | small | user-driven | hot: portfolio |
| `events` | ~300 | 10-50/week | hot: events tab |
| `label_events` | static | **not written by the live scan path** | hot: feedback loop, train data |
| `spend_events` | empty | per paid API call | hot: budget circuit breaker |
| `calibration_snapshots` | 0 (until today) | 54/day | cold: model health |

**The single problematic table is `market_hits`.** Everything else scales linearly with users (which we don't have yet) or is small enough to not matter.

## 2. The two growth axes

1. **Scrape volume:** every adapter writes to `market_hits`. Today ~30k/week. With full adapter coverage (44 sources × 54 categories × daily sweeps), realistic 12-month target = **5-15M rows**.
2. **Per-item pressure:** each item accrues `market_hits` over time. At 140k catalog items × 20 average hits each → **2.8M base load** just from existing catalog coverage, before new items.

Conservative 12-month target: **~10M rows in `market_hits`**. That's 20x today.

## 3. The architectural constraint

**Supabase pooler transaction mode has a 30s statement timeout.** Every INSERT, UPDATE, DELETE done via PostgREST (import pipelines, adapter persist path, API writes) is subject to this cap. It applies to:
- Index maintenance on every INSERT
- ON CONFLICT upsert scans
- Autovacuum that happens mid-query
- Any trigger fired on the row

At 528k rows + 24 indexes we already exceeded it. Without changes, we'd hit it again at ~1M rows even with today's 10 indexes.

## 4. The layered plan

### Tonight (done in R50m): Hot/cold split
- `market_hits` = last 90 days (~150k rows)
- `market_hits_archive` = everything older (append-only, cheap)
- Buys 3-6 months of runway. Immediate fix.

### Month 1: Time-range partitioning
Migrate `market_hits` to `PARTITION BY RANGE (seen_at)` with monthly partitions.

```sql
CREATE TABLE market_hits (
  -- columns
) PARTITION BY RANGE (seen_at);

CREATE TABLE market_hits_2026_04 PARTITION OF market_hits
  FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
-- ...plus monthly partitions ahead, auto-created by pg_partman
```

**Why this works:**
- INSERTs route to the current-month partition only. A single month = ~100k rows, 10 indexes. Well under the 30s cap.
- Partition pruning: queries with `WHERE seen_at > now() - interval '30 days'` only touch the latest 1-2 partitions.
- Archive story: `DETACH PARTITION` is instant. Drop or move to archive-tier storage.
- Zero code changes for reads/writes — Postgres partitioning is transparent.

**Tooling:** Install `pg_partman` extension (available on Supabase). Set retention to 12-18 months on the hot tier.

### Month 2-3: Tiered storage — hot in Postgres, cold in S3 Parquet

**The "data lake" part of the question.** Here's the tiered layout:

| Tier | Location | Age | Format | Cost | Query speed |
|---|---|---|---|---|---|
| Hot | Supabase Postgres, partitioned | 0-6 months | row-store | $25/mo (already paid) | single-digit ms |
| Warm | S3 Parquet via DuckDB | 6-24 months | columnar | ~$0.023/GB/mo | 100-1000 ms |
| Cold | S3 Glacier | 24+ months | columnar | ~$0.004/GB/mo | hours |

**Data lake path for warm tier:**
1. Nightly job: for each partition > 6 months old, export to `s3://collectai-warehouse-prod-eu-north-1/market_hits/year=2026/month=04/part-NNN.parquet`
2. Schema: Apache Parquet, snappy compression, partitioned by `year/month/category`. Expected ~10x compression vs Postgres (columnar + dict encoding).
3. Read path: `DuckDB` as query engine. It reads Parquet straight from S3 with predicate pushdown. 100x cheaper than keeping everything hot.
4. DETACH old Postgres partitions after S3 export verified.

**What queries stay fast after this split:**
- Deal discovery, valuation, user-facing pages → all use last 6 months → hot tier, unchanged.
- Model training (weekly/monthly) → can read warm tier via DuckDB. Training jobs don't care about 1-second latency.
- Admin analytics (lifetime user history etc.) → DuckDB unified view (`CREATE VIEW market_hits_all AS SELECT * FROM market_hits UNION ALL SELECT * FROM read_parquet('s3://...'))`).

### Month 4-6: Category sharding overlay (if needed)

If any single month's partition exceeds 500k rows (→ MTG/Pokemon/Yu-Gi-Oh at scale), **sub-partition by category hash** within monthly partitions. Postgres 12+ supports 2-level partitioning natively.

```sql
CREATE TABLE market_hits_2026_06
  PARTITION OF market_hits FOR VALUES FROM ('2026-06-01') TO ('2026-07-01')
  PARTITION BY HASH (category);

CREATE TABLE market_hits_2026_06_h0 PARTITION OF market_hits_2026_06
  FOR VALUES WITH (MODULUS 8, REMAINDER 0);
-- ...7 more
```

This is overkill today; add only when a monthly partition shows strain.

### Month 6+: Read replica for heavy analytics
Supabase offers read replicas. Deal discovery, scheduled batch jobs, ML training reads go to the replica. Writes + latency-sensitive reads stay on primary. Unblocks long-running analytical queries that would otherwise hold locks.

---

## 5. Other tables at 12-month scale

### `price_predictions`
At 14k/day → **5M rows/year**. Same pattern as `market_hits`: partition by `generated_at` monthly, archive > 6 months to S3 Parquet.

### `label_events` / `predict_sessions`
User-driven → scales with DAU. At 10k DAU × 5 scans/day × 365 = **18M/year**. Monthly partitioning from day one.

### `spend_events`
~1k/day at scale → **365k/year**. Small enough to stay single-table but index tightly (month_key + provider).

### `category_items`
Near-static ~200k. No action.

### `market_hits_archive` (the bucket we create tonight)
Becomes the seed for the Parquet lake in month 2. Don't add indexes to it, don't query it online — it's a holding pen until S3 export.

### Deal discovery scales in CAPACITY but not in FRESHNESS (measured 2026-08-12)

`deal_discovery` is capped at `MAX_MANDATES_PER_CYCLE = 50` on a 30-minute
interval — a hard ceiling of **2,400 mandate-scans/day**, ordered
`last_scan_at ASC NULLS FIRST` so no user starves. Nothing errors past that
point; scans just get rarer. At Pro's 10 mandates/user:

| Paying users | Mandates | Each scanned every |
|---|---|---|
| 5 | 50 | 30 min |
| 50 | 500 | ~5 hours |
| 500 | 5,000 | ~2 days |

**A deal alert on a live marketplace listing that arrives two days late is
worthless**, and nothing reports that: the worker returns `ok`, the silent-writer
probe sees writes. The scaling lever is the cap and the interval, and the metric
to watch is `now() - last_scan_at`, which nothing currently alerts on.

Three secondary limits: `deal_discovery` shares one global `_HEAVY_LOCK` with
the marketplace scraper (a 167.5s wait for the gate was observed on 08-12); the
5s per-adapter budget is a latency guard, not a rate guard; and
`source_rate_limits` holds exactly one row (`reverb`) — **no eBay entry** — so
2,400 searches/day × adapters is unguarded against a third-party quota
([[learning_third_party_rate_bans_and_schedule_drift]]).

The `market_hits` feed is NOT a scaling risk: it dedupes on
`(provider, listing_id)` with `WHERE NOT EXISTS`, so re-scans of the same query
add nothing.

## 6. Governance rules (to prevent R50m from repeating)

These are the rules we didn't have that caused 24 indexes on one table:

1. **Index policy:** every new index requires a written justification (comment in the migration) of which existing index doesn't serve. Default state = refuse to add.
2. **Schema changes benchmark the write path.** Before merging a migration, compare INSERT latency before/after. Pooler caps this at 30s; we target 5s.
3. **Autovacuum health in the correctness probe.** Dead-tuple ratio > 15% → page Telegram. Last vacuum > 24h with >1k dead rows → page.
4. **Row count alarms.** Any table over 1M rows shows up in the daily audit with "partition candidate" flag.
5. **Quarterly schema audit.** Index sizes, row counts, slow queries. Documented in learnings essay as "Audit reality against memory quarterly" — now becomes a scheduled deliverable.
6. **Pooler vs direct connection split.** The application request path (latency-sensitive) uses the pooler. Worker processes doing bulk inserts use a separate direct-connection DSN (port 5432 session mode) so they can't get guillotined mid-upsert. Two `.env` vars: `DB_DSN` (pooler) and `DB_DSN_DIRECT` (direct).

## 7. What to implement in what order

| Week | Task | Risk | Reversible? |
|---|---|---|---|
| 1 (now) | Hot/cold split via archive table | low | yes (copy back) |
| 1 | `DB_DSN_DIRECT` for worker upserts | low | yes |
| 2 | pg_partman install + monthly partitioning on `market_hits` | medium | yes (rollback script) |
| 3 | Same partitioning on `price_predictions` | medium | yes |
| 4-5 | S3 Parquet export + DuckDB read layer | medium | yes (Parquet is append-only, Postgres retains truth) |
| 6 | Read replica for analytics workloads | low | yes |
| 8 | pg_partman auto-archive > 6 months to S3 | medium | yes |
| ongoing | Governance rules + quarterly audit | low | n/a |

## 8. What we're explicitly NOT doing

- **No Redshift / Snowflake.** DuckDB on S3 is 100x cheaper and good enough for this scale. Only reconsider at 1B+ rows or when query concurrency demands separated compute.
- **No Kafka / Kinesis.** Scrapers write directly to Postgres. Adding a message bus is overkill until we have multiple consumers of the same stream.
- **No NoSQL.** The data is relational (items↔market_hits↔predictions↔categories). Document stores would lose us JOIN performance that we rely on.
- **No custom ORM.** Plain asyncpg + PostgREST is the most-understood, least-surprising path. ORM migrations are where silent schema drift comes from (essay recommendation #5).

## 9. What makes this 12-month-durable

The plan separates **storage format** (Postgres row / S3 columnar) from **query path** (partition pruning / DuckDB). Each layer is independently replaceable:

- Postgres can move to RDS / Aurora / Neon without changing the S3 warm tier.
- S3 can be replaced by GCS / R2 / Azure Blob; DuckDB speaks all of them.
- The application code touches only "active `market_hits`" — the lake exists behind an analytical read view.
- Growth pressure pushes rows _older_, not _wider_. The hot tier stays the same size forever if partitioning + archival are working.

---

**Status:** hot/cold split running tonight on EC2 (R50m). pg_partman + monthly partitioning = week 2 deliverable. S3 Parquet export = week 4-5 deliverable.

---

## 10. Lessons from the R50m rollout (appended 2026-04-19)

### ON CONFLICT + partitioned tables

Postgres requires any unique constraint on a partitioned table to include the partition key columns. That means `ON CONFLICT (provider, listing_id) DO NOTHING` stops working after you partition by `seen_at` — you either need to include `seen_at` in the conflict target (which defeats deduplication since `seen_at = NOW()` is unique per insert) or change writers to use `WHERE NOT EXISTS`.

**Fix we shipped for marketplace_agent (asyncpg direct writer):**
```sql
INSERT INTO market_hits (...)
SELECT $1, $2, ...
WHERE NOT EXISTS (
  SELECT 1 FROM market_hits WHERE provider = $1 AND listing_id = $2
);
```
This uses the `(provider, listing_id, seen_at)` composite index's leading columns for a fast existence probe across partitions.

**Fix pending for PostgREST writers (tcgcsv, discogs):** PostgREST's `?on_conflict=...` query param can't be converted to `WHERE NOT EXISTS` directly. Need a Supabase SQL function (RPC) that does the dedup server-side. Those two daily workers are disabled in the bake_orchestrator manifest until the RPC ships.

### Bucket naming

Original bucket `collectai-datalake` was renamed to `collectai-warehouse-prod-eu-north-1` the same day, before any data landed. Convention: `collectai-{purpose}-{env}-{region}`. Rationale: the bucket name doesn't need dates (S3 lifecycle + Hive-style object-key partitioning handle aging) but it DOES need env + region for multi-region / multi-env futures.

### Writer bugs hide in INSERT column lists

After partitioning, a `null_category_rate` audit alarm fired — 58,995 market_hits rows had NULL category in the last 7 days, all with recoverable `category:` prefix in `item_ref`. Root cause: `persist_comps_to_db` accepted `category` as a kwarg but never included it in the INSERT column list. Adding to the list + backfilling fixed it, but the broader lesson is **every kwarg a writer accepts should have a CI test asserting the resulting row has that column populated**. The R50l essay's "post-write assertion at the writer" rule would have caught this on day 1.

### Within-batch dedup is also required (appended 2026-05-02)

Follow-up to the partitioned-table ON CONFLICT issue above. The
`upsert_market_hits_batch` RPC shipped in `20260426_upsert_market_hits_batch_rpc.sql`
deduplicates against `market_hits` (across batches via `WHERE NOT EXISTS`)
but did NOT deduplicate within a single input batch.

If a batch contains the same `(provider, listing_id)` more than once
(which the discogs pipeline does on retries / pagination overlap):

1. Both duplicate input rows pass `WHERE NOT EXISTS` (table is empty for them)
2. Both get the same `now()` (one statement → one timestamp evaluation)
3. The unique constraint on `(provider, listing_id, seen_at)` rejects the second
4. Postgres rolls back the entire INSERT — **all 100 rows in the batch are lost**

Caught 2026-05-02 when the user reported "ingest stalled, no market_hits in 30
minutes". `bake.log` showed `Persisted 0/N hits` over and over for `discogs_listing`.
Verified: every 23505'd `listing_id` was missing from `market_hits` — the
duplicate rejection cascaded to the rest of the batch via atomic rollback.

Fix in `20260502_upsert_market_hits_batch_dedup_within_batch.sql` —
adds `DISTINCT ON (provider, listing_id)` to the input CTE so duplicates
inside a batch are collapsed to one row before INSERT. Pure RPC body
change, no schema migration, no bake restart.

**Generalizable rule:** any RPC or batch-INSERT path with `WHERE NOT EXISTS`
must also `DISTINCT ON` the input by the columns participating in the
unique key. Defense in depth — even if the caller "should" dedup. The
atomic-rollback amplification (one bad row → 100 lost) is too costly.

### Retention worked exactly as designed and still armed a landmine (appended 2026-08-02)

The DB reached 7305 MB and read as "near cap". Nothing was broken:
`market_hits_y2026m07` (2223 MB) and `price_history_y2026m07` (692 MB) were
past their 1-month retention and fully exported, but `partition_drop_worker`
had refused to drop them and logged an error:

```
2026-08-01 16:38:46  error  "2 partitions old enough but missing from
                             manifest: [market_hits_y2026m07,
                                        price_history_y2026m07]"
2026-08-01 16:42:35  market_hits_y2026m07    exported
2026-08-01 16:45:27  price_history_y2026m07  exported
```

**The drop worker runs ~30–60s BEFORE the export worker in every cycle** (also
visible on 07-31 at 17:11/17:12 and 09:33/09:34). Eleven months a year that is
invisible, because both are no-ops. On the one day a month a month closes, the
drop checks a manifest that does not yet contain it, refuses, and errors. The
next cycle succeeds. The gate behaved correctly — it would rather error than
drop unexported data — but it emits an error row that pages Telegram for a
condition that resolves itself.

**The real cost was downstream.** `schema.lock.json` locked the partition
CHILDREN. Dropping two of them left the lock naming tables that no longer
existed, so `preflight_schema_lock.py` — stage 8 of the 9-stage `ExecStartPre`
chain — failed:

```
❌ 2 locked tables MISSING       ❌ 3 locked UNIQUE keys MISSING
❌ 2 locked CHECK constraints MISSING          verdict: FAIL (exit 1)
```

That gate **only runs at startup**. The running API was unaffected; the next
bake restart — a deploy, a reboot, an OOM restart — would have hard-downed it,
with the cause hours in the past and no obvious link to a routine retention
drop. This had already happened at least once (`d54e947`, "sync regenerated
schema.lock after the view + partition drop").

**Fix: `regen_schema_lock.py` now excludes `c.relispartition` rows.** Partition
children are created by pg_cron on the 25th and dropped by the retention worker
by design — locking them makes routine churn indistinguishable from schema
drift. The partitioned PARENTS stay locked in full (`market_hits` 30 cols,
`price_predictions` 21, `price_history` 11), which is where the code contract
actually lives; no application code references a child by name (verified by
grep across `app/`, `src/`, `server/app/` — zero hits for `_y20\d\dm\d\d`).

`relispartition` rather than a name regex, because it is exact — measured on
live: 3 parents + 304 ordinary tables kept, 8 children excluded, including the
`_default` partitions that a `_yYYYYmMM` pattern would have silently kept.

**Verification discipline that mattered here**, since the operation deletes
2.9 GB irreversibly:

1. The manifest is written by the same worker that claims success — it is
   self-attested, so it is evidence, not proof. Every one of the 122 parquet
   parts was HEAD-checked individually, the summed object sizes compared to the
   manifest byte totals (340,483,081 and 92,845,505 — exact match), the part
   after the last confirmed absent, and the final part's `PAR1` magic read back.
2. Postgres row counts were compared to manifest rows (4,114,488 and 1,948,837
   — exact match) BEFORE the drop.
3. Dry-run first (`PARTITION_DROP_ENABLED=false`) to confirm the target list.
4. The gate was proven to FAIL after the drop and PASS after the regen, and the
   narrowed lock was mutation-tested — injecting a fake locked table still
   produces `verdict: FAIL`, so excluding partitions did not disable drift
   detection.

**A trap worth recording:** the first S3 verification returned `AccessDenied`
on all 122 objects and looked like catastrophic data loss. The EC2 instance
role cannot read the bucket; the export worker uses credentials from
`/opt/collectors/.env`. **Any S3 check against this bucket must source that
env first** — a bare `aws`/`boto3` call on the box falls back to the instance
role and reports missing data that is actually present.

Result: 7305 MB → 4390 MB, API healthy throughout, all 9 preflight stages green.

**Still open (deliberately not folded into the cleanup):** the drop-before-export
ordering. It is benign — one spurious error per month-close, self-resolving next
cycle — but it should either run export-before-drop, or the drop should treat
"eligible but not yet exported this cycle" as info rather than error.

---

## Growing the catalogue from what we already collect (appended 2026-08-12)

`server/pipelines/mine_catalog_from_market_hits.py`

Hand-typing catalogue rows does not scale — a batch of 15 against a market that
holds thousands. Every marketplace title we already store names a real product,
so the catalogue is derivable from `market_hits` rather than authored.

The miner reads titles, extracts `(brand, reference)` with a **per-brand
grammar** — Rolex six digits, Omega dotted `310.30.42.50.01.002`, Cartier
`W`/`WS`/`CRW` codes, and so on — and diffs the result against `category_items`.
One grammar per brand, not one regex for all: `116610LN` and `5711/1A-010` have
nothing structurally in common, and a permissive pattern is what produced the
first run's garbage.

Run it read-only, read the output, then promote:

```bash
python -m pipelines.mine_catalog_from_market_hits --category watches
python -m pipelines.mine_catalog_from_market_hits --category watches --promote
```

Default `--promote` writes **high-confidence only** (a brand-specific grammar hit,
unambiguous, not a partial). `--include-medium` also writes titles matched by the
generic fallback — those need eyes on them first.

### Four filters, each of which exists because of a bug it let through

| Filter | What it stopped |
|---|---|
| ≥2 digits in the reference | The Cartier grammar matched the literal word `WATCHES` |
| `^\d{2,4}M$` rejected | `200M` is water resistance; nine different brands "made" it |
| Cross-brand ambiguity → skip | One string claimed by several grammars is not a reference |
| Containment → skip | `Casio GA-110` is a partial of three catalogued collabs, not a new row |

### Two things this does NOT do

**It does not make the rows priceable.** eBay's Browse API returns 100% live
listings, and `valuation_worker.py:279` excludes `is_listing IS TRUE`, so mined
rows are browsable and searchable but carry no comps until eBay Marketplace
Insights is approved (`ebay_caller.py:387 sold_comps()` is still stubbed).
Growing the catalogue and growing price coverage are separate problems — see
[[learning_coverage_in_price_rows_is_not_coverage_in_offers]].

**It does not resolve brand aliases.** Bvlgari/Bulgari, Hermes/Hermès,
Christian Dior/Dior and S.T.Dupont/ST Dupont are each two brands to the miner.
Dedup is exact-match after prefix-stripping, so aliases produce near-duplicate
rows that no key check catches. Open.

### Duplicate checks must compare titles, not keys

Two batches shipped duplicates past a key-uniqueness check, because a key is
generated from the title and any wording difference makes a fresh one. The
second batch still missed two exact Cartier duplicates: house-brand titles
(Cartier, Van Cleef & Arpels) don't repeat the brand in the title the way
`Rolex Submariner` does, so the comparison has to strip the brand prefix before
matching. Compare normalised titles both ways or you are not checking anything.
