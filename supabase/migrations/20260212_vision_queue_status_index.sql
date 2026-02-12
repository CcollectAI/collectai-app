-- vision_queue performance index for worker polling
-- The vision_ingest_worker queries: WHERE status = 'pending' ORDER BY created_at ASC
-- This composite index supports both the filter and the sort in one scan.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_vision_queue_status_created
    ON public.vision_queue (status, created_at ASC);
