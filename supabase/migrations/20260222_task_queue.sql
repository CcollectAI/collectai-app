-- Background task queue
CREATE TABLE IF NOT EXISTS task_queue (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_type text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}',
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
  priority int NOT NULL DEFAULT 0,  -- Higher = more important
  result jsonb,
  error_message text,
  attempts int NOT NULL DEFAULT 0,
  max_attempts int NOT NULL DEFAULT 3,
  created_by uuid REFERENCES auth.users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  completed_at timestamptz,
  scheduled_for timestamptz DEFAULT now()  -- Can be used for delayed jobs
);

-- RLS
ALTER TABLE task_queue ENABLE ROW LEVEL SECURITY;

-- Users can see their own tasks
CREATE POLICY "task_queue_select_own" ON task_queue
  FOR SELECT USING (created_by = auth.uid());

-- Users can create tasks
CREATE POLICY "task_queue_insert" ON task_queue
  FOR INSERT WITH CHECK (created_by = auth.uid());

-- Indexes
CREATE INDEX idx_task_queue_status ON task_queue(status, priority DESC, scheduled_for)
  WHERE status = 'pending';
CREATE INDEX idx_task_queue_user ON task_queue(created_by, created_at DESC);
CREATE INDEX idx_task_queue_type ON task_queue(task_type, status);

-- RPC: Enqueue a task
CREATE OR REPLACE FUNCTION rpc_enqueue_task_v1(
  p_task_type text,
  p_payload jsonb DEFAULT '{}',
  p_priority int DEFAULT 0,
  p_scheduled_for timestamptz DEFAULT now()
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_id uuid;
BEGIN
  INSERT INTO task_queue (task_type, payload, priority, created_by, scheduled_for)
  VALUES (p_task_type, p_payload, p_priority, auth.uid(), p_scheduled_for)
  RETURNING id INTO v_id;
  RETURN v_id;
END;
$$;

-- RPC: Claim next pending task (for worker)
CREATE OR REPLACE FUNCTION rpc_claim_task_v1(p_task_types text[] DEFAULT NULL)
RETURNS TABLE(
  id uuid,
  task_type text,
  payload jsonb,
  attempts int
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  RETURN QUERY
  UPDATE task_queue tq
  SET status = 'running',
      started_at = now(),
      attempts = tq.attempts + 1
  WHERE tq.id = (
    SELECT t.id FROM task_queue t
    WHERE t.status = 'pending'
      AND t.scheduled_for <= now()
      AND t.attempts < t.max_attempts
      AND (p_task_types IS NULL OR t.task_type = ANY(p_task_types))
    ORDER BY t.priority DESC, t.scheduled_for ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
  )
  RETURNING tq.id, tq.task_type, tq.payload, tq.attempts;
END;
$$;

-- RPC: Complete a task
CREATE OR REPLACE FUNCTION rpc_complete_task_v1(
  p_task_id uuid,
  p_result jsonb DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  UPDATE task_queue
  SET status = 'completed',
      completed_at = now(),
      result = p_result
  WHERE id = p_task_id AND status = 'running';
END;
$$;

-- RPC: Fail a task
CREATE OR REPLACE FUNCTION rpc_fail_task_v1(
  p_task_id uuid,
  p_error text
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  UPDATE task_queue
  SET status = CASE
        WHEN attempts >= max_attempts THEN 'failed'
        ELSE 'pending'  -- Re-queue for retry
      END,
      error_message = p_error,
      completed_at = CASE WHEN attempts >= max_attempts THEN now() ELSE NULL END
  WHERE id = p_task_id AND status = 'running';
END;
$$;

-- RPC: Get user's task status
CREATE OR REPLACE FUNCTION rpc_get_task_status_v1(p_task_id uuid)
RETURNS TABLE(
  id uuid,
  task_type text,
  status text,
  result jsonb,
  error_message text,
  created_at timestamptz,
  completed_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  RETURN QUERY
  SELECT tq.id, tq.task_type, tq.status, tq.result, tq.error_message,
         tq.created_at, tq.completed_at
  FROM task_queue tq
  WHERE tq.id = p_task_id
    AND tq.created_by = auth.uid();
END;
$$;

-- Cleanup old completed tasks (run periodically)
CREATE OR REPLACE FUNCTION cleanup_old_tasks()
RETURNS int
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_count int;
BEGIN
  DELETE FROM task_queue
  WHERE status IN ('completed', 'failed', 'cancelled')
    AND completed_at < now() - interval '7 days';
  GET DIAGNOSTICS v_count = ROW_COUNT;
  RETURN v_count;
END;
$$;
