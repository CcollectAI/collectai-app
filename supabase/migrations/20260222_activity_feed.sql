-- Activity feed for tracking user actions
CREATE TABLE IF NOT EXISTS activity_feed (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  activity_type text NOT NULL CHECK (activity_type IN (
    'item_added', 'item_sold', 'event_rsvp', 'event_created',
    'project_completed', 'achievement_earned', 'category_followed',
    'collection_milestone'
  )),
  title text NOT NULL,
  description text,
  metadata jsonb DEFAULT '{}',
  is_public boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE activity_feed ENABLE ROW LEVEL SECURITY;

CREATE POLICY "activity_feed_select" ON activity_feed
  FOR SELECT USING (is_public = true OR user_id = auth.uid());

CREATE POLICY "activity_feed_insert" ON activity_feed
  FOR INSERT WITH CHECK (user_id = auth.uid());

CREATE INDEX idx_activity_feed_user ON activity_feed(user_id, created_at DESC);
CREATE INDEX idx_activity_feed_public ON activity_feed(user_id, is_public, created_at DESC) WHERE is_public = true;

-- RPC: Log an activity
CREATE OR REPLACE FUNCTION rpc_log_activity_v1(
  p_activity_type text,
  p_title text,
  p_description text DEFAULT NULL,
  p_metadata jsonb DEFAULT '{}',
  p_is_public boolean DEFAULT true
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_id uuid;
BEGIN
  INSERT INTO activity_feed (user_id, activity_type, title, description, metadata, is_public)
  VALUES (auth.uid(), p_activity_type, p_title, p_description, p_metadata, p_is_public)
  RETURNING id INTO v_id;
  RETURN v_id;
END;
$$;

-- RPC: Get user activity feed
CREATE OR REPLACE FUNCTION rpc_get_user_activity_v1(
  p_user_id uuid,
  p_limit int DEFAULT 20,
  p_offset int DEFAULT 0
)
RETURNS TABLE(
  id uuid,
  user_id uuid,
  activity_type text,
  title text,
  description text,
  metadata jsonb,
  is_public boolean,
  created_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  RETURN QUERY
  SELECT af.id, af.user_id, af.activity_type, af.title, af.description,
         af.metadata, af.is_public, af.created_at
  FROM activity_feed af
  WHERE af.user_id = p_user_id
    AND (af.is_public = true OR af.user_id = auth.uid())
  ORDER BY af.created_at DESC
  LIMIT p_limit
  OFFSET p_offset;
END;
$$;
