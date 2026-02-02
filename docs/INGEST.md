# CollectAI Nightly Ingest Pipeline

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
