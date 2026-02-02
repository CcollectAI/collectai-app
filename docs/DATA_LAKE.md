# CollectAI Hybrid Data Architecture

## Overview

CollectAI uses a hybrid data architecture:

- **Supabase Postgres** - App-critical data, curated training, per-user state
- **S3** - Large volumes (market comps, images, embeddings), cheap storage, batch analytics

**Design Rule:** Postgres stores what the app needs NOW. S3 stores what models need to learn at scale.

## Data Split

| Data Type | Supabase Postgres | S3 |
|-----------|-------------------|-----|
| User items (collection) | ✅ `public.items` | Optional mirror |
| Watchlist + alerts | ✅ `public.watchlist`, `public.alerts` | No |
| Latest price prediction | ✅ `public.price_predictions` | Optional history |
| Curated training anchors | ✅ `public.training_items_v1` | Optional archive |
| User feedback events | ✅ `public.user_feedback_events_v1` | Optional archive |
| Market comps (full history) | No (summary only if needed) | ✅ Partitioned by date/category |
| Vision images + OCR | Metadata pointers only | ✅ Images, JSONL |
| Embeddings | No | ✅ Parquet files |

## S3 Layout (Dataset Lakehouse)

```
s3://<bucket>/
├── market_comps/
│   └── dt=2026-02-02/
│       └── category_id=pokemon/
│           └── source=ebay/
│               └── *.parquet
├── price_comps/
│   └── dt=2026-02-02/
│       └── category_id=mtg/
│           └── *.parquet
├── vision/
│   ├── images/
│   │   └── dt=2026-02-02/
│   │       └── user_id=abc123/
│   │           └── *.jpg
│   └── extracts/
│       └── dt=2026-02-02/
│           └── user_id=abc123/
│               └── *.jsonl
├── embeddings/
│   └── dt=2026-02-02/
│       └── model=clip-vit-b32/
│           └── *.parquet
└── training/
    ├── raw/
    └── processed/
```

### Path Conventions

- `dt=YYYY-MM-DD` - Date partition for time-based queries
- `category_id=X` - Category partition for filtering
- `user_id=X` - User partition for isolation
- `source=X` - Data source (ebay, tcgplayer, etc.)
- `model=X` - Model version for embeddings

## Files

- `src/storage/objectStore.ts` - Interfaces and mock implementation
- Backend: `app/routes/storage.py` (to be created) - Presigned URL generation

## Security

**CRITICAL: Never put AWS credentials in the mobile app.**

Upload flow:
1. App requests presigned URL from backend
2. Backend generates URL with proper IAM credentials
3. App uploads directly to S3 using presigned URL
4. App saves metadata pointer to Postgres

```typescript
// In mobile app
const store = getObjectStore();

// 1. Get presigned URL from backend
const { uploadUrl, objectKey } = await store.getPresignedUploadUrl({
  prefix: 'vision/images',
  filename: 'scan_001.jpg',
  contentType: 'image/jpeg',
  userId: currentUser.id,
});

// 2. Upload to S3
await store.uploadWithPresignedUrl(uploadUrl, imageBlob, 'image/jpeg');

// 3. Save pointer to Postgres
await store.saveObjectPointer({
  objectKey,
  bucket: 'collectai-data',
  contentType: 'image/jpeg',
  sizeBytes: imageBlob.size,
  createdAt: new Date().toISOString(),
});
```

## Postgres Tables

### Minimal Required Tables

```sql
-- User items (collection)
public.items

-- Curated training anchors (small, high-signal)
public.training_items_v1

-- User feedback (edits, verified sales)
public.user_feedback_events_v1

-- Price predictions with quantiles
public.price_predictions

-- Object storage pointers
public.object_pointers (
  id uuid PRIMARY KEY,
  object_key text NOT NULL,
  bucket text NOT NULL,
  content_type text,
  size_bytes bigint,
  hash text,
  user_id uuid,
  category_id text,
  created_at timestamptz DEFAULT now(),
  metadata jsonb
)
```

## Training Strategy

### Keep Costs Low

1. **Postgres** holds only curated anchors (hundreds → low tens of thousands)
2. **S3** holds raw comps, noisy OCR as append-only logs
3. Calibration loop uses feedback signals:
   - Verified sale prices
   - User purchase prices
   - User overrides/corrections
   - Comps drift detection
   - Engagement signals

### Batch Jobs

Nightly/weekly jobs can:
1. Read from S3 (cheap bulk scans)
2. Read from Postgres (curated anchors)
3. Train/calibrate models
4. Write small calibration params back to Postgres

## Implementation Checklist

### Phase 1: Stubs & Interfaces (Current)
- [x] `src/storage/objectStore.ts` - Interface + mock
- [x] Path builder functions
- [x] Type definitions

### Phase 2: Backend Presigned URLs
- [ ] FastAPI endpoint for presigned upload URLs
- [ ] FastAPI endpoint for presigned download URLs
- [ ] IAM policy for upload bucket

### Phase 3: Postgres Pointers
- [ ] `object_pointers` table migration
- [ ] RLS policies (user-owned objects)
- [ ] Index on category_id, user_id, created_at

### Phase 4: Integration
- [ ] Replace mock with real backend calls
- [ ] Upload flow in QuickScan
- [ ] Background sync for large datasets

## Best Practices

1. **Always partition by date** - Enables cheap time-range queries
2. **Store pointers in Postgres** - Source of truth for existence
3. **Use Parquet for analytics** - Columnar, compressed, fast
4. **Use JSONL for streaming** - Easy append, line-by-line processing
5. **Never expose S3 directly** - Always through presigned URLs
