-- Admin dashboard persistence tables (replaces localStorage)
-- Used by: AutoBriefScheduler, PipelineAutomation, DigestScheduler

CREATE TABLE IF NOT EXISTS public.admin_content_config (
  id text PRIMARY KEY,
  config_type text NOT NULL,  -- 'brief', 'rule', 'rule_log', 'digest'
  data jsonb NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_content_config_type
  ON public.admin_content_config (config_type);

-- Used by: DeveloperHub (issues, feedback, deploys)

CREATE TABLE IF NOT EXISTS public.admin_dev_hub (
  id text PRIMARY KEY,
  item_type text NOT NULL,  -- 'issue', 'feedback'
  data jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_dev_hub_type
  ON public.admin_dev_hub (item_type);

-- RLS: admin tables are internal-only, accessed via anon key from admin dashboard
-- The admin dashboard is PIN-protected and not exposed to end users
ALTER TABLE public.admin_content_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.admin_dev_hub ENABLE ROW LEVEL SECURITY;

-- Allow all operations for anon (admin dashboard uses anon key behind PIN gate)
CREATE POLICY admin_content_config_all ON public.admin_content_config
  FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY admin_dev_hub_all ON public.admin_dev_hub
  FOR ALL USING (true) WITH CHECK (true);
