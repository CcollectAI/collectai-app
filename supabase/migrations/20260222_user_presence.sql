-- ═══════════════════════════════════════════════════════════════════════════════
-- LP-3: User Presence Tracking (Online/Offline/Last-Seen)
-- ═══════════════════════════════════════════════════════════════════════════════

-- User presence tracking table
CREATE TABLE IF NOT EXISTS user_presence (
  user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  is_online boolean NOT NULL DEFAULT false,
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- RLS
ALTER TABLE user_presence ENABLE ROW LEVEL SECURITY;

-- Anyone can read presence (public feature)
CREATE POLICY "user_presence_select" ON user_presence
  FOR SELECT USING (true);

-- Users can only update their own presence
CREATE POLICY "user_presence_upsert" ON user_presence
  FOR INSERT WITH CHECK (user_id = auth.uid());

CREATE POLICY "user_presence_update" ON user_presence
  FOR UPDATE USING (user_id = auth.uid());

-- Index for online users
CREATE INDEX idx_user_presence_online ON user_presence(is_online) WHERE is_online = true;

-- RPC: Heartbeat — upsert presence, mark online
CREATE OR REPLACE FUNCTION rpc_heartbeat_v1()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO user_presence (user_id, last_seen_at, is_online, updated_at)
  VALUES (auth.uid(), now(), true, now())
  ON CONFLICT (user_id)
  DO UPDATE SET last_seen_at = now(), is_online = true, updated_at = now();
END;
$$;

-- RPC: Go offline
CREATE OR REPLACE FUNCTION rpc_go_offline_v1()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  UPDATE user_presence
  SET is_online = false, updated_at = now()
  WHERE user_id = auth.uid();
END;
$$;

-- RPC: Get presence for a user
CREATE OR REPLACE FUNCTION rpc_get_presence_v1(p_user_id uuid)
RETURNS TABLE(user_id uuid, last_seen_at timestamptz, is_online boolean)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  RETURN QUERY
  SELECT up.user_id, up.last_seen_at,
    -- Consider offline if last heartbeat > 2 minutes ago
    CASE WHEN up.last_seen_at > now() - interval '2 minutes' AND up.is_online
         THEN true ELSE false END AS is_online
  FROM user_presence up
  WHERE up.user_id = p_user_id;
END;
$$;

-- RPC: Get batch presence for multiple users
CREATE OR REPLACE FUNCTION rpc_get_batch_presence_v1(p_user_ids uuid[])
RETURNS TABLE(user_id uuid, last_seen_at timestamptz, is_online boolean)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  RETURN QUERY
  SELECT up.user_id, up.last_seen_at,
    CASE WHEN up.last_seen_at > now() - interval '2 minutes' AND up.is_online
         THEN true ELSE false END AS is_online
  FROM user_presence up
  WHERE up.user_id = ANY(p_user_ids);
END;
$$;

-- Cleanup: mark stale users offline (run periodically)
CREATE OR REPLACE FUNCTION cleanup_stale_presence()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  UPDATE user_presence
  SET is_online = false
  WHERE is_online = true
    AND last_seen_at < now() - interval '3 minutes';
END;
$$;
