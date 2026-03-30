// ---------------------------------------------------------------------------
// Content Machine — Persistence layer
// Saves/loads generated content to Supabase with localStorage fallback
// ---------------------------------------------------------------------------

import { getSupabase, isSupabaseConfigured } from "@/lib/supabase";
import type { ContentIdea, WeeklyCalendar, CaptionPack, ContentBatch } from "./types";

// ─── localStorage keys ───────────────────────────────────────────────────

const LS_PREFIX = "cm_";
const LS_IDEAS = `${LS_PREFIX}ideas`;
const LS_CALENDAR = `${LS_PREFIX}calendar`;
const LS_CAPTIONS = `${LS_PREFIX}captions`;
const LS_BATCH = `${LS_PREFIX}batch`;
const LS_BATCH_CHECKS = `${LS_PREFIX}batch_checks`;
const LS_GENERATED_AT = `${LS_PREFIX}generated_at`;

// ─── Saved state type ────────────────────────────────────────────────────

export interface SavedGeneration {
  ideas: ContentIdea[];
  calendar: WeeklyCalendar | null;
  captionPacks: CaptionPack[];
  batch: ContentBatch | null;
  generatedAt: string;
}

// ─── localStorage helpers ────────────────────────────────────────────────

function lsGet<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function lsSet(key: string, value: unknown): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // localStorage full or disabled — ignore
  }
}

// ─── Save to localStorage ────────────────────────────────────────────────

export function saveToLocalStorage(gen: SavedGeneration): void {
  lsSet(LS_IDEAS, gen.ideas);
  lsSet(LS_CALENDAR, gen.calendar);
  lsSet(LS_CAPTIONS, gen.captionPacks);
  lsSet(LS_BATCH, gen.batch);
  lsSet(LS_GENERATED_AT, gen.generatedAt);
}

export function loadFromLocalStorage(): SavedGeneration | null {
  const ideas = lsGet<ContentIdea[]>(LS_IDEAS);
  if (!ideas || ideas.length === 0) return null;
  return {
    ideas,
    calendar: lsGet<WeeklyCalendar>(LS_CALENDAR),
    captionPacks: lsGet<CaptionPack[]>(LS_CAPTIONS) ?? [],
    batch: lsGet<ContentBatch>(LS_BATCH),
    generatedAt: lsGet<string>(LS_GENERATED_AT) ?? new Date().toISOString(),
  };
}

export function clearLocalStorage(): void {
  if (typeof window === "undefined") return;
  [LS_IDEAS, LS_CALENDAR, LS_CAPTIONS, LS_BATCH, LS_BATCH_CHECKS, LS_GENERATED_AT].forEach((k) =>
    localStorage.removeItem(k)
  );
}

// ─── Batch checklist persistence ─────────────────────────────────────────

export function saveBatchChecks(checked: string[]): void {
  lsSet(LS_BATCH_CHECKS, checked);
}

export function loadBatchChecks(): string[] {
  return lsGet<string[]>(LS_BATCH_CHECKS) ?? [];
}

// ─── Save to Supabase ────────────────────────────────────────────────────

export async function saveToSupabase(gen: SavedGeneration): Promise<boolean> {
  if (!isSupabaseConfigured()) return false;
  const sb = getSupabase();
  if (!sb) return false;

  try {
    // Save ideas
    const ideaRows = gen.ideas.map((idea) => ({
      id: idea.id,
      title: idea.title,
      hook: idea.hook,
      concept: idea.concept,
      shot_list: idea.shotList,
      voiceover: idea.voiceover,
      cta: idea.cta,
      pillar_id: null, // Would need pillar UUID lookup
      objective_type: idea.objectiveType,
      commerce_mode: idea.commerceMode,
      presence_mode: idea.presenceMode,
      paid_candidate: idea.paidCandidate,
      affiliate_ready: idea.affiliateReady,
      boostable_reason: idea.boostableReason,
      target_keyword: idea.targetKeyword,
      hashtags: idea.hashtags,
      series_id: idea.seriesId,
      series_order: idea.seriesOrder,
      format: idea.format,
      estimated_duration: idea.estimatedDuration,
      language_code: idea.languageCode,
      status: idea.status,
      priority: idea.priority,
      target_completion_rate: idea.targetCompletionRate,
      target_save_rate: idea.targetSaveRate,
    }));

    const { error: ideasError } = await sb
      .from("content_ideas")
      .upsert(ideaRows, { onConflict: "id" });

    if (ideasError) {
      console.error("Failed to save ideas to Supabase:", ideasError);
      return false;
    }

    // Save calendar
    if (gen.calendar) {
      const { error: calError } = await sb
        .from("weekly_calendars")
        .upsert({
          id: gen.calendar.id,
          week_start: gen.calendar.weekStart,
          goal: gen.calendar.goal,
          notes: gen.calendar.notes,
          pillar_distribution: gen.calendar.pillarDistribution,
          batch_film_day: gen.calendar.batchFilmDay,
          status: "draft",
        }, { onConflict: "id" });

      if (calError) {
        console.error("Failed to save calendar to Supabase:", calError);
      }
    }

    return true;
  } catch (err) {
    console.error("Supabase save failed:", err);
    return false;
  }
}

// ─── Load from Supabase ──────────────────────────────────────────────────

export async function loadFromSupabase(): Promise<SavedGeneration | null> {
  if (!isSupabaseConfigured()) return null;
  const sb = getSupabase();
  if (!sb) return null;

  try {
    const { data, error } = await sb
      .from("content_ideas")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(50);

    if (error || !data || data.length === 0) return null;

    const ideas: ContentIdea[] = data.map((r: Record<string, unknown>) => ({
      id: r.id as string,
      title: r.title as string,
      hook: r.hook as string,
      concept: r.concept as string,
      shotList: (r.shot_list as string[]) ?? [],
      voiceover: (r.voiceover as string) ?? "",
      cta: (r.cta as string) ?? "",
      pillarSlug: "", // Would need JOIN
      pillarName: "",
      pillarEmoji: "",
      accountHandle: "",
      objectiveType: (r.objective_type as ContentIdea["objectiveType"]) ?? "awareness",
      commerceMode: (r.commerce_mode as ContentIdea["commerceMode"]) ?? "organic",
      presenceMode: (r.presence_mode as ContentIdea["presenceMode"]) ?? "hands_only",
      paidCandidate: (r.paid_candidate as boolean) ?? false,
      affiliateReady: (r.affiliate_ready as boolean) ?? false,
      boostableReason: r.boostable_reason as string | undefined,
      targetKeyword: r.target_keyword as string | undefined,
      hashtags: (r.hashtags as string[]) ?? [],
      seriesId: r.series_id as string | undefined,
      seriesOrder: r.series_order as number | undefined,
      format: (r.format as ContentIdea["format"]) ?? "reveal",
      estimatedDuration: (r.estimated_duration as string) ?? "15-30s",
      languageCode: (r.language_code as ContentIdea["languageCode"]) ?? "en",
      status: (r.status as ContentIdea["status"]) ?? "draft",
      priority: (r.priority as ContentIdea["priority"]) ?? "normal",
      targetCompletionRate: r.target_completion_rate as number | undefined,
      targetSaveRate: r.target_save_rate as number | undefined,
    }));

    return {
      ideas,
      calendar: null,
      captionPacks: [],
      batch: null,
      generatedAt: (data[0]?.created_at as string) ?? new Date().toISOString(),
    };
  } catch {
    return null;
  }
}

// ─── Update idea status ──────────────────────────────────────────────────

export async function updateIdeaStatus(
  ideaId: string,
  status: ContentIdea["status"]
): Promise<boolean> {
  if (!isSupabaseConfigured()) return false;
  const sb = getSupabase();
  if (!sb) return false;

  const { error } = await sb
    .from("content_ideas")
    .update({ status })
    .eq("id", ideaId);

  return !error;
}

export async function updateIdeaPriority(
  ideaId: string,
  priority: ContentIdea["priority"]
): Promise<boolean> {
  if (!isSupabaseConfigured()) return false;
  const sb = getSupabase();
  if (!sb) return false;

  const { error } = await sb
    .from("content_ideas")
    .update({ priority })
    .eq("id", ideaId);

  return !error;
}
