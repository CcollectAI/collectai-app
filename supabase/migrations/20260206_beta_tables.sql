-- ============================================================================
-- Migration: 20260206_beta_tables.sql
-- Purpose:   Create all missing tables, views, and RPC functions referenced
--            by SupabaseDataProvider.ts for the beta launch.
-- Safe:      Uses IF NOT EXISTS / CREATE OR REPLACE throughout.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. PORTFOLIO VALUES — time series of portfolio values
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.portfolio_values (
  id       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id  uuid        NOT NULL,
  at       timestamptz NOT NULL DEFAULT now(),
  value    numeric     NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_portfolio_values_user_at
  ON public.portfolio_values(user_id, at DESC);

ALTER TABLE public.portfolio_values ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'portfolio_values' AND policyname = 'portfolio_values_select_own'
  ) THEN
    CREATE POLICY portfolio_values_select_own ON public.portfolio_values
      FOR SELECT USING (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'portfolio_values' AND policyname = 'portfolio_values_insert_own'
  ) THEN
    CREATE POLICY portfolio_values_insert_own ON public.portfolio_values
      FOR INSERT WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;


-- ============================================================================
-- 2. WATCHLIST ITEMS — richer watchlist (replaces the legacy bigserial watchlist)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.watchlist_items (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid        NOT NULL,
  title        text        NOT NULL,
  category     text,
  priority     text        NOT NULL DEFAULT 'medium'
                           CHECK (priority IN ('high', 'medium', 'low')),
  owned        boolean     NOT NULL DEFAULT false,
  target_price numeric,
  currency     text        NOT NULL DEFAULT 'EUR',
  image_url    text,
  notes        text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_watchlist_items_user
  ON public.watchlist_items(user_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_items_user_created
  ON public.watchlist_items(user_id, created_at DESC);

ALTER TABLE public.watchlist_items ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'watchlist_items' AND policyname = 'watchlist_items_select_own'
  ) THEN
    CREATE POLICY watchlist_items_select_own ON public.watchlist_items
      FOR SELECT USING (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'watchlist_items' AND policyname = 'watchlist_items_insert_own'
  ) THEN
    CREATE POLICY watchlist_items_insert_own ON public.watchlist_items
      FOR INSERT WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'watchlist_items' AND policyname = 'watchlist_items_update_own'
  ) THEN
    CREATE POLICY watchlist_items_update_own ON public.watchlist_items
      FOR UPDATE USING (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'watchlist_items' AND policyname = 'watchlist_items_delete_own'
  ) THEN
    CREATE POLICY watchlist_items_delete_own ON public.watchlist_items
      FOR DELETE USING (auth.uid() = user_id);
  END IF;
END $$;

-- View: v_watchlist_items_v1  (columns match SupabaseDataProvider.ts SELECT)
CREATE OR REPLACE VIEW public.v_watchlist_items_v1 AS
SELECT
  id,
  title,
  priority,
  owned,
  target_price,
  currency,
  category,
  notes,
  created_at
FROM public.watchlist_items
WHERE user_id = auth.uid();


-- ============================================================================
-- 3. USER PUBLIC PROFILES
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.user_public_profiles (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid        NOT NULL UNIQUE,
  handle       text        UNIQUE,
  display_name text        NOT NULL DEFAULT 'Unknown',
  avatar_url   text,
  bio          text,
  location     text,
  interests    text[],
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_public_profiles_user_id
  ON public.user_public_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_public_profiles_handle
  ON public.user_public_profiles(handle)
  WHERE handle IS NOT NULL;

ALTER TABLE public.user_public_profiles ENABLE ROW LEVEL SECURITY;

-- Public read access (these are public profiles)
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'user_public_profiles' AND policyname = 'user_public_profiles_select_all'
  ) THEN
    CREATE POLICY user_public_profiles_select_all ON public.user_public_profiles
      FOR SELECT USING (true);
  END IF;
END $$;

-- Owner can update their own profile
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'user_public_profiles' AND policyname = 'user_public_profiles_update_own'
  ) THEN
    CREATE POLICY user_public_profiles_update_own ON public.user_public_profiles
      FOR UPDATE USING (auth.uid() = user_id);
  END IF;
END $$;

-- Owner can insert their own profile
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'user_public_profiles' AND policyname = 'user_public_profiles_insert_own'
  ) THEN
    CREATE POLICY user_public_profiles_insert_own ON public.user_public_profiles
      FOR INSERT WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- View: user_public_profile_v1  (enriched with collection stats)
CREATE OR REPLACE VIEW public.user_public_profile_v1 AS
SELECT
  upp.id,
  upp.user_id,
  upp.handle,
  upp.display_name,
  upp.avatar_url,
  upp.bio,
  upp.interests,
  upp.location,
  upp.created_at,
  -- Aggregate collection stats from items table
  (SELECT count(*) FROM public.items i WHERE i.user_id = upp.user_id)
    AS collection_count,
  (SELECT coalesce(sum(pp.q50), 0)
   FROM public.items i
   JOIN public.price_predictions pp ON pp.item_id = i.id
   WHERE i.user_id = upp.user_id
     AND pp.asof = (SELECT max(pp2.asof) FROM public.price_predictions pp2 WHERE pp2.item_id = i.id)
  ) AS collection_value_eur
FROM public.user_public_profiles upp;


-- ============================================================================
-- 4. ALERTS FEED VIEW (joins user_price_alerts with item data)
--    user_price_alerts table already exists from 20260202_user_price_alerts.sql
-- ============================================================================

CREATE OR REPLACE VIEW public.v_alerts_feed_v1 AS
SELECT
  upa.id,
  upa.trigger_type AS type,
  coalesce(i.title, 'Alert') AS title,
  CASE
    WHEN upa.trigger_type = 'below_threshold' THEN
      'Price dropped below ' || coalesce(upa.threshold_value::text, '?') || ' threshold'
    WHEN upa.trigger_type = 'category_trend' THEN
      coalesce(upa.category, 'Category') || ' trending ' || coalesce(upa.direction, 'up')
    WHEN upa.trigger_type = 'high_prediction' THEN
      'High prediction confidence for this item'
    ELSE
      'Alert triggered'
  END AS body,
  upa.last_triggered_at AS created_at,
  upa.item_id,
  NULL::uuid AS watchlist_item_id
FROM public.user_price_alerts upa
LEFT JOIN public.items i ON i.id = upa.item_id
WHERE upa.user_id = auth.uid()
  AND upa.last_triggered_at IS NOT NULL
ORDER BY upa.last_triggered_at DESC;


-- ============================================================================
-- 5. DM THREADS — direct message threads between users
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.dm_threads (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  requester_id  uuid        NOT NULL,
  responder_id  uuid        NOT NULL,
  status        text        NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'accepted', 'declined')),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dm_threads_requester
  ON public.dm_threads(requester_id);
CREATE INDEX IF NOT EXISTS idx_dm_threads_responder
  ON public.dm_threads(responder_id);
CREATE INDEX IF NOT EXISTS idx_dm_threads_status
  ON public.dm_threads(status);

ALTER TABLE public.dm_threads ENABLE ROW LEVEL SECURITY;

-- Both participants can see their threads
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'dm_threads' AND policyname = 'dm_threads_select_participant'
  ) THEN
    CREATE POLICY dm_threads_select_participant ON public.dm_threads
      FOR SELECT USING (auth.uid() IN (requester_id, responder_id));
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'dm_threads' AND policyname = 'dm_threads_update_participant'
  ) THEN
    CREATE POLICY dm_threads_update_participant ON public.dm_threads
      FOR UPDATE USING (auth.uid() IN (requester_id, responder_id));
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'dm_threads' AND policyname = 'dm_threads_insert_requester'
  ) THEN
    CREATE POLICY dm_threads_insert_requester ON public.dm_threads
      FOR INSERT WITH CHECK (auth.uid() = requester_id);
  END IF;
END $$;


-- ============================================================================
-- 6. CHAT MESSAGES
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.chat_messages (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id      uuid        NOT NULL REFERENCES public.dm_threads(id) ON DELETE CASCADE,
  author_user_id uuid        NOT NULL,
  text           text        NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  read_at        timestamptz
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_thread
  ON public.chat_messages(thread_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_chat_messages_author
  ON public.chat_messages(author_user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_unread
  ON public.chat_messages(thread_id, read_at)
  WHERE read_at IS NULL;

ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

-- Participants of the thread can read/write messages
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'chat_messages' AND policyname = 'chat_messages_select_participant'
  ) THEN
    CREATE POLICY chat_messages_select_participant ON public.chat_messages
      FOR SELECT USING (
        EXISTS (
          SELECT 1 FROM public.dm_threads t
          WHERE t.id = thread_id
            AND auth.uid() IN (t.requester_id, t.responder_id)
        )
      );
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'chat_messages' AND policyname = 'chat_messages_insert_participant'
  ) THEN
    CREATE POLICY chat_messages_insert_participant ON public.chat_messages
      FOR INSERT WITH CHECK (
        auth.uid() = author_user_id
        AND EXISTS (
          SELECT 1 FROM public.dm_threads t
          WHERE t.id = thread_id
            AND auth.uid() IN (t.requester_id, t.responder_id)
        )
      );
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'chat_messages' AND policyname = 'chat_messages_update_read'
  ) THEN
    CREATE POLICY chat_messages_update_read ON public.chat_messages
      FOR UPDATE USING (
        EXISTS (
          SELECT 1 FROM public.dm_threads t
          WHERE t.id = thread_id
            AND auth.uid() IN (t.requester_id, t.responder_id)
        )
      );
  END IF;
END $$;

-- View: chat_messages_v1  (the TS code reads from this name)
CREATE OR REPLACE VIEW public.chat_messages_v1 AS
SELECT
  cm.id,
  cm.thread_id,
  cm.author_user_id,
  cm.text,
  cm.created_at
FROM public.chat_messages cm
WHERE EXISTS (
  SELECT 1 FROM public.dm_threads t
  WHERE t.id = cm.thread_id
    AND auth.uid() IN (t.requester_id, t.responder_id)
);

-- View: v_chat_inbox_v1  (columns match SupabaseDataProvider.ts expectations)
CREATE OR REPLACE VIEW public.v_chat_inbox_v1 AS
SELECT
  t.id,
  -- Determine the "other" user relative to the current user
  CASE WHEN t.requester_id = auth.uid() THEN t.responder_id ELSE t.requester_id END
    AS other_user_id,
  CASE WHEN t.requester_id = auth.uid() THEN
    coalesce(pr.display_name, 'Unknown')
  ELSE
    coalesce(pq.display_name, 'Unknown')
  END AS other_user_name,
  CASE WHEN t.requester_id = auth.uid() THEN pr.handle ELSE pq.handle END
    AS other_user_handle,
  CASE WHEN t.requester_id = auth.uid() THEN pr.avatar_url ELSE pq.avatar_url END
    AS other_user_avatar_url,
  '#6b7280' AS other_user_avatar_color,
  t.status,
  last_msg.text AS last_message_preview,
  last_msg.created_at AS last_message_at,
  -- Count unread messages (messages from the other user that I haven't read)
  (
    SELECT count(*)
    FROM public.chat_messages cm2
    WHERE cm2.thread_id = t.id
      AND cm2.author_user_id != auth.uid()
      AND cm2.read_at IS NULL
  )::int AS unread_count,
  -- is_incoming = true if the other user initiated the thread
  (t.requester_id != auth.uid()) AS is_incoming
FROM public.dm_threads t
LEFT JOIN public.user_public_profiles pq ON pq.user_id = t.requester_id
LEFT JOIN public.user_public_profiles pr ON pr.user_id = t.responder_id
LEFT JOIN LATERAL (
  SELECT cm.text, cm.created_at
  FROM public.chat_messages cm
  WHERE cm.thread_id = t.id
  ORDER BY cm.created_at DESC
  LIMIT 1
) last_msg ON true
WHERE auth.uid() IN (t.requester_id, t.responder_id);


-- ============================================================================
-- 7. BUILD & PAINT PROJECTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.build_paint_projects (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid        NOT NULL,
  title         text        NOT NULL,
  category      text,
  image_url     text,
  percent_complete integer  NOT NULL DEFAULT 0 CHECK (percent_complete BETWEEN 0 AND 100),
  is_completed  boolean     NOT NULL DEFAULT false,
  status        text        NOT NULL DEFAULT 'Active',
  notes         text,
  started_at    timestamptz,
  completed_at  timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_build_paint_projects_user
  ON public.build_paint_projects(user_id);
CREATE INDEX IF NOT EXISTS idx_build_paint_projects_user_status
  ON public.build_paint_projects(user_id, status);
CREATE INDEX IF NOT EXISTS idx_build_paint_projects_updated
  ON public.build_paint_projects(user_id, updated_at DESC);

ALTER TABLE public.build_paint_projects ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'build_paint_projects' AND policyname = 'build_paint_projects_select_own'
  ) THEN
    CREATE POLICY build_paint_projects_select_own ON public.build_paint_projects
      FOR SELECT USING (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'build_paint_projects' AND policyname = 'build_paint_projects_insert_own'
  ) THEN
    CREATE POLICY build_paint_projects_insert_own ON public.build_paint_projects
      FOR INSERT WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'build_paint_projects' AND policyname = 'build_paint_projects_update_own'
  ) THEN
    CREATE POLICY build_paint_projects_update_own ON public.build_paint_projects
      FOR UPDATE USING (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'build_paint_projects' AND policyname = 'build_paint_projects_delete_own'
  ) THEN
    CREATE POLICY build_paint_projects_delete_own ON public.build_paint_projects
      FOR DELETE USING (auth.uid() = user_id);
  END IF;
END $$;

-- View: v_build_paint_projects_v1
CREATE OR REPLACE VIEW public.v_build_paint_projects_v1 AS
SELECT
  id,
  title,
  category,
  status,
  percent_complete,
  is_completed,
  notes,
  created_at,
  updated_at
FROM public.build_paint_projects
WHERE user_id = auth.uid();


-- ============================================================================
-- 8. BUILD & PAINT STEPS
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.build_paint_steps (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  uuid        NOT NULL REFERENCES public.build_paint_projects(id) ON DELETE CASCADE,
  title       text        NOT NULL,
  is_done     boolean     NOT NULL DEFAULT false,
  sort_order  integer     NOT NULL DEFAULT 0,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_build_paint_steps_project
  ON public.build_paint_steps(project_id, sort_order ASC);

ALTER TABLE public.build_paint_steps ENABLE ROW LEVEL SECURITY;

-- Owner of the parent project can CRUD steps
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'build_paint_steps' AND policyname = 'build_paint_steps_select_own'
  ) THEN
    CREATE POLICY build_paint_steps_select_own ON public.build_paint_steps
      FOR SELECT USING (
        EXISTS (
          SELECT 1 FROM public.build_paint_projects p
          WHERE p.id = project_id AND p.user_id = auth.uid()
        )
      );
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'build_paint_steps' AND policyname = 'build_paint_steps_insert_own'
  ) THEN
    CREATE POLICY build_paint_steps_insert_own ON public.build_paint_steps
      FOR INSERT WITH CHECK (
        EXISTS (
          SELECT 1 FROM public.build_paint_projects p
          WHERE p.id = project_id AND p.user_id = auth.uid()
        )
      );
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'build_paint_steps' AND policyname = 'build_paint_steps_update_own'
  ) THEN
    CREATE POLICY build_paint_steps_update_own ON public.build_paint_steps
      FOR UPDATE USING (
        EXISTS (
          SELECT 1 FROM public.build_paint_projects p
          WHERE p.id = project_id AND p.user_id = auth.uid()
        )
      );
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'build_paint_steps' AND policyname = 'build_paint_steps_delete_own'
  ) THEN
    CREATE POLICY build_paint_steps_delete_own ON public.build_paint_steps
      FOR DELETE USING (
        EXISTS (
          SELECT 1 FROM public.build_paint_projects p
          WHERE p.id = project_id AND p.user_id = auth.uid()
        )
      );
  END IF;
END $$;

-- View: v_build_paint_project_steps_v1
CREATE OR REPLACE VIEW public.v_build_paint_project_steps_v1 AS
SELECT
  s.id,
  s.project_id,
  s.title,
  s.is_done,
  s.sort_order,
  s.created_at
FROM public.build_paint_steps s
JOIN public.build_paint_projects p ON p.id = s.project_id
WHERE p.user_id = auth.uid();


-- ============================================================================
-- 9. BUILD & PAINT NOTES
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.build_paint_notes (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  uuid        NOT NULL REFERENCES public.build_paint_projects(id) ON DELETE CASCADE,
  body        text        NOT NULL,
  image_url   text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_build_paint_notes_project
  ON public.build_paint_notes(project_id, created_at DESC);

ALTER TABLE public.build_paint_notes ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'build_paint_notes' AND policyname = 'build_paint_notes_select_own'
  ) THEN
    CREATE POLICY build_paint_notes_select_own ON public.build_paint_notes
      FOR SELECT USING (
        EXISTS (
          SELECT 1 FROM public.build_paint_projects p
          WHERE p.id = project_id AND p.user_id = auth.uid()
        )
      );
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'build_paint_notes' AND policyname = 'build_paint_notes_insert_own'
  ) THEN
    CREATE POLICY build_paint_notes_insert_own ON public.build_paint_notes
      FOR INSERT WITH CHECK (
        EXISTS (
          SELECT 1 FROM public.build_paint_projects p
          WHERE p.id = project_id AND p.user_id = auth.uid()
        )
      );
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'build_paint_notes' AND policyname = 'build_paint_notes_delete_own'
  ) THEN
    CREATE POLICY build_paint_notes_delete_own ON public.build_paint_notes
      FOR DELETE USING (
        EXISTS (
          SELECT 1 FROM public.build_paint_projects p
          WHERE p.id = project_id AND p.user_id = auth.uid()
        )
      );
  END IF;
END $$;

-- View: v_build_paint_project_notes_v1
CREATE OR REPLACE VIEW public.v_build_paint_project_notes_v1 AS
SELECT
  n.id,
  n.project_id,
  n.body,
  n.created_at
FROM public.build_paint_notes n
JOIN public.build_paint_projects p ON p.id = n.project_id
WHERE p.user_id = auth.uid();


-- ============================================================================
-- 10. BUILD & PAINT SESSIONS — time tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.build_paint_sessions (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id       uuid        NOT NULL REFERENCES public.build_paint_projects(id) ON DELETE CASCADE,
  user_id          uuid        NOT NULL,
  minutes          integer     NOT NULL DEFAULT 0,
  started_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_build_paint_sessions_project
  ON public.build_paint_sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_build_paint_sessions_user
  ON public.build_paint_sessions(user_id);

ALTER TABLE public.build_paint_sessions ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'build_paint_sessions' AND policyname = 'build_paint_sessions_select_own'
  ) THEN
    CREATE POLICY build_paint_sessions_select_own ON public.build_paint_sessions
      FOR SELECT USING (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'build_paint_sessions' AND policyname = 'build_paint_sessions_insert_own'
  ) THEN
    CREATE POLICY build_paint_sessions_insert_own ON public.build_paint_sessions
      FOR INSERT WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;


-- ============================================================================
-- 11. TWITCH CREATORS — tracked Twitch creators
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.twitch_creators (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  channel_name    text        NOT NULL,
  category        text,
  last_live_at    timestamptz,
  follower_count  integer     DEFAULT 0,
  is_live         boolean     NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_twitch_creators_channel
  ON public.twitch_creators(channel_name);
CREATE INDEX IF NOT EXISTS idx_twitch_creators_is_live
  ON public.twitch_creators(is_live)
  WHERE is_live = true;

ALTER TABLE public.twitch_creators ENABLE ROW LEVEL SECURITY;

-- Public read for twitch creators (shared community data)
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'twitch_creators' AND policyname = 'twitch_creators_select_all'
  ) THEN
    CREATE POLICY twitch_creators_select_all ON public.twitch_creators
      FOR SELECT USING (true);
  END IF;
END $$;


-- ============================================================================
-- 12. ITEMS TABLE — add user_photo_url column if not exists
-- ============================================================================

ALTER TABLE public.items ADD COLUMN IF NOT EXISTS user_photo_url text;


-- ============================================================================
-- RPC FUNCTIONS
-- ============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_add_watchlist_item_v1
-- Params match SupabaseDataProvider.ts: p_title, p_category, p_target_price,
--   p_notes, p_priority
-- Returns the inserted row as JSON.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_add_watchlist_item_v1(
  p_title        text,
  p_category     text     DEFAULT NULL,
  p_target_price numeric  DEFAULT NULL,
  p_notes        text     DEFAULT NULL,
  p_priority     text     DEFAULT 'medium'
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid := auth.uid();
  v_id      uuid;
  v_result  jsonb;
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  INSERT INTO public.watchlist_items (user_id, title, category, target_price, notes, priority)
  VALUES (v_user_id, p_title, p_category, p_target_price, p_notes,
          CASE WHEN p_priority IN ('high','medium','low') THEN p_priority ELSE 'medium' END)
  RETURNING id INTO v_id;

  SELECT jsonb_build_object(
    'id', wi.id,
    'title', wi.title,
    'priority', wi.priority,
    'owned', wi.owned,
    'target_price', wi.target_price,
    'currency', wi.currency,
    'category', wi.category,
    'notes', wi.notes,
    'created_at', wi.created_at
  ) INTO v_result
  FROM public.watchlist_items wi
  WHERE wi.id = v_id;

  RETURN v_result;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_remove_watchlist_item_v1
-- Params match SupabaseDataProvider.ts: p_id
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_remove_watchlist_item_v1(
  p_id uuid
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid := auth.uid();
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  DELETE FROM public.watchlist_items
  WHERE id = p_id AND user_id = v_user_id;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_create_item_v1
-- Params match SupabaseDataProvider.ts: p_title, p_category, p_image_url,
--   p_attributes (jsonb), p_notes
-- Returns the created item row as JSON.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_create_item_v1(
  p_title      text,
  p_category   text,
  p_image_url  text     DEFAULT NULL,
  p_attributes jsonb    DEFAULT '{}'::jsonb,
  p_notes      text     DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid := auth.uid();
  v_id      uuid;
  v_images  jsonb;
  v_result  jsonb;
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  -- Build images array from image_url
  IF p_image_url IS NOT NULL AND p_image_url != '' THEN
    v_images := jsonb_build_array(p_image_url);
  ELSE
    v_images := '[]'::jsonb;
  END IF;

  INSERT INTO public.items (
    user_id, title, category, images, attributes_json,
    user_photo_url, created_at, updated_at
  )
  VALUES (
    v_user_id, p_title, p_category, v_images,
    coalesce(p_attributes, '{}'::jsonb),
    p_image_url, now(), now()
  )
  RETURNING id INTO v_id;

  -- If notes provided, we could store in attributes_json or a notes column
  -- For now, merge into attributes_json
  IF p_notes IS NOT NULL THEN
    UPDATE public.items
    SET attributes_json = attributes_json || jsonb_build_object('notes', p_notes)
    WHERE id = v_id;
  END IF;

  SELECT jsonb_build_object(
    'id', i.id,
    'title', i.title,
    'category', i.category,
    'images', i.images,
    'created_at', i.created_at,
    'updated_at', i.updated_at
  ) INTO v_result
  FROM public.items i
  WHERE i.id = v_id;

  RETURN v_result;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_convert_watchlist_to_item_v1
-- Params match SupabaseDataProvider.ts: p_watchlist_item_id, p_actual_price,
--   p_notes
-- Creates an item from a watchlist entry, removes it from watchlist, returns
-- the new item.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_convert_watchlist_to_item_v1(
  p_watchlist_item_id uuid,
  p_actual_price      numeric DEFAULT NULL,
  p_notes             text    DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id  uuid := auth.uid();
  v_wl       record;
  v_item_id  uuid;
  v_images   jsonb;
  v_result   jsonb;
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  -- Fetch watchlist item (must belong to user)
  SELECT * INTO v_wl
  FROM public.watchlist_items
  WHERE id = p_watchlist_item_id AND user_id = v_user_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Watchlist item not found or not owned by user';
  END IF;

  -- Build images
  IF v_wl.image_url IS NOT NULL THEN
    v_images := jsonb_build_array(v_wl.image_url);
  ELSE
    v_images := '[]'::jsonb;
  END IF;

  -- Create the item
  INSERT INTO public.items (user_id, title, category, images, user_photo_url, created_at, updated_at)
  VALUES (
    v_user_id,
    v_wl.title,
    coalesce(v_wl.category, 'Other'),
    v_images,
    v_wl.image_url,
    now(),
    now()
  )
  RETURNING id INTO v_item_id;

  -- Mark watchlist item as owned (soft-convert) or delete
  DELETE FROM public.watchlist_items
  WHERE id = p_watchlist_item_id AND user_id = v_user_id;

  -- Build result
  v_result := jsonb_build_object(
    'id', v_item_id,
    'title', v_wl.title,
    'name', v_wl.title,
    'category', coalesce(v_wl.category, 'Other'),
    'price', coalesce(p_actual_price, v_wl.target_price, 0),
    'image_url', v_wl.image_url,
    'updated_at', now()
  );

  RETURN v_result;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_request_dm_v1
-- Params match SupabaseDataProvider.ts: p_to_user_id, p_message
-- Creates or re-opens a DM thread and sends initial message.
-- Returns JSON with thread_id.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_request_dm_v1(
  p_to_user_id uuid,
  p_message    text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id   uuid := auth.uid();
  v_thread_id uuid;
  v_msg_id    uuid;
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  IF v_user_id = p_to_user_id THEN
    RAISE EXCEPTION 'Cannot send DM to yourself';
  END IF;

  -- Check if a thread already exists between these two users
  SELECT id INTO v_thread_id
  FROM public.dm_threads
  WHERE (requester_id = v_user_id AND responder_id = p_to_user_id)
     OR (requester_id = p_to_user_id AND responder_id = v_user_id)
  LIMIT 1;

  IF v_thread_id IS NULL THEN
    -- Create new thread
    INSERT INTO public.dm_threads (requester_id, responder_id, status)
    VALUES (v_user_id, p_to_user_id, 'pending')
    RETURNING id INTO v_thread_id;
  END IF;

  -- Send the initial message if provided
  IF p_message IS NOT NULL AND p_message != '' THEN
    INSERT INTO public.chat_messages (thread_id, author_user_id, text)
    VALUES (v_thread_id, v_user_id, p_message)
    RETURNING id INTO v_msg_id;

    -- Update thread timestamp
    UPDATE public.dm_threads SET updated_at = now() WHERE id = v_thread_id;
  END IF;

  RETURN jsonb_build_object('thread_id', v_thread_id);
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_decide_dm_request_v1
-- Params match SupabaseDataProvider.ts: p_thread_id, p_accept (boolean)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_decide_dm_request_v1(
  p_thread_id uuid,
  p_accept    boolean
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid := auth.uid();
  v_thread  record;
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  -- Fetch thread (must be the responder to accept/decline)
  SELECT * INTO v_thread
  FROM public.dm_threads
  WHERE id = p_thread_id AND responder_id = v_user_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Thread not found or you are not the responder';
  END IF;

  -- Update status
  UPDATE public.dm_threads
  SET
    status = CASE WHEN p_accept THEN 'accepted' ELSE 'declined' END,
    updated_at = now()
  WHERE id = p_thread_id;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_mark_thread_read_v1
-- Params match SupabaseDataProvider.ts: p_thread_id
-- Marks all unread messages from the other user as read.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_mark_thread_read_v1(
  p_thread_id uuid
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid := auth.uid();
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  -- Verify user is a participant
  IF NOT EXISTS (
    SELECT 1 FROM public.dm_threads
    WHERE id = p_thread_id
      AND auth.uid() IN (requester_id, responder_id)
  ) THEN
    RAISE EXCEPTION 'Thread not found or not a participant';
  END IF;

  -- Mark all messages from the other user as read
  UPDATE public.chat_messages
  SET read_at = now()
  WHERE thread_id = p_thread_id
    AND author_user_id != v_user_id
    AND read_at IS NULL;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_send_message_v1
-- Params match SupabaseDataProvider.ts: p_thread_id, p_text
-- Returns the created message row as JSON.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_send_message_v1(
  p_thread_id uuid,
  p_text      text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid := auth.uid();
  v_thread  record;
  v_msg_id  uuid;
  v_result  jsonb;
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  -- Verify user is a participant and thread is accepted
  SELECT * INTO v_thread
  FROM public.dm_threads
  WHERE id = p_thread_id
    AND v_user_id IN (requester_id, responder_id);

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Thread not found or not a participant';
  END IF;

  IF v_thread.status = 'declined' THEN
    RAISE EXCEPTION 'Thread has been declined';
  END IF;

  -- Insert message
  INSERT INTO public.chat_messages (thread_id, author_user_id, text)
  VALUES (p_thread_id, v_user_id, p_text)
  RETURNING id INTO v_msg_id;

  -- Update thread timestamp
  UPDATE public.dm_threads SET updated_at = now() WHERE id = p_thread_id;

  -- Return message
  SELECT jsonb_build_object(
    'id', cm.id,
    'thread_id', cm.thread_id,
    'author_user_id', cm.author_user_id,
    'text', cm.text,
    'created_at', cm.created_at
  ) INTO v_result
  FROM public.chat_messages cm
  WHERE cm.id = v_msg_id;

  RETURN v_result;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_create_build_paint_project_v1
-- Params match SupabaseDataProvider.ts: p_title, p_category
-- Returns the created project row as JSON.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_create_build_paint_project_v1(
  p_title    text,
  p_category text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid := auth.uid();
  v_id      uuid;
  v_result  jsonb;
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  INSERT INTO public.build_paint_projects (user_id, title, category, status, started_at)
  VALUES (v_user_id, p_title, p_category, 'Active', now())
  RETURNING id INTO v_id;

  SELECT jsonb_build_object(
    'id', bp.id,
    'title', bp.title,
    'category', bp.category,
    'status', bp.status,
    'percent_complete', bp.percent_complete,
    'is_completed', bp.is_completed,
    'notes', bp.notes,
    'created_at', bp.created_at,
    'updated_at', bp.updated_at
  ) INTO v_result
  FROM public.build_paint_projects bp
  WHERE bp.id = v_id;

  RETURN v_result;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_set_build_paint_progress_v1
-- Params match SupabaseDataProvider.ts: p_project_id, p_percent, p_status
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_set_build_paint_progress_v1(
  p_project_id uuid,
  p_percent    integer,
  p_status     text DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid := auth.uid();
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  UPDATE public.build_paint_projects
  SET
    percent_complete = LEAST(GREATEST(p_percent, 0), 100),
    status = coalesce(p_status, status),
    updated_at = now()
  WHERE id = p_project_id AND user_id = v_user_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Project not found or not owned by user';
  END IF;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_mark_build_paint_project_complete_v1
-- Params match SupabaseDataProvider.ts: p_project_id, p_is_completed
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_mark_build_paint_project_complete_v1(
  p_project_id   uuid,
  p_is_completed boolean
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid := auth.uid();
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  UPDATE public.build_paint_projects
  SET
    is_completed = p_is_completed,
    percent_complete = CASE WHEN p_is_completed THEN 100 ELSE percent_complete END,
    status = CASE WHEN p_is_completed THEN 'Completed' ELSE 'Active' END,
    completed_at = CASE WHEN p_is_completed THEN now() ELSE NULL END,
    updated_at = now()
  WHERE id = p_project_id AND user_id = v_user_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Project not found or not owned by user';
  END IF;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_add_build_paint_step_v1
-- Params match SupabaseDataProvider.ts: p_project_id, p_title
-- Returns the created step row as JSON.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_add_build_paint_step_v1(
  p_project_id uuid,
  p_title      text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id    uuid := auth.uid();
  v_id         uuid;
  v_sort_order integer;
  v_result     jsonb;
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  -- Verify project ownership
  IF NOT EXISTS (
    SELECT 1 FROM public.build_paint_projects
    WHERE id = p_project_id AND user_id = v_user_id
  ) THEN
    RAISE EXCEPTION 'Project not found or not owned by user';
  END IF;

  -- Get next sort_order
  SELECT coalesce(max(sort_order), 0) + 1 INTO v_sort_order
  FROM public.build_paint_steps
  WHERE project_id = p_project_id;

  INSERT INTO public.build_paint_steps (project_id, title, sort_order)
  VALUES (p_project_id, p_title, v_sort_order)
  RETURNING id INTO v_id;

  -- Update project timestamp
  UPDATE public.build_paint_projects SET updated_at = now() WHERE id = p_project_id;

  SELECT jsonb_build_object(
    'id', s.id,
    'project_id', s.project_id,
    'title', s.title,
    'is_done', s.is_done,
    'sort_order', s.sort_order,
    'created_at', s.created_at
  ) INTO v_result
  FROM public.build_paint_steps s
  WHERE s.id = v_id;

  RETURN v_result;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_toggle_build_paint_step_v1
-- Params match SupabaseDataProvider.ts: p_step_id, p_is_done
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_toggle_build_paint_step_v1(
  p_step_id uuid,
  p_is_done boolean
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id    uuid := auth.uid();
  v_project_id uuid;
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  -- Get project_id and verify ownership
  SELECT s.project_id INTO v_project_id
  FROM public.build_paint_steps s
  JOIN public.build_paint_projects p ON p.id = s.project_id
  WHERE s.id = p_step_id AND p.user_id = v_user_id;

  IF v_project_id IS NULL THEN
    RAISE EXCEPTION 'Step not found or not owned by user';
  END IF;

  UPDATE public.build_paint_steps
  SET is_done = p_is_done
  WHERE id = p_step_id;

  -- Update project timestamp
  UPDATE public.build_paint_projects SET updated_at = now() WHERE id = v_project_id;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_add_build_paint_note_v1
-- Params match SupabaseDataProvider.ts: p_project_id, p_body
-- Returns the created note row as JSON.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_add_build_paint_note_v1(
  p_project_id uuid,
  p_body       text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid := auth.uid();
  v_id      uuid;
  v_result  jsonb;
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  -- Verify project ownership
  IF NOT EXISTS (
    SELECT 1 FROM public.build_paint_projects
    WHERE id = p_project_id AND user_id = v_user_id
  ) THEN
    RAISE EXCEPTION 'Project not found or not owned by user';
  END IF;

  INSERT INTO public.build_paint_notes (project_id, body)
  VALUES (p_project_id, p_body)
  RETURNING id INTO v_id;

  -- Update project timestamp
  UPDATE public.build_paint_projects SET updated_at = now() WHERE id = p_project_id;

  SELECT jsonb_build_object(
    'id', n.id,
    'project_id', n.project_id,
    'body', n.body,
    'created_at', n.created_at
  ) INTO v_result
  FROM public.build_paint_notes n
  WHERE n.id = v_id;

  RETURN v_result;
END;
$$;


-- ============================================================================
-- GRANT EXECUTE ON ALL RPC FUNCTIONS
-- ============================================================================

GRANT EXECUTE ON FUNCTION public.rpc_add_watchlist_item_v1(text, text, numeric, text, text)              TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_remove_watchlist_item_v1(uuid)                                      TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_create_item_v1(text, text, text, jsonb, text)                       TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_convert_watchlist_to_item_v1(uuid, numeric, text)                   TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_request_dm_v1(uuid, text)                                           TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_decide_dm_request_v1(uuid, boolean)                                 TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_mark_thread_read_v1(uuid)                                           TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_send_message_v1(uuid, text)                                         TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_create_build_paint_project_v1(text, text)                           TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_set_build_paint_progress_v1(uuid, integer, text)                    TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_mark_build_paint_project_complete_v1(uuid, boolean)                 TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_add_build_paint_step_v1(uuid, text)                                TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_toggle_build_paint_step_v1(uuid, boolean)                           TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_add_build_paint_note_v1(uuid, text)                                TO authenticated;


COMMIT;
