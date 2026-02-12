-- RLS Enforcement Migration
-- Adds missing user_id column to feedback table, adds RLS policies for
-- user_push_tokens, and tightens object_pointers policies.
--
-- Context: asyncpg connections bypass Supabase RLS because they use service-role
-- credentials. This migration adds database-level policies as defense-in-depth,
-- complementing the application-level user_id filtering added in the routers.

BEGIN;

-- =========================================================================
-- 1. feedback table: add user_id column
-- =========================================================================

ALTER TABLE public.feedback
  ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES auth.users(id);

CREATE INDEX IF NOT EXISTS idx_feedback_user_id
  ON public.feedback(user_id);

-- RLS policy: users can only read/write their own feedback
DROP POLICY IF EXISTS feedback_owner_select ON public.feedback;
CREATE POLICY feedback_owner_select ON public.feedback
  FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS feedback_owner_insert ON public.feedback;
CREATE POLICY feedback_owner_insert ON public.feedback
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Service role can read all feedback (for training pipeline / workers)
DROP POLICY IF EXISTS feedback_service_all ON public.feedback;
CREATE POLICY feedback_service_all ON public.feedback
  FOR ALL
  USING (current_setting('role', true) = 'service_role')
  WITH CHECK (current_setting('role', true) = 'service_role');

-- =========================================================================
-- 2. user_push_tokens: enable RLS + add owner policy
-- =========================================================================

ALTER TABLE public.user_push_tokens ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS push_tokens_owner_select ON public.user_push_tokens;
CREATE POLICY push_tokens_owner_select ON public.user_push_tokens
  FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS push_tokens_owner_mod ON public.user_push_tokens;
CREATE POLICY push_tokens_owner_mod ON public.user_push_tokens
  FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- Service role can manage all tokens (for push notification worker)
DROP POLICY IF EXISTS push_tokens_service_all ON public.user_push_tokens;
CREATE POLICY push_tokens_service_all ON public.user_push_tokens
  FOR ALL
  USING (current_setting('role', true) = 'service_role')
  WITH CHECK (current_setting('role', true) = 'service_role');

-- =========================================================================
-- 3. object_pointers: tighten RLS policies
-- =========================================================================

-- Users can only see their own objects
DROP POLICY IF EXISTS object_pointers_owner_select ON public.object_pointers;
CREATE POLICY object_pointers_owner_select ON public.object_pointers
  FOR SELECT USING (auth.uid()::text = created_by);

-- Users can only insert objects attributed to themselves
DROP POLICY IF EXISTS object_pointers_owner_insert ON public.object_pointers;
CREATE POLICY object_pointers_owner_insert ON public.object_pointers
  FOR INSERT WITH CHECK (auth.uid()::text = created_by);

-- Users can only update/delete their own objects
DROP POLICY IF EXISTS object_pointers_owner_update ON public.object_pointers;
CREATE POLICY object_pointers_owner_update ON public.object_pointers
  FOR UPDATE USING (auth.uid()::text = created_by);

DROP POLICY IF EXISTS object_pointers_owner_delete ON public.object_pointers;
CREATE POLICY object_pointers_owner_delete ON public.object_pointers
  FOR DELETE USING (auth.uid()::text = created_by);

-- Service role bypass for workers/system
DROP POLICY IF EXISTS object_pointers_service_all ON public.object_pointers;
CREATE POLICY object_pointers_service_all ON public.object_pointers
  FOR ALL
  USING (current_setting('role', true) = 'service_role')
  WITH CHECK (current_setting('role', true) = 'service_role');

-- =========================================================================
-- 4. item_provenance_events: tighten to owner via items join
-- =========================================================================

-- Users can only read provenance for items they own
DROP POLICY IF EXISTS provenance_owner_select ON public.item_provenance_events;
CREATE POLICY provenance_owner_select ON public.item_provenance_events
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.items
      WHERE items.id = item_provenance_events.item_id
        AND items.user_id = auth.uid()
    )
  );

-- Users can only insert provenance for items they own
DROP POLICY IF EXISTS provenance_owner_insert ON public.item_provenance_events;
CREATE POLICY provenance_owner_insert ON public.item_provenance_events
  FOR INSERT WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.items
      WHERE items.id = item_provenance_events.item_id
        AND items.user_id = auth.uid()
    )
  );

-- Service role bypass for workers
DROP POLICY IF EXISTS provenance_service_all ON public.item_provenance_events;
CREATE POLICY provenance_service_all ON public.item_provenance_events
  FOR ALL
  USING (current_setting('role', true) = 'service_role')
  WITH CHECK (current_setting('role', true) = 'service_role');

COMMIT;
