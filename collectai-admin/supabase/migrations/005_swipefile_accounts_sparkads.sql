-- Swipe File, Multi-Account Tracking, Spark Ads Boost Tracking

-- ─── Swipe File / Inspiration Library ────────────────────────────────────────

CREATE TABLE ugc_swipe_file (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  url             TEXT NOT NULL,                -- TikTok/Instagram URL
  platform        TEXT DEFAULT 'tiktok',        -- tiktok, instagram, youtube
  hook_text       TEXT,                         -- The hook used
  hook_type       TEXT,                         -- question, POV, statement, etc.
  format          TEXT,                         -- tutorial, transition, etc.
  niche           TEXT,                         -- crochet, craft, wellness, etc.
  why_it_works    TEXT,                         -- Notes on why this is worth saving
  tags            TEXT[] DEFAULT '{}',          -- Freeform tags for filtering
  estimated_views INT DEFAULT 0,
  saved_by        TEXT,                         -- Who saved it (admin name)
  is_competitor   BOOLEAN DEFAULT FALSE,        -- From a competitor?
  source_account  TEXT,                         -- The TikTok account that posted it
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_swipe_hook_type ON ugc_swipe_file(hook_type);
CREATE INDEX idx_swipe_format ON ugc_swipe_file(format);
CREATE INDEX idx_swipe_tags ON ugc_swipe_file USING GIN(tags);

-- ─── TikTok Account Tracking ────────────────────────────────────────────────

CREATE TABLE ugc_accounts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  handle          TEXT UNIQUE NOT NULL,         -- @sammysam.eu, @sammysam.de, etc.
  platform        TEXT DEFAULT 'tiktok',
  language        TEXT NOT NULL,                -- Primary language
  description     TEXT,
  followers       INT DEFAULT 0,
  is_active       BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Spark Ads / Boost Tracking (extends ugc_videos) ────────────────────────

ALTER TABLE ugc_videos
  ADD COLUMN IF NOT EXISTS is_boosted      BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS boost_spend_cents INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS boost_views     INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS boost_clicks    INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS boost_installs  INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS boost_start_date DATE,
  ADD COLUMN IF NOT EXISTS boost_end_date  DATE;

CREATE INDEX idx_ugc_videos_boosted ON ugc_videos(is_boosted) WHERE is_boosted = TRUE;

-- ─── RLS ─────────────────────────────────────────────────────────────────────

ALTER TABLE ugc_swipe_file ENABLE ROW LEVEL SECURITY;
ALTER TABLE ugc_accounts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "swipe_admin" ON ugc_swipe_file FOR ALL USING (true);
CREATE POLICY "accounts_admin" ON ugc_accounts FOR ALL USING (true);
