-- ============================================================================
-- Chat Improvements: Typing Indicators + Read Receipt Support
-- 2026-02-22
-- ============================================================================

-- ────────────────────────────────────────────────────────────────────────────
-- 1. TYPING INDICATORS TABLE
-- Ephemeral presence: upserted when a user types, polled by the other user.
-- Rows older than 10 seconds are stale and should be ignored client-side.
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.chat_typing (
  thread_id   uuid NOT NULL REFERENCES public.dm_threads(id) ON DELETE CASCADE,
  user_id     uuid NOT NULL,
  last_typed  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (thread_id, user_id)
);

ALTER TABLE public.chat_typing ENABLE ROW LEVEL SECURITY;

-- Participants can read typing status in their threads
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'chat_typing' AND policyname = 'chat_typing_select'
  ) THEN
    CREATE POLICY chat_typing_select ON public.chat_typing
      FOR SELECT USING (
        EXISTS (
          SELECT 1 FROM public.dm_threads t
          WHERE t.id = thread_id
            AND auth.uid() IN (t.requester_id, t.responder_id)
        )
      );
  END IF;
END $$;

-- Users can upsert their own typing row
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'chat_typing' AND policyname = 'chat_typing_insert'
  ) THEN
    CREATE POLICY chat_typing_insert ON public.chat_typing
      FOR INSERT WITH CHECK (user_id = auth.uid());
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'chat_typing' AND policyname = 'chat_typing_update'
  ) THEN
    CREATE POLICY chat_typing_update ON public.chat_typing
      FOR UPDATE USING (user_id = auth.uid());
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'chat_typing' AND policyname = 'chat_typing_delete'
  ) THEN
    CREATE POLICY chat_typing_delete ON public.chat_typing
      FOR DELETE USING (user_id = auth.uid());
  END IF;
END $$;

-- ────────────────────────────────────────────────────────────────────────────
-- 2. RPC: upsert typing indicator
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_set_typing_v1(
  p_thread_id uuid
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER
AS $$
DECLARE
  v_user_id uuid := auth.uid();
BEGIN
  -- Verify the user is a participant
  IF NOT EXISTS (
    SELECT 1 FROM public.dm_threads t
    WHERE t.id = p_thread_id
      AND v_user_id IN (t.requester_id, t.responder_id)
      AND t.status = 'accepted'
  ) THEN
    RAISE EXCEPTION 'Thread not found or not accepted';
  END IF;

  INSERT INTO public.chat_typing (thread_id, user_id, last_typed)
  VALUES (p_thread_id, v_user_id, now())
  ON CONFLICT (thread_id, user_id)
  DO UPDATE SET last_typed = now();
END;
$$;

-- ────────────────────────────────────────────────────────────────────────────
-- 3. RPC: clear typing indicator (when message is sent or user stops)
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_clear_typing_v1(
  p_thread_id uuid
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER
AS $$
BEGIN
  DELETE FROM public.chat_typing
  WHERE thread_id = p_thread_id
    AND user_id = auth.uid();
END;
$$;

-- ────────────────────────────────────────────────────────────────────────────
-- 4. RPC: get typing status for a thread (returns other user's typing state)
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_get_typing_v1(
  p_thread_id uuid
) RETURNS TABLE(user_id uuid, is_typing boolean)
LANGUAGE plpgsql SECURITY DEFINER STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT
    ct.user_id,
    (ct.last_typed > now() - interval '8 seconds') AS is_typing
  FROM public.chat_typing ct
  WHERE ct.thread_id = p_thread_id
    AND ct.user_id != auth.uid();
END;
$$;

-- ────────────────────────────────────────────────────────────────────────────
-- 5. Cleanup: periodically remove stale typing rows (older than 30 seconds)
-- This can be called from a cron job or just let them accumulate harmlessly.
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.cleanup_stale_typing()
RETURNS void LANGUAGE sql SECURITY DEFINER
AS $$
  DELETE FROM public.chat_typing
  WHERE last_typed < now() - interval '30 seconds';
$$;
