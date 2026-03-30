// ---------------------------------------------------------------------------
// Content Machine — Type definitions for CollectAI content operating system
// ---------------------------------------------------------------------------

export type ObjectiveType = "awareness" | "proof" | "learning" | "conversion" | "retention";
export type CommerceMode = "organic" | "organic_plus_commerce" | "affiliate_ready";
export type PresenceMode = "face" | "voiceover" | "hands_only" | "text_only";

export type ContentFormat =
  | "tutorial"
  | "timelapse"
  | "POV"
  | "unboxing"
  | "ASMR"
  | "routine"
  | "reveal"
  | "comparison"
  | "transformation"
  | "fix-it"
  | "lifestyle"
  | "top-list";

export type IdeaStatus = "draft" | "approved" | "scheduled" | "filmed" | "posted" | "archived";
export type CalendarStatus = "draft" | "active" | "completed";
export type Priority = "low" | "normal" | "high" | "urgent";

export const LANGUAGES = ["en", "nl", "de", "fr", "es", "it"] as const;
export type LanguageCode = (typeof LANGUAGES)[number];

export const LANGUAGE_LABELS: Record<LanguageCode, string> = {
  en: "English",
  nl: "Nederlands",
  de: "Deutsch",
  fr: "Français",
  es: "Español",
  it: "Italiano",
};

// ─── Core Interfaces ────────────────────────────────────────────────────

export interface ContentAccount {
  id: string;
  handle: string;
  displayName: string;
  purpose: string;
  platform: string;
  contentFocus: string[];
  isActive: boolean;
}

export interface ContentPillar {
  id: string;
  slug: string;
  name: string;
  description: string;
  targetMixPct: number;
  defaultCta: string;
  emoji: string;
  bestFormats: ContentFormat[];
  bestPresence: PresenceMode[];
  isActive: boolean;
}

export interface ContentNiche {
  id: string;
  slug: string;
  name: string;
  categorySlug: string;
  emoji: string;
  priceRange: string;
  audienceTags: string[];
  trendingTopics: string[];
  shortDescription: string;
  personalityTags: string[];
}

export interface ContentProduct {
  id: string;
  slug: string;
  name: string;
  category: string;
  description: string;
  tier: string;
  bestContentAngles: string[];
}

export interface ContentIdea {
  id: string;
  title: string;
  hook: string;
  concept: string;
  shotList: string[];
  voiceover: string;
  cta: string;

  pillarSlug: string;
  pillarName: string;
  pillarEmoji: string;
  accountHandle: string;
  productSlug?: string;
  productName?: string;
  nicheSlug?: string;
  nicheName?: string;
  nicheEmoji?: string;

  objectiveType: ObjectiveType;
  commerceMode: CommerceMode;
  presenceMode: PresenceMode;
  paidCandidate: boolean;
  affiliateReady: boolean;
  boostableReason?: string;

  targetKeyword?: string;
  hashtags: string[];

  seriesId?: string;
  seriesOrder?: number;

  format: ContentFormat;
  estimatedDuration: string;
  languageCode: LanguageCode;

  status: IdeaStatus;
  priority: Priority;

  targetCompletionRate?: number;
  targetSaveRate?: number;
}

export interface CalendarItem {
  id: string;
  ideaId: string;
  idea: ContentIdea;
  accountHandle: string;
  plannedDate: string; // YYYY-MM-DD
  plannedTime: string; // HH:MM
  languageCode: LanguageCode;
  status: string;
  format: ContentFormat;
}

export interface WeeklyCalendar {
  id: string;
  weekStart: string; // YYYY-MM-DD
  goal: string;
  notes: string;
  pillarDistribution: Record<string, { target: number; actual: number }>;
  batchFilmDay: string;
  items: CalendarItem[];
  warnings: string[];
}

export interface GeneratedCaption {
  ideaId: string;
  ideaTitle: string;
  languageCode: LanguageCode;
  organic: string;
  commerce: string;
  hashtags: string[];
  seoKeyword: string;
}

export interface CaptionPack {
  ideaId: string;
  ideaTitle: string;
  hook: string;
  captions: Record<LanguageCode, { organic: string; commerce: string; hashtags: string[] }>;
}

export interface BatchItem {
  idea: ContentIdea;
  shotOrder: number;
  setupNotes: string;
}

export interface ContentBatch {
  id: string;
  title: string;
  batchDate: string;
  setupType: string;
  estimatedDurationMins: number;
  items: BatchItem[];
  preChecklist: string[];
  postTasks: string[];
}

// ─── Generator Options ──────────────────────────────────────────────────

export interface GenerateIdeasOptions {
  count?: number;
  pillarFilter?: string[];
  accountFilter?: string[];
  nicheFilter?: string[];
  languageCode?: LanguageCode;
}

export interface GenerateCalendarOptions {
  weekStart?: string;
  batchFilmDay?: "monday" | "tuesday" | "wednesday" | "thursday" | "friday" | "saturday" | "sunday";
  ideas?: ContentIdea[];
}

export interface GenerateBatchOptions {
  ideas?: ContentIdea[];
  maxDurationMins?: number;
  batchDate?: string;
}
