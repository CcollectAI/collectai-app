-- Members can delete their own build & paint project (2026-09-26).
--
-- build_paint_projects had SELECT/INSERT/UPDATE policies and no DELETE, and
-- the app had no delete path, so a project made by mistake could never be
-- removed (walked on Android). Steps and notes already carry owner DELETE
-- policies; the app removes them first (they have no ON DELETE CASCADE).
DROP POLICY IF EXISTS delete_own_build_projects ON public.build_paint_projects;
CREATE POLICY delete_own_build_projects ON public.build_paint_projects
  FOR DELETE TO authenticated
  USING (auth.uid() = user_id);
