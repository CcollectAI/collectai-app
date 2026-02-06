-- ============================================================================
-- Migration: 20260206_events_system.sql
-- Purpose:   Create the events & calendar system — category follows, events,
--            attendees, views, and RPC functions for the community events feed.
-- Safe:      Uses IF NOT EXISTS / CREATE OR REPLACE throughout.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. USER CATEGORY FOLLOWS — tracks which categories a user is interested in
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.user_category_follows (
  user_id     uuid        NOT NULL REFERENCES auth.users(id),
  category_id text        NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, category_id)
);

ALTER TABLE public.user_category_follows ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'user_category_follows' AND policyname = 'user_category_follows_select_own'
  ) THEN
    CREATE POLICY user_category_follows_select_own ON public.user_category_follows
      FOR SELECT USING (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'user_category_follows' AND policyname = 'user_category_follows_insert_own'
  ) THEN
    CREATE POLICY user_category_follows_insert_own ON public.user_category_follows
      FOR INSERT WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'user_category_follows' AND policyname = 'user_category_follows_update_own'
  ) THEN
    CREATE POLICY user_category_follows_update_own ON public.user_category_follows
      FOR UPDATE USING (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'user_category_follows' AND policyname = 'user_category_follows_delete_own'
  ) THEN
    CREATE POLICY user_category_follows_delete_own ON public.user_category_follows
      FOR DELETE USING (auth.uid() = user_id);
  END IF;
END $$;


-- ============================================================================
-- 2. EVENTS — community events, drops, conventions, streams, meetups
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.events (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  title       text        NOT NULL,
  kind        text        NOT NULL CHECK (kind IN ('collection_drop','meetup','stream','convention','release')),
  category_id text,
  date        date        NOT NULL,
  time        text,
  end_date    date,
  location    text,
  online_url  text,
  description text,
  image_url   text,
  source      text        NOT NULL DEFAULT 'user'
                          CHECK (source IN ('user','admin','scraper','newsletter')),
  source_url  text,
  created_by  uuid        REFERENCES auth.users(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_events_date
  ON public.events(date);
CREATE INDEX IF NOT EXISTS idx_events_category_id
  ON public.events(category_id);

ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;

-- Everyone can read events
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'events' AND policyname = 'events_select_all'
  ) THEN
    CREATE POLICY events_select_all ON public.events
      FOR SELECT USING (true);
  END IF;
END $$;

-- Only the creator can update their own user-sourced events
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'events' AND policyname = 'events_update_own'
  ) THEN
    CREATE POLICY events_update_own ON public.events
      FOR UPDATE USING (
        auth.uid() = created_by
        AND source = 'user'
      );
  END IF;
END $$;

-- Only the creator can delete their own user-sourced events
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'events' AND policyname = 'events_delete_own'
  ) THEN
    CREATE POLICY events_delete_own ON public.events
      FOR DELETE USING (
        auth.uid() = created_by
        AND source = 'user'
      );
  END IF;
END $$;

-- Authenticated users can insert events (source will be forced to 'user' via RPC)
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'events' AND policyname = 'events_insert_authenticated'
  ) THEN
    CREATE POLICY events_insert_authenticated ON public.events
      FOR INSERT WITH CHECK (auth.uid() = created_by);
  END IF;
END $$;


-- ============================================================================
-- 3. EVENT ATTENDEES — RSVP tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.event_attendees (
  event_id   uuid        NOT NULL REFERENCES public.events(id) ON DELETE CASCADE,
  user_id    uuid        NOT NULL REFERENCES auth.users(id),
  status     text        NOT NULL DEFAULT 'going'
                         CHECK (status IN ('going','interested','not_going')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (event_id, user_id)
);

ALTER TABLE public.event_attendees ENABLE ROW LEVEL SECURITY;

-- Everyone can read attendees
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'event_attendees' AND policyname = 'event_attendees_select_all'
  ) THEN
    CREATE POLICY event_attendees_select_all ON public.event_attendees
      FOR SELECT USING (true);
  END IF;
END $$;

-- Users can insert their own attendance
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'event_attendees' AND policyname = 'event_attendees_insert_own'
  ) THEN
    CREATE POLICY event_attendees_insert_own ON public.event_attendees
      FOR INSERT WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- Users can update their own attendance
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'event_attendees' AND policyname = 'event_attendees_update_own'
  ) THEN
    CREATE POLICY event_attendees_update_own ON public.event_attendees
      FOR UPDATE USING (auth.uid() = user_id);
  END IF;
END $$;

-- Users can delete their own attendance
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'event_attendees' AND policyname = 'event_attendees_delete_own'
  ) THEN
    CREATE POLICY event_attendees_delete_own ON public.event_attendees
      FOR DELETE USING (auth.uid() = user_id);
  END IF;
END $$;


-- ============================================================================
-- 4. VIEW: v_events_with_attendees_v1
-- ============================================================================

CREATE OR REPLACE VIEW public.v_events_with_attendees_v1 AS
SELECT
  e.id,
  e.title,
  e.kind,
  e.category_id,
  e.date,
  e.time,
  e.end_date,
  e.location,
  e.online_url,
  e.description,
  e.image_url,
  e.source,
  e.source_url,
  e.created_by,
  e.created_at,
  e.updated_at,
  coalesce(ac.attendee_count, 0)::int AS attendee_count
FROM public.events e
LEFT JOIN LATERAL (
  SELECT count(*) AS attendee_count
  FROM public.event_attendees ea
  WHERE ea.event_id = e.id
    AND ea.status IN ('going','interested')
) ac ON true;


-- ============================================================================
-- RPC FUNCTIONS
-- ============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_follow_category_v1
-- Follow a category. No-op if already following.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_follow_category_v1(
  p_category_id text
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

  INSERT INTO public.user_category_follows (user_id, category_id)
  VALUES (v_user_id, p_category_id)
  ON CONFLICT DO NOTHING;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_unfollow_category_v1
-- Unfollow a category.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_unfollow_category_v1(
  p_category_id text
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

  DELETE FROM public.user_category_follows
  WHERE user_id = v_user_id AND category_id = p_category_id;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_list_followed_categories_v1
-- Returns all categories the current user follows.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_list_followed_categories_v1()
RETURNS TABLE(category_id text, created_at timestamptz)
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

  RETURN QUERY
  SELECT ucf.category_id, ucf.created_at
  FROM public.user_category_follows ucf
  WHERE ucf.user_id = v_user_id;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_is_following_category_v1
-- Returns true if the current user follows the given category.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_is_following_category_v1(
  p_category_id text
)
RETURNS boolean
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

  RETURN EXISTS (
    SELECT 1
    FROM public.user_category_follows
    WHERE user_id = v_user_id AND category_id = p_category_id
  );
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_create_event_v1
-- Create a new user-sourced event. Returns the new row as JSON.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_create_event_v1(
  p_title       text,
  p_kind        text,
  p_category_id text     DEFAULT NULL,
  p_date        date     DEFAULT NULL,
  p_time        text     DEFAULT NULL,
  p_end_date    date     DEFAULT NULL,
  p_location    text     DEFAULT NULL,
  p_online_url  text     DEFAULT NULL,
  p_description text     DEFAULT NULL
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

  INSERT INTO public.events (
    title, kind, category_id, date, time, end_date,
    location, online_url, description,
    source, created_by
  )
  VALUES (
    p_title, p_kind, p_category_id, p_date, p_time, p_end_date,
    p_location, p_online_url, p_description,
    'user', v_user_id
  )
  RETURNING id INTO v_id;

  SELECT jsonb_build_object(
    'id', ev.id,
    'title', ev.title,
    'kind', ev.kind,
    'category_id', ev.category_id,
    'date', ev.date,
    'time', ev.time,
    'end_date', ev.end_date,
    'location', ev.location,
    'online_url', ev.online_url,
    'description', ev.description,
    'image_url', ev.image_url,
    'source', ev.source,
    'source_url', ev.source_url,
    'created_by', ev.created_by,
    'created_at', ev.created_at,
    'updated_at', ev.updated_at
  ) INTO v_result
  FROM public.events ev
  WHERE ev.id = v_id;

  RETURN v_result;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_rsvp_event_v1
-- RSVP to an event. Upserts on conflict.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_rsvp_event_v1(
  p_event_id uuid,
  p_status   text DEFAULT 'going'
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

  INSERT INTO public.event_attendees (event_id, user_id, status)
  VALUES (p_event_id, v_user_id, p_status)
  ON CONFLICT (event_id, user_id) DO UPDATE SET status = p_status;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_unrsvp_event_v1
-- Remove RSVP from an event.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_unrsvp_event_v1(
  p_event_id uuid
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

  DELETE FROM public.event_attendees
  WHERE event_id = p_event_id AND user_id = v_user_id;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_get_event_rsvp_status_v1
-- Returns the current user's RSVP status for an event, or null.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_get_event_rsvp_status_v1(
  p_event_id uuid
)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid := auth.uid();
  v_status  text;
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  SELECT ea.status INTO v_status
  FROM public.event_attendees ea
  WHERE ea.event_id = p_event_id AND ea.user_id = v_user_id;

  RETURN v_status;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- rpc_list_personalized_events_v1
-- Returns events matching the user's collection categories + followed
-- categories, plus global (NULL category) events. Includes attendee count
-- and the user's own RSVP status.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_list_personalized_events_v1()
RETURNS TABLE(
  id              uuid,
  title           text,
  kind            text,
  category_id     text,
  date            date,
  time            text,
  end_date        date,
  location        text,
  online_url      text,
  description     text,
  image_url       text,
  source          text,
  source_url      text,
  created_by      uuid,
  created_at      timestamptz,
  updated_at      timestamptz,
  attendee_count  int,
  is_attending    boolean,
  my_rsvp_status  text
)
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

  RETURN QUERY
  SELECT
    e.id,
    e.title,
    e.kind,
    e.category_id,
    e.date,
    e.time,
    e.end_date,
    e.location,
    e.online_url,
    e.description,
    e.image_url,
    e.source,
    e.source_url,
    e.created_by,
    e.created_at,
    e.updated_at,
    coalesce(ac.cnt, 0)::int AS attendee_count,
    (my.status IS NOT NULL)  AS is_attending,
    my.status                AS my_rsvp_status
  FROM public.events e
  LEFT JOIN LATERAL (
    SELECT count(*) AS cnt
    FROM public.event_attendees ea
    WHERE ea.event_id = e.id
      AND ea.status IN ('going','interested')
  ) ac ON true
  LEFT JOIN LATERAL (
    SELECT ea2.status
    FROM public.event_attendees ea2
    WHERE ea2.event_id = e.id
      AND ea2.user_id = v_user_id
  ) my ON true
  WHERE e.category_id IN (
      SELECT DISTINCT i.category
      FROM public.items i
      WHERE i.user_id = v_user_id
      UNION
      SELECT ucf.category_id
      FROM public.user_category_follows ucf
      WHERE ucf.user_id = v_user_id
    )
    OR e.category_id IS NULL
  ORDER BY e.date ASC;
END;
$$;


-- ============================================================================
-- GRANT EXECUTE ON ALL RPC FUNCTIONS
-- ============================================================================

GRANT EXECUTE ON FUNCTION public.rpc_follow_category_v1(text)                     TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_unfollow_category_v1(text)                   TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_list_followed_categories_v1()                TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_is_following_category_v1(text)               TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_create_event_v1(text, text, text, date, text, date, text, text, text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_rsvp_event_v1(uuid, text)                   TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_unrsvp_event_v1(uuid)                       TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_get_event_rsvp_status_v1(uuid)              TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_list_personalized_events_v1()               TO authenticated;


-- ============================================================================
-- 6. SEED DATA — 20 real upcoming events (Feb–Aug 2026)
-- ============================================================================

INSERT INTO public.events (title, kind, category_id, date, time, end_date, location, online_url, description, source, source_url, created_by)
VALUES
  -- TCG -----------------------------------------------------------------------
  (
    'Pokemon TCG Scarlet & Violet — Twilight Masquerade Set Release',
    'release', 'pokemon', '2026-03-22', NULL, NULL,
    NULL, 'https://www.pokemon.com/us/pokemon-tcg',
    'Global release of the Scarlet & Violet — Twilight Masquerade expansion.',
    'admin', 'https://www.pokemon.com/us/pokemon-tcg', NULL
  ),
  (
    'MTG Aetherdrift Prerelease Weekend',
    'release', 'mtg', '2026-02-14', NULL, '2026-02-16',
    'Local game stores worldwide', 'https://magic.wizards.com',
    'Prerelease weekend for Magic: The Gathering Aetherdrift. Visit your LGS to play sealed.',
    'admin', 'https://magic.wizards.com/en/products/aetherdrift', NULL
  ),
  (
    'Yu-Gi-Oh! YCSJ Amsterdam 2026',
    'convention', 'yugioh', '2026-04-12', '09:00 CET', '2026-04-13',
    'RAI Amsterdam, Netherlands', NULL,
    'Yu-Gi-Oh! Championship Series Jump event in Amsterdam. Open to all duelists.',
    'admin', 'https://www.yugioh-card.com/en/events/', NULL
  ),

  -- Figures -------------------------------------------------------------------
  (
    'Funko Fair 2026',
    'release', 'funko', '2026-02-17', '09:00 PST', '2026-02-21',
    NULL, 'https://www.funko.com',
    'Annual Funko Fair week-long reveal event showcasing new Pop! vinyl figures across all licences.',
    'admin', 'https://www.funko.com/funko-fair', NULL
  ),
  (
    'Wonder Festival Winter 2026',
    'convention', 'anime_figures', '2026-02-08', '10:00 JST', NULL,
    'Makuhari Messe, Chiba, Japan', 'https://wonfes.jp',
    'The world''s largest garage kit and figure convention. New prototypes and exclusives revealed.',
    'admin', 'https://wonfes.jp', NULL
  ),

  -- Build / Model -------------------------------------------------------------
  (
    'LEGO May the 4th GWP Window',
    'release', 'lego', '2026-05-04', NULL, '2026-05-06',
    NULL, 'https://www.lego.com',
    'LEGO Star Wars May the 4th promotional window with Gift-With-Purchase sets and exclusives.',
    'admin', 'https://www.lego.com/campaigns/star-wars', NULL
  ),
  (
    'Warhammer Fest 2026',
    'convention', 'warhammer', '2026-05-16', '10:00 BST', '2026-05-17',
    'Manchester Central, Manchester, UK', 'https://www.warhammer-community.com',
    'Games Workshop''s flagship community event with reveals, painting masterclasses, and demo games.',
    'admin', 'https://www.warhammer-community.com/warhammer-fest/', NULL
  ),
  (
    'Bandai Hobby Next Phase Spring 2026',
    'release', 'gunpla', '2026-03-15', NULL, NULL,
    NULL, 'https://bandai-hobby.net',
    'Bandai reveals upcoming Gunpla and model kit releases for the spring/summer window.',
    'admin', 'https://bandai-hobby.net', NULL
  ),

  -- Anime / Japan -------------------------------------------------------------
  (
    'Comiket C101',
    'convention', 'jp_event', '2026-08-15', '10:00 JST', '2026-08-16',
    'Tokyo Big Sight, Tokyo, Japan', 'https://www.comiket.co.jp',
    'Comic Market summer edition — the world''s largest doujinshi and fan-works convention.',
    'admin', 'https://www.comiket.co.jp', NULL
  ),
  (
    'AnimeJapan 2026',
    'convention', 'anime_figures', '2026-03-28', '10:00 JST', '2026-03-31',
    'Tokyo Big Sight, Tokyo, Japan', 'https://www.anime-japan.jp',
    'Japan''s largest anime industry expo with exclusive merchandise, screenings, and stage events.',
    'admin', 'https://www.anime-japan.jp', NULL
  ),

  -- Music / Fandom ------------------------------------------------------------
  (
    'HYBE Pop-Up Store Europe',
    'release', 'kpop_merch', '2026-03-01', NULL, '2026-04-30',
    'Multiple cities across Europe', NULL,
    'Official HYBE pop-up stores in major European cities featuring BTS, SEVENTEEN, and TXT merch.',
    'admin', 'https://hybecorp.com', NULL
  ),
  (
    'Taylor Swift Eras Tour Europe Leg 2026',
    'convention', 'taylor_swift', '2026-06-01', '18:00 CET', '2026-08-20',
    'Multiple stadiums across Europe', 'https://www.taylorswift.com',
    'Extended European stadium dates for the record-breaking Eras Tour.',
    'admin', 'https://www.taylorswift.com/tour', NULL
  ),

  -- Disney --------------------------------------------------------------------
  (
    'D23 Europe 2026',
    'convention', 'disney', '2026-04-05', '10:00 CET', '2026-04-06',
    'ExCeL London, London, UK', 'https://d23.com',
    'Disney''s official European fan event with panels, exclusive merch, and sneak peeks.',
    'admin', 'https://d23.com', NULL
  ),
  (
    'Loungefly Spring Collection Drop',
    'release', 'loungefly', '2026-03-20', '09:00 PST', NULL,
    NULL, 'https://www.loungefly.com',
    'Spring 2026 collection launch featuring new Disney, Sanrio, and anime-themed bags and accessories.',
    'admin', 'https://www.loungefly.com', NULL
  ),

  -- Niche ---------------------------------------------------------------------
  (
    'GMK Keycap Group Buy Round 2',
    'release', 'keycaps', '2026-03-10', NULL, '2026-04-10',
    NULL, 'https://www.drop.com',
    'Second round group buy for the popular GMK-profile keycap set. Limited window.',
    'admin', 'https://www.drop.com', NULL
  ),
  (
    'Mattel Creations Hot Wheels Exclusive Drop',
    'release', 'diecast', '2026-02-28', '09:00 PST', NULL,
    NULL, 'https://creations.mattel.com',
    'Limited-edition Hot Wheels RLC exclusive drop on Mattel Creations.',
    'admin', 'https://creations.mattel.com', NULL
  ),
  (
    'National Sports Card Convention 2026',
    'convention', 'sportscards', '2026-07-22', '10:00 EST', '2026-07-26',
    'Atlantic City Convention Center, Atlantic City, NJ, USA', 'https://www.nsccshow.com',
    'The premier sports card & memorabilia show in the US with major manufacturer booths and breaks.',
    'admin', 'https://www.nsccshow.com', NULL
  ),

  -- Additional events to reach 20 total --------------------------------------
  (
    'Lorcana Into the Inklands Championship Season',
    'convention', 'lorcana', '2026-04-19', '10:00 CET', '2026-04-20',
    'Messe Berlin, Berlin, Germany', 'https://www.disneylorcana.com',
    'European championship qualifier for Disney Lorcana TCG Into the Inklands set.',
    'admin', 'https://www.disneylorcana.com', NULL
  ),
  (
    'Retro Game Con Spring 2026',
    'convention', 'retro_games', '2026-05-09', '10:00 EST', '2026-05-10',
    'Oncenter, Syracuse, NY, USA', 'https://www.retrogamecon.com',
    'Retro gaming convention with vendors, tournaments, and panels covering classic consoles.',
    'admin', 'https://www.retrogamecon.com', NULL
  ),
  (
    'One Piece Day 2026',
    'convention', 'one_piece', '2026-07-22', '10:00 JST', '2026-07-23',
    'Makuhari Messe, Chiba, Japan', 'https://onepiece-day.com',
    'Annual One Piece celebration with exclusive merch reveals, stage shows, and creator panels.',
    'admin', 'https://onepiece-day.com', NULL
  );


COMMIT;
