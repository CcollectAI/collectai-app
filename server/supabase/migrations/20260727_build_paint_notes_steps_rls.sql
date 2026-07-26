-- Build & Paint: replace deny-all RLS on notes + steps with owner policies.
--
-- Apply via: psql $DB_DSN_DIRECT -f 20260727_build_paint_notes_steps_rls.sql
--
-- WHY
-- ---
-- build_paint_notes and build_paint_steps each carried a single policy
-- (`*_deny_all`, FOR ALL, USING false / WITH CHECK false). That is a total
-- denial: every insert was rejected and every select returned zero rows.
-- build_paint_notes had 0 rows table-wide.
--
-- The UI showed no error, because the two directions fail differently:
--   addBuildPaintNote()   throws  -> a toast the user may miss
--   listBuildPaintNotes() returns [] on error -> renders "No notes added yet"
-- So a shipped feature read as simply "empty". Same for Steps, which also made
-- the 7 per-category templates in src/constants/buildStepTemplates.ts
-- unreachable — they can never be seeded into a table that refuses writes.
--
-- These were NOT intentional: audit_rls_coverage.py documents exactly one
-- table as legitimately deny-all (subscription_events, service-role only).
--
-- Ownership model differs per table:
--   notes  has user_id NOT NULL          -> auth.uid() = user_id, like
--                                           build_paint_projects.
--   steps  has NO user_id column         -> ownership is derived through
--                                           project_id. The client insert
--                                           ({project_id, title, status,
--                                           step_order}) sets no user_id, so a
--                                           user_id-based policy would reject
--                                           every write.

BEGIN;

-- ---------------------------------------------------------------------------
-- build_paint_notes — owned directly via user_id
-- ---------------------------------------------------------------------------
ALTER TABLE build_paint_notes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS build_paint_notes_deny_all ON build_paint_notes;

DROP POLICY IF EXISTS select_own_build_notes ON build_paint_notes;
CREATE POLICY select_own_build_notes ON build_paint_notes
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS insert_own_build_notes ON build_paint_notes;
CREATE POLICY insert_own_build_notes ON build_paint_notes
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS update_own_build_notes ON build_paint_notes;
CREATE POLICY update_own_build_notes ON build_paint_notes
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS delete_own_build_notes ON build_paint_notes;
CREATE POLICY delete_own_build_notes ON build_paint_notes
    FOR DELETE USING (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- build_paint_steps — no user_id; ownership derived from the parent project
-- ---------------------------------------------------------------------------
ALTER TABLE build_paint_steps ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS build_paint_steps_deny_all ON build_paint_steps;

DROP POLICY IF EXISTS select_own_build_steps ON build_paint_steps;
CREATE POLICY select_own_build_steps ON build_paint_steps
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM build_paint_projects p
            WHERE p.id = build_paint_steps.project_id
              AND p.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS insert_own_build_steps ON build_paint_steps;
CREATE POLICY insert_own_build_steps ON build_paint_steps
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM build_paint_projects p
            WHERE p.id = build_paint_steps.project_id
              AND p.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS update_own_build_steps ON build_paint_steps;
CREATE POLICY update_own_build_steps ON build_paint_steps
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM build_paint_projects p
            WHERE p.id = build_paint_steps.project_id
              AND p.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS delete_own_build_steps ON build_paint_steps;
CREATE POLICY delete_own_build_steps ON build_paint_steps
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM build_paint_projects p
            WHERE p.id = build_paint_steps.project_id
              AND p.user_id = auth.uid()
        )
    );

-- Policy lookups run per row on read; index the FK they filter on.
CREATE INDEX IF NOT EXISTS idx_build_paint_steps_project_id
    ON build_paint_steps (project_id);
CREATE INDEX IF NOT EXISTS idx_build_paint_notes_user_id
    ON build_paint_notes (user_id);

COMMIT;
