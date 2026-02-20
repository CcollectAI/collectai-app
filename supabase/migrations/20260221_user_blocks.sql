-- ============================================================================
-- User Blocks table + RPC functions
-- Supports blocking/unblocking users and auto-declining pending DMs
-- ============================================================================

-- Table
CREATE TABLE IF NOT EXISTS user_blocks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  blocker_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  blocked_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(blocker_id, blocked_id),
  CHECK (blocker_id != blocked_id)
);

CREATE INDEX IF NOT EXISTS idx_blocks_blocker ON user_blocks(blocker_id);
CREATE INDEX IF NOT EXISTS idx_blocks_blocked ON user_blocks(blocked_id);

-- RLS
ALTER TABLE user_blocks ENABLE ROW LEVEL SECURITY;

CREATE POLICY blocks_select ON user_blocks
  FOR SELECT USING (blocker_id = auth.uid());

CREATE POLICY blocks_insert ON user_blocks
  FOR INSERT WITH CHECK (blocker_id = auth.uid());

CREATE POLICY blocks_delete ON user_blocks
  FOR DELETE USING (blocker_id = auth.uid());

-- ============================================================================
-- RPC: Block a user
-- Inserts block row + auto-declines any pending DM threads between the pair
-- ============================================================================
CREATE OR REPLACE FUNCTION rpc_block_user_v1(p_target_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_uid uuid := auth.uid();
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  IF v_uid = p_target_id THEN
    RAISE EXCEPTION 'Cannot block yourself';
  END IF;

  -- Insert block (ignore if already exists)
  INSERT INTO user_blocks (blocker_id, blocked_id)
  VALUES (v_uid, p_target_id)
  ON CONFLICT (blocker_id, blocked_id) DO NOTHING;

  -- Auto-decline any pending DM threads between these two users
  UPDATE chat_threads
  SET status = 'declined'
  WHERE status = 'pending'
    AND (
      (sender_id = v_uid AND recipient_id = p_target_id) OR
      (sender_id = p_target_id AND recipient_id = v_uid)
    );
END;
$$;

-- ============================================================================
-- RPC: Unblock a user
-- ============================================================================
CREATE OR REPLACE FUNCTION rpc_unblock_user_v1(p_target_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_uid uuid := auth.uid();
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  DELETE FROM user_blocks
  WHERE blocker_id = v_uid
    AND blocked_id = p_target_id;
END;
$$;

-- ============================================================================
-- RPC: List blocked user IDs
-- ============================================================================
CREATE OR REPLACE FUNCTION rpc_list_blocked_v1()
RETURNS TABLE(blocked_id uuid, created_at timestamptz)
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT ub.blocked_id, ub.created_at
  FROM user_blocks ub
  WHERE ub.blocker_id = auth.uid()
  ORDER BY ub.created_at DESC;
END;
$$;

-- ============================================================================
-- RPC: Check if blocked (either direction)
-- Returns true if either user has blocked the other
-- ============================================================================
CREATE OR REPLACE FUNCTION rpc_is_blocked_v1(p_other_id uuid)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
AS $$
DECLARE
  v_uid uuid := auth.uid();
BEGIN
  IF v_uid IS NULL THEN
    RETURN false;
  END IF;

  RETURN EXISTS (
    SELECT 1 FROM user_blocks
    WHERE (blocker_id = v_uid AND blocked_id = p_other_id)
       OR (blocker_id = p_other_id AND blocked_id = v_uid)
  );
END;
$$;
