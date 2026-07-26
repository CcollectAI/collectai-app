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
