-- UGC / TikTok Video Analytics
-- Tracks per-video performance for the creator content pipeline.

-- ─── Videos table ────────────────────────────────────────────────────────────

CREATE TABLE ugc_videos (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id        TEXT UNIQUE NOT NULL,        -- TikTok/platform video ID
  account_id      TEXT NOT NULL,               -- TikTok account handle
  creator_id      UUID REFERENCES creators(id),-- Links to creators table
  date_posted     DATE NOT NULL,
  niche           TEXT,                        -- e.g. "crochet", "mindfulness"
  format          TEXT,                        -- e.g. "tutorial", "POV", "transition"
  hook_text       TEXT,                        -- Opening hook text
  hook_type       TEXT,                        -- e.g. "question", "statement", "shock"
  concept_cluster TEXT,                        -- Group similar concepts
  country         TEXT,                        -- Target country

  -- Performance (updated at check intervals)
  views_2h        INT DEFAULT 0,
  views_12h       INT DEFAULT 0,
  views_24h       INT DEFAULT 0,
  views_total     INT DEFAULT 0,
  hook_retention_rate NUMERIC(5,4) DEFAULT 0,  -- viewers_3s / total_views
  avg_watch_time  NUMERIC(6,2) DEFAULT 0,      -- seconds
  completion_rate NUMERIC(5,4) DEFAULT 0,      -- full_views / total_views
  likes           INT DEFAULT 0,
  comments        INT DEFAULT 0,
  shares          INT DEFAULT 0,
  saves           INT DEFAULT 0,

  -- Business metrics
  clicks          INT DEFAULT 0,
  installs        INT DEFAULT 0,
  revenue_cents   INT DEFAULT 0,

  -- Classification (computed)
  classification  TEXT DEFAULT 'pending',      -- pending, fail, average, hit

  -- Cost tracking
  cost_cents      INT DEFAULT 0,               -- Production cost

  -- Metadata
  video_url       TEXT,
  thumbnail_url   TEXT,
  notes           TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ugc_videos_creator ON ugc_videos(creator_id);
CREATE INDEX idx_ugc_videos_date ON ugc_videos(date_posted);
CREATE INDEX idx_ugc_videos_classification ON ugc_videos(classification);
CREATE INDEX idx_ugc_videos_concept ON ugc_videos(concept_cluster);
CREATE INDEX idx_ugc_videos_account ON ugc_videos(account_id);
CREATE INDEX idx_ugc_videos_hook_type ON ugc_videos(hook_type);
CREATE INDEX idx_ugc_videos_format ON ugc_videos(format);

-- ─── Daily snapshots for time-series analysis ────────────────────────────────

CREATE TABLE ugc_daily_snapshots (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id        TEXT NOT NULL REFERENCES ugc_videos(video_id),
  snapshot_date   DATE NOT NULL,
  views           INT DEFAULT 0,
  likes           INT DEFAULT 0,
  comments        INT DEFAULT 0,
  shares          INT DEFAULT 0,
  saves           INT DEFAULT 0,
  UNIQUE(video_id, snapshot_date)
);

-- ─── RLS ─────────────────────────────────────────────────────────────────────

ALTER TABLE ugc_videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE ugc_daily_snapshots ENABLE ROW LEVEL SECURITY;

-- Admin-only access (service role or authenticated admin)
CREATE POLICY "ugc_videos_admin" ON ugc_videos FOR ALL USING (true);
CREATE POLICY "ugc_snapshots_admin" ON ugc_daily_snapshots FOR ALL USING (true);
