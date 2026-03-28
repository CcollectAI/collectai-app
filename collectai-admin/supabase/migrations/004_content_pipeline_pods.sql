-- Content Pipeline & Pod Management
-- Tracks content from idea → published and organizes creators into pods.

-- ─── Pods ────────────────────────────────────────────────────────────────────

CREATE TABLE ugc_pods (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,               -- e.g. "DE Pod", "FR Pod"
  language        TEXT NOT NULL,               -- Primary language
  description     TEXT,
  color           TEXT DEFAULT '#FF6B6B',      -- Display color
  target_videos_per_week INT DEFAULT 5,
  is_active       BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Link creators to pods (many-to-many)
CREATE TABLE ugc_pod_members (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pod_id          UUID NOT NULL REFERENCES ugc_pods(id) ON DELETE CASCADE,
  creator_id      UUID NOT NULL REFERENCES creators(id) ON DELETE CASCADE,
  role            TEXT DEFAULT 'creator',      -- creator, lead, manager
  joined_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(pod_id, creator_id)
);

-- ─── Content Pipeline ────────────────────────────────────────────────────────

CREATE TABLE ugc_content_pipeline (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title           TEXT NOT NULL,               -- Working title / concept
  description     TEXT,

  -- Assignment
  pod_id          UUID REFERENCES ugc_pods(id),
  creator_id      UUID REFERENCES creators(id),
  account_id      TEXT,                        -- Target TikTok account

  -- Content details
  hook_text       TEXT,
  hook_type       TEXT,                        -- question, POV, statement, etc.
  format          TEXT,                        -- tutorial, transition, unboxing, etc.
  concept_cluster TEXT,
  kit_slug        TEXT,                        -- Which kit featured
  niche           TEXT DEFAULT 'crochet',
  country         TEXT,

  -- Pipeline status
  status          TEXT NOT NULL DEFAULT 'idea',
  -- idea → scripted → filming → editing → ready → posted → tracking

  -- Dates
  due_date        DATE,
  posted_date     DATE,

  -- Link to video record once posted
  video_id        TEXT REFERENCES ugc_videos(video_id),

  -- Priority & notes
  priority        TEXT DEFAULT 'normal',       -- low, normal, high, urgent
  notes           TEXT,

  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pipeline_status ON ugc_content_pipeline(status);
CREATE INDEX idx_pipeline_pod ON ugc_content_pipeline(pod_id);
CREATE INDEX idx_pipeline_creator ON ugc_content_pipeline(creator_id);
CREATE INDEX idx_pipeline_due ON ugc_content_pipeline(due_date);

-- ─── RLS ─────────────────────────────────────────────────────────────────────

ALTER TABLE ugc_pods ENABLE ROW LEVEL SECURITY;
ALTER TABLE ugc_pod_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE ugc_content_pipeline ENABLE ROW LEVEL SECURITY;

CREATE POLICY "pods_admin" ON ugc_pods FOR ALL USING (true);
CREATE POLICY "pod_members_admin" ON ugc_pod_members FOR ALL USING (true);
CREATE POLICY "pipeline_admin" ON ugc_content_pipeline FOR ALL USING (true);
