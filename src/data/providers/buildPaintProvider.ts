/**
 * Build & Paint domain provider — projects, steps, notes, analytics metrics.
 */

import { API_LIMITS } from '@/constants/apiLimits';
import type {
  AnalyticsMetrics,
  BuildPaintProject,
  BuildPaintStep,
  BuildPaintNote,
  PaintRecipe,
  CreateBuildPaintProjectInput,
} from '../types';
import { supabase } from '../../lib/supabase';
import logger from '../../utils/logger';

export async function getAnalyticsMetrics(): Promise<AnalyticsMetrics> {
  let activeProjects = 0;
  let backlogProjects = 0;
  let completedProjects = 0;
  let totalBuildMinutes = 0;
  let twitchCreatorsTracked = 0;
  let twitchCreatorsLive = 0;

  const [projectsRes, sessionsRes, twitchRes] = await Promise.allSettled([
    supabase.from('build_paint_projects').select('id, status').limit(API_LIMITS.BATCH_PROJECTS),
    supabase.from('build_paint_sessions').select('minutes').limit(API_LIMITS.BATCH_LARGE),
    // twitch_creators has no is_live column — use last_seen_live_at
    // (recent timestamp = "currently live", < 15 min threshold).
    supabase.from('twitch_creators').select('id, last_seen_live_at').limit(API_LIMITS.BATCH_PROJECTS),
  ]);

  if (projectsRes.status === 'fulfilled') {
    const { data, error } = projectsRes.value;
    if (!error && Array.isArray(data)) {
      for (const row of data) {
        const status = (row.status || '').toString().toLowerCase();
        if (status === 'finished' || status === 'completed' || status === 'displayed') {
          completedProjects += 1;
        } else if (status === 'wishlist') {
          backlogProjects += 1;
        } else {
          activeProjects += 1;  // Everything between wishlist and finished is "active"
        }
      }
    }
  }

  if (sessionsRes.status === 'fulfilled') {
    const { data, error } = sessionsRes.value;
    if (!error && Array.isArray(data)) {
      for (const row of data) {
        const m = Number(row.minutes ?? 0);
        if (!Number.isNaN(m)) totalBuildMinutes += m;
      }
    }
  }

  if (twitchRes.status === 'fulfilled') {
    const { data, error } = twitchRes.value;
    if (!error && Array.isArray(data)) {
      twitchCreatorsTracked = data.length;
      const liveThreshold = Date.now() - 15 * 60 * 1000; // 15 min window
      twitchCreatorsLive = data.filter((row: { id: string; last_seen_live_at?: string | null }) => {
        const t = row.last_seen_live_at ? Date.parse(row.last_seen_live_at) : 0;
        return t > liveThreshold;
      }).length;
    }
  }

  return {
    activeProjects,
    backlogProjects,
    completedProjects,
    totalBuildMinutes,
    totalBuildHours: totalBuildMinutes / 60,
    twitchCreatorsTracked,
    twitchCreatorsLive,
  };
}

export async function listBuildPaintProjects(): Promise<BuildPaintProject[]> {
  // build_paint_projects real columns: name (no separate title), image_url
  // (no cover_image_url), last_updated (no updated_at), progress_pct (no
  // percent_complete). paint_recipes never existed on the table — recipes
  // live elsewhere if/when reintroduced.
  const bpCols = 'id, name, category, category_id, item_id, status, progress_pct, image_url, notes, created_at, last_updated';
  const { data, error } = await supabase
    .from('build_paint_projects')
    .select(bpCols)
    .order('last_updated', { ascending: false })
    .limit(200);

  if (error) {
    logger.warn('[SupabaseDataProvider] listBuildPaintProjects error:', error);
    return [];
  }

  return (data ?? []).map((row: Record<string, unknown>) => ({
    id: row.id as string,
    title: (row.name as string) || 'Untitled',
    category: row.category as string | undefined,
    categoryId: (row.category_id as string) ?? undefined,
    itemId: (row.item_id as string) ?? undefined,
    itemName: undefined,
    itemImageUrl: undefined,
    status: row.status as string | undefined,
    percent: (row.progress_pct as number) ?? 0,
    isCompleted: ['finished', 'completed', 'displayed'].includes(((row.status as string) || '').toLowerCase()),
    notes: row.notes as string | undefined,
    imageUrl: (row.image_url as string) ?? undefined,
    paintRecipes: [],
    createdAt: (row.created_at as string) ?? new Date().toISOString(),
    updatedAt: (row.last_updated as string) ?? new Date().toISOString(),
  }));
}

export async function createBuildPaintProject(input: CreateBuildPaintProjectInput): Promise<BuildPaintProject> {
  let data: unknown;
  let error: { message?: string } | null;

  ({ data, error } = await supabase.rpc('rpc_create_build_paint_project_v1', {
    p_title: input.title,
    p_category: input.category || null,
    p_category_id: input.categoryId || null,
    p_item_id: input.itemId || null,
  }));

  if (error) {
    logger.info('[SupabaseDataProvider] trying original RPC signature');
    ({ data, error } = await supabase.rpc('rpc_create_build_paint_project_v1', {
      p_title: input.title,
      p_category: input.category || null,
    }));
  }

  if (error) {
    logger.warn('[SupabaseDataProvider] createBuildPaintProject error:', error);
    throw new Error(error.message || 'Failed to create project');
  }

  const row = data as Record<string, unknown>;
  return {
    id: row.id as string,
    title: row.title as string,
    category: row.category as string | undefined,
    categoryId: (row.category_id as string | null) ?? undefined,
    itemId: (row.item_id as string | null) ?? undefined,
    status: row.status as string | undefined,
    percent: (row.percent_complete as number | null) ?? 0,
    isCompleted: (row.is_completed as boolean | null) ?? false,
    notes: (row.notes as string | null) || null,
    createdAt: (row.created_at as string | null) ?? new Date().toISOString(),
    updatedAt: (row.updated_at as string | null) ?? new Date().toISOString(),
  };
}

export async function setBuildPaintProgress(projectId: string, percent: number, status?: string): Promise<void> {
  const { error } = await supabase.rpc('rpc_set_build_paint_progress_v1', {
    p_project_id: projectId,
    p_percent: percent,
    p_status: status || null,
  });

  if (error) {
    logger.warn('[SupabaseDataProvider] setBuildPaintProgress error:', error);
    throw new Error(error.message || 'Failed to set progress');
  }
}

export async function markBuildPaintProjectComplete(projectId: string, isCompleted: boolean): Promise<void> {
  const { error } = await supabase.rpc('rpc_mark_build_paint_project_complete_v1', {
    p_project_id: projectId,
    p_is_completed: isCompleted,
  });

  if (error) {
    logger.warn('[SupabaseDataProvider] markBuildPaintProjectComplete error:', error);
    throw new Error(error.message || 'Failed to mark complete');
  }
}

export async function listBuildPaintSteps(projectId: string): Promise<BuildPaintStep[]> {
  const { data, error } = await supabase
    .from('v_build_paint_project_steps_v1')
    .select('id, project_id, title, is_done, sort_order, created_at')
    .eq('project_id', projectId)
    .order('sort_order', { ascending: true });

  if (error) {
    logger.warn('[SupabaseDataProvider] listBuildPaintSteps error:', error);
    return [];
  }

  type StepRow = { id: string; project_id: string; title: string; is_done?: boolean; sort_order?: number; created_at?: string };
  return (data ?? []).map((row: StepRow) => ({
    id: row.id,
    projectId: row.project_id,
    title: row.title,
    isDone: row.is_done ?? false,
    sortOrder: row.sort_order ?? 0,
    createdAt: row.created_at ?? new Date().toISOString(),
  }));
}

export async function addBuildPaintStep(projectId: string, title: string): Promise<BuildPaintStep> {
  const { data, error } = await supabase.rpc('rpc_add_build_paint_step_v1', {
    p_project_id: projectId,
    p_title: title,
  });

  if (error) {
    logger.warn('[SupabaseDataProvider] addBuildPaintStep error:', error);
    throw new Error(error.message || 'Failed to add step');
  }

  const row = data as Record<string, unknown>;
  return {
    id: row.id as string,
    projectId: row.project_id as string,
    title: row.title as string,
    isDone: (row.is_done as boolean | null) ?? false,
    sortOrder: (row.sort_order as number | null) ?? 0,
    createdAt: (row.created_at as string | null) ?? new Date().toISOString(),
  };
}

export async function toggleBuildPaintStep(stepId: string, isDone: boolean): Promise<void> {
  const { error } = await supabase.rpc('rpc_toggle_build_paint_step_v1', {
    p_step_id: stepId,
    p_is_done: isDone,
  });

  if (error) {
    logger.warn('[SupabaseDataProvider] toggleBuildPaintStep error:', error);
    throw new Error(error.message || 'Failed to toggle step');
  }
}

export async function listBuildPaintNotes(projectId: string): Promise<BuildPaintNote[]> {
  const { data, error } = await supabase
    .from('v_build_paint_project_notes_v1')
    .select('id, project_id, body, created_at')
    .eq('project_id', projectId)
    .order('created_at', { ascending: false });

  if (error) {
    logger.warn('[SupabaseDataProvider] listBuildPaintNotes error:', error);
    return [];
  }

  type NoteRow = { id: string; project_id: string; body: string; created_at?: string };
  return (data ?? []).map((row: NoteRow) => ({
    id: row.id,
    projectId: row.project_id,
    body: row.body,
    createdAt: row.created_at ?? new Date().toISOString(),
  }));
}

export async function addBuildPaintNote(projectId: string, body: string): Promise<BuildPaintNote> {
  const { data, error } = await supabase.rpc('rpc_add_build_paint_note_v1', {
    p_project_id: projectId,
    p_body: body,
  });

  if (error) {
    logger.warn('[SupabaseDataProvider] addBuildPaintNote error:', error);
    throw new Error(error.message || 'Failed to add note');
  }

  const row = data as Record<string, unknown>;
  return {
    id: row.id as string,
    projectId: row.project_id as string,
    body: row.body as string,
    createdAt: (row.created_at as string | null) ?? new Date().toISOString(),
  };
}

export async function listBuildPaintProjectsByCategory(categoryId: string): Promise<BuildPaintProject[]> {
  const { data, error } = await supabase
    .from('build_paint_projects')
    .select('id, name, status, category_id, item_id, image_url, created_at, last_updated')
    .eq('category_id', categoryId)
    .order('last_updated', { ascending: false });

  if (error) {
    logger.warn('[SupabaseDataProvider] listBuildPaintProjectsByCategory error:', error);
    return [];
  }

  return (data ?? []).map((r: Record<string, unknown>) => ({
    id: r.id as string,
    title: (r.name as string) ?? 'Untitled',
    status: (r.status as string) ?? 'in_progress',
    categoryId: (r.category_id as string | null) ?? undefined,
    itemId: (r.item_id as string | null) ?? undefined,
    imageUrl: (r.image_url as string | null) ?? undefined,
    percent: 0,
    isCompleted: ['finished', 'completed', 'displayed'].includes(((r.status as string) || '').toLowerCase()),
    paintRecipes: [],
    createdAt: (r.created_at as string | null) ?? new Date().toISOString(),
    updatedAt: (r.last_updated as string | null) ?? new Date().toISOString(),
  }));
}

export async function listBuildPaintProjectsByItem(itemId: string): Promise<BuildPaintProject[]> {
  const { data, error } = await supabase
    .from('build_paint_projects')
    .select('id, name, status, category_id, item_id, image_url, created_at, last_updated')
    .eq('item_id', itemId)
    .order('last_updated', { ascending: false });

  if (error) {
    logger.warn('[SupabaseDataProvider] listBuildPaintProjectsByItem error:', error);
    return [];
  }

  return (data ?? []).map((r: Record<string, unknown>) => ({
    id: r.id as string,
    title: (r.name as string) ?? 'Untitled',
    status: (r.status as string) ?? 'in_progress',
    categoryId: (r.category_id as string | null) ?? undefined,
    itemId: (r.item_id as string | null) ?? undefined,
    imageUrl: (r.image_url as string | null) ?? undefined,
    percent: 0,
    isCompleted: ['finished', 'completed', 'displayed'].includes(((r.status as string) || '').toLowerCase()),
    paintRecipes: [],
    createdAt: (r.created_at as string | null) ?? new Date().toISOString(),
    updatedAt: (r.last_updated as string | null) ?? new Date().toISOString(),
  }));
}

export async function applyStepTemplate(projectId: string, categoryId: string): Promise<BuildPaintStep[]> {
  const { getStepTemplateForCategory } = await import('../../constants/buildStepTemplates');
  const template = getStepTemplateForCategory(categoryId);
  const steps: BuildPaintStep[] = [];
  for (const s of template.steps) {
    const step = await addBuildPaintStep(projectId, s.label);
    steps.push(step);
  }
  return steps;
}

export async function updateBuildPaintProject(projectId: string, patch: { paintRecipes?: unknown[] }): Promise<void> {
  const updatePayload: Record<string, unknown> = {};
  if (patch.paintRecipes !== undefined) {
    updatePayload.paint_recipes = patch.paintRecipes;
  }
  const { error } = await supabase
    .from('build_paint_projects')
    .update(updatePayload)
    .eq('id', projectId);
  if (error) {
    logger.error('[SupabaseDataProvider] updateBuildPaintProject error:', error);
    throw new Error(error.message || 'Failed to update project');
  }
}
