-- ═══════════════════════════════════════════════════════════════════════════
-- Video Script Pipeline — tracks Remotion video generation, rendering, and performance
-- ═══════════════════════════════════════════════════════════════════════════

-- ─── Video Scripts ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ugc_video_scripts (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  template_id   TEXT NOT NULL CHECK (template_id IN ('pull-reveal', 'whats-it-worth', 'hidden-gem', 'market-alert', 'collection-flex')),
  composition_id TEXT NOT NULL,
  niche_id      TEXT NOT NULL,
  niche_label   TEXT NOT NULL,
  language      TEXT NOT NULL DEFAULT 'EN',
  hook_text     TEXT NOT NULL,
  hook_id       TEXT,                        -- References hook library for learning
  props         JSONB NOT NULL DEFAULT '{}', -- Full Remotion input props
  status        TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'rendering', 'rendered', 'posted', 'tracking')),
  estimated_cost NUMERIC(6,4) NOT NULL DEFAULT 0.03,

  -- Rendering
  render_id     TEXT,                        -- Lambda render ID
  render_url    TEXT,                        -- S3 URL of rendered video
  video_url     TEXT,                        -- Posted video URL (TikTok/IG)

  -- Performance (populated by TikTok metrics pull)
  views_2h      INTEGER,
  views_12h     INTEGER,
  views_24h     INTEGER,
  views_total   INTEGER,
  retention_3s  NUMERIC(4,3),                -- 0.000–1.000
  completion_rate NUMERIC(4,3),
  shares        INTEGER,
  link_clicks   INTEGER,
  installs      INTEGER,
  classification TEXT CHECK (classification IN ('hit', 'average', 'fail', 'pending')),

  -- A/B testing
  ab_group      TEXT,                        -- 'A' or 'B' or NULL
  ab_pair_id    UUID,                        -- Links to the other variant
  ab_winner     BOOLEAN,

  -- Metadata
  pod_id        TEXT,                        -- Which pod this was generated for
  creator_id    TEXT,                        -- If assigned to a specific creator
  pipeline_item_id TEXT,                     -- Link to ugc_content_pipeline
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  posted_at     TIMESTAMPTZ,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Indexes ─────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_video_scripts_status ON ugc_video_scripts(status);
CREATE INDEX IF NOT EXISTS idx_video_scripts_template ON ugc_video_scripts(template_id);
CREATE INDEX IF NOT EXISTS idx_video_scripts_niche ON ugc_video_scripts(niche_id);
CREATE INDEX IF NOT EXISTS idx_video_scripts_classification ON ugc_video_scripts(classification);
CREATE INDEX IF NOT EXISTS idx_video_scripts_ab_pair ON ugc_video_scripts(ab_pair_id) WHERE ab_pair_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_video_scripts_created ON ugc_video_scripts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_video_scripts_pod ON ugc_video_scripts(pod_id) WHERE pod_id IS NOT NULL;

-- ─── Learning Store ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ugc_video_learning (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  hook_id       TEXT NOT NULL,
  niche_id      TEXT NOT NULL,
  template_id   TEXT NOT NULL,
  score         NUMERIC(6,2) NOT NULL DEFAULT 0,
  uses          INTEGER NOT NULL DEFAULT 0,
  hits          INTEGER NOT NULL DEFAULT 0,
  avg_retention NUMERIC(4,3) NOT NULL DEFAULT 0,
  avg_views     INTEGER NOT NULL DEFAULT 0,
  trend         TEXT DEFAULT 'stable' CHECK (trend IN ('rising', 'stable', 'declining')),
  last_used     TIMESTAMPTZ,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(hook_id, niche_id, template_id)
);

CREATE INDEX IF NOT EXISTS idx_video_learning_niche ON ugc_video_learning(niche_id);
CREATE INDEX IF NOT EXISTS idx_video_learning_score ON ugc_video_learning(score DESC);

-- ─── Audio Library ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ugc_video_audio (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title         TEXT NOT NULL,
  artist        TEXT,
  s3_key        TEXT NOT NULL,               -- S3 path to audio file
  duration_ms   INTEGER NOT NULL,
  bpm           INTEGER,
  mood          TEXT NOT NULL CHECK (mood IN ('hype', 'chill', 'dramatic', 'upbeat', 'cinematic', 'lofi')),
  niche_tags    TEXT[] NOT NULL DEFAULT '{}', -- Which niches this track fits
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_video_audio_mood ON ugc_video_audio(mood) WHERE is_active = TRUE;

-- ─── TikTok Metrics Cache ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ugc_tiktok_metrics (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_script_id UUID NOT NULL REFERENCES ugc_video_scripts(id) ON DELETE CASCADE,
  tiktok_video_id TEXT NOT NULL,
  snapshot_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  views         INTEGER NOT NULL DEFAULT 0,
  likes         INTEGER NOT NULL DEFAULT 0,
  comments      INTEGER NOT NULL DEFAULT 0,
  shares        INTEGER NOT NULL DEFAULT 0,
  avg_watch_time NUMERIC(6,2),               -- seconds
  retention_3s  NUMERIC(4,3),
  completion_rate NUMERIC(4,3),
  reach         INTEGER,
  profile_views INTEGER,
  UNIQUE(video_script_id, snapshot_at)
);

CREATE INDEX IF NOT EXISTS idx_tiktok_metrics_script ON ugc_tiktok_metrics(video_script_id);
CREATE INDEX IF NOT EXISTS idx_tiktok_metrics_time ON ugc_tiktok_metrics(snapshot_at DESC);

-- ─── Updated-at trigger ──────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
  CREATE TRIGGER trg_video_scripts_updated
    BEFORE UPDATE ON ugc_video_scripts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TRIGGER trg_video_learning_updated
    BEFORE UPDATE ON ugc_video_learning
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
