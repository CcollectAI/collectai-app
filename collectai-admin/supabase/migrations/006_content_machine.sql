-- ═══════════════════════════════════════════════════════════════════════════
-- 006_content_machine.sql — Content Machine tables for CollectAI
-- Automated content idea generation, calendar, captions, batch filming
-- ═══════════════════════════════════════════════════════════════════════════

-- Content accounts (brand-owned TikTok/IG accounts with distinct purposes)
CREATE TABLE IF NOT EXISTS content_accounts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  handle          TEXT NOT NULL UNIQUE,
  display_name    TEXT NOT NULL,
  purpose         TEXT NOT NULL,
  platform        TEXT NOT NULL DEFAULT 'tiktok',
  account_type    TEXT NOT NULL DEFAULT 'brand',
  language        TEXT,
  content_focus   TEXT[],
  posting_rules   JSONB DEFAULT '{}',
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Content pillars with target weekly mix percentages
CREATE TABLE IF NOT EXISTS content_pillars (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug            TEXT NOT NULL UNIQUE,
  name            TEXT NOT NULL,
  description     TEXT,
  target_mix_pct  INT NOT NULL DEFAULT 10,
  default_cta     TEXT,
  emoji           TEXT,
  best_formats    TEXT[],
  best_presence   TEXT[],
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Collectible niches (replaces "characters" from generic brief)
CREATE TABLE IF NOT EXISTS content_niches (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug            TEXT NOT NULL UNIQUE,
  name            TEXT NOT NULL,
  category_slug   TEXT NOT NULL,
  emoji           TEXT,
  price_range     TEXT,
  audience_tags   TEXT[],
  trending_topics TEXT[],
  short_description TEXT NOT NULL,
  personality_tags TEXT[],
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- App features / products to promote
CREATE TABLE IF NOT EXISTS content_products (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug            TEXT NOT NULL UNIQUE,
  name            TEXT NOT NULL,
  category        TEXT NOT NULL,
  description     TEXT,
  tier            TEXT DEFAULT 'free',
  best_content_angles TEXT[],
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Generated content ideas with success-pattern fields
CREATE TABLE IF NOT EXISTS content_ideas (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Core
  title           TEXT NOT NULL,
  hook            TEXT NOT NULL,
  concept         TEXT NOT NULL,
  shot_list       TEXT[],
  voiceover       TEXT,
  cta             TEXT,

  -- Assignments
  pillar_id       UUID NOT NULL REFERENCES content_pillars(id),
  account_id      UUID REFERENCES content_accounts(id),
  product_id      UUID REFERENCES content_products(id),
  niche_id        UUID REFERENCES content_niches(id),

  -- Success pattern fields
  objective_type  TEXT NOT NULL DEFAULT 'awareness',
  commerce_mode   TEXT NOT NULL DEFAULT 'organic',
  presence_mode   TEXT NOT NULL DEFAULT 'hands_only',
  paid_candidate  BOOLEAN NOT NULL DEFAULT FALSE,
  affiliate_ready BOOLEAN NOT NULL DEFAULT FALSE,
  boostable_reason TEXT,

  -- TikTok SEO
  target_keyword  TEXT,
  hashtags        TEXT[],

  -- Series support
  series_id       TEXT,
  series_order    INT,

  -- Format
  format          TEXT NOT NULL DEFAULT 'tutorial',
  estimated_duration TEXT DEFAULT '15-45s',
  language_code   TEXT DEFAULT 'en',

  -- Status
  status          TEXT NOT NULL DEFAULT 'draft',
  priority        TEXT NOT NULL DEFAULT 'normal',

  -- Targets
  target_completion_rate NUMERIC(3,2),
  target_save_rate NUMERIC(3,2),

  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Weekly calendars
CREATE TABLE IF NOT EXISTS weekly_calendars (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  week_start      DATE NOT NULL,
  goal            TEXT,
  notes           TEXT,
  pillar_distribution JSONB,
  batch_film_day  DATE,
  status          TEXT NOT NULL DEFAULT 'draft',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Calendar items (idea placements on specific days)
CREATE TABLE IF NOT EXISTS calendar_items (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  calendar_id     UUID NOT NULL REFERENCES weekly_calendars(id) ON DELETE CASCADE,
  idea_id         UUID NOT NULL REFERENCES content_ideas(id),
  account_id      UUID REFERENCES content_accounts(id),
  planned_date    DATE NOT NULL,
  planned_time    TIME,
  language_code   TEXT NOT NULL DEFAULT 'en',
  status          TEXT NOT NULL DEFAULT 'planned',
  format          TEXT,
  notes           TEXT,
  sort_order      INT DEFAULT 0,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Generated captions (multilingual, organic + commerce modes)
CREATE TABLE IF NOT EXISTS generated_captions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_id         UUID NOT NULL REFERENCES content_ideas(id) ON DELETE CASCADE,
  account_id      UUID REFERENCES content_accounts(id),
  language_code   TEXT NOT NULL,
  caption         TEXT NOT NULL,
  hashtags        TEXT[],
  cta             TEXT,
  seo_keyword     TEXT,
  mode            TEXT NOT NULL DEFAULT 'organic',
  version         INT NOT NULL DEFAULT 1,
  is_approved     BOOLEAN DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(idea_id, language_code, mode, version)
);

-- Batch filming sessions
CREATE TABLE IF NOT EXISTS content_batches (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title           TEXT NOT NULL,
  batch_date      DATE NOT NULL,
  setup_type      TEXT NOT NULL DEFAULT 'mixed',
  estimated_duration_mins INT,
  actual_duration_mins INT,
  status          TEXT NOT NULL DEFAULT 'planned',
  notes           TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS content_batch_items (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id        UUID NOT NULL REFERENCES content_batches(id) ON DELETE CASCADE,
  idea_id         UUID NOT NULL REFERENCES content_ideas(id),
  shot_order      INT NOT NULL DEFAULT 0,
  setup_notes     TEXT,
  is_filmed       BOOLEAN DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Indexes ────────────────────────────────────────────────────────────────

CREATE INDEX idx_cm_ideas_pillar ON content_ideas(pillar_id);
CREATE INDEX idx_cm_ideas_account ON content_ideas(account_id);
CREATE INDEX idx_cm_ideas_status ON content_ideas(status);
CREATE INDEX idx_cm_ideas_series ON content_ideas(series_id);
CREATE INDEX idx_cm_ideas_objective ON content_ideas(objective_type);
CREATE INDEX idx_cm_ideas_format ON content_ideas(format);
CREATE INDEX idx_cm_ideas_created ON content_ideas(created_at DESC);
CREATE INDEX idx_cm_calendar_items_cal ON calendar_items(calendar_id);
CREATE INDEX idx_cm_calendar_items_date ON calendar_items(planned_date);
CREATE INDEX idx_cm_captions_idea ON generated_captions(idea_id);
CREATE INDEX idx_cm_captions_lang ON generated_captions(language_code);
CREATE INDEX idx_cm_batches_date ON content_batches(batch_date);
CREATE INDEX idx_cm_batch_items_batch ON content_batch_items(batch_id);

-- ─── Updated-at trigger ─────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION cm_update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_content_ideas_updated
  BEFORE UPDATE ON content_ideas
  FOR EACH ROW EXECUTE FUNCTION cm_update_updated_at();

-- ─── RLS (admin-only) ───────────────────────────────────────────────────────

ALTER TABLE content_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_pillars ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_niches ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_products ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_ideas ENABLE ROW LEVEL SECURITY;
ALTER TABLE weekly_calendars ENABLE ROW LEVEL SECURITY;
ALTER TABLE calendar_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_captions ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_batch_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "content_accounts_admin" ON content_accounts FOR ALL USING (true);
CREATE POLICY "content_pillars_admin" ON content_pillars FOR ALL USING (true);
CREATE POLICY "content_niches_admin" ON content_niches FOR ALL USING (true);
CREATE POLICY "content_products_admin" ON content_products FOR ALL USING (true);
CREATE POLICY "content_ideas_admin" ON content_ideas FOR ALL USING (true);
CREATE POLICY "weekly_calendars_admin" ON weekly_calendars FOR ALL USING (true);
CREATE POLICY "calendar_items_admin" ON calendar_items FOR ALL USING (true);
CREATE POLICY "generated_captions_admin" ON generated_captions FOR ALL USING (true);
CREATE POLICY "content_batches_admin" ON content_batches FOR ALL USING (true);
CREATE POLICY "content_batch_items_admin" ON content_batch_items FOR ALL USING (true);
