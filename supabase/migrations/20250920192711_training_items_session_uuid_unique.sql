-- Ensure a unique index exists for upserts on session_uuid.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = 'public'
      AND indexname = 'training_items_session_uuid_key'
  ) THEN
    CREATE UNIQUE INDEX training_items_session_uuid_key
      ON public.training_items(session_uuid);
  END IF;
END$$;

-- Refresh PostgREST routes/caches
NOTIFY pgrst, 'reload schema';
