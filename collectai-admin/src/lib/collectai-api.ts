// ---------------------------------------------------------------------------
// CollectAI Backend API Client
// Connects to the FastAPI backend for admin data
// ---------------------------------------------------------------------------

import { APP_CONFIG } from "../../admin.config";
import { noteDemo, clearDemo, getDemoReason, isUsingDemoData as isDemoSource } from "@/lib/demoState";

const BASE = APP_CONFIG.api.baseUrl; // "/api/admin/api" — the same-origin proxy

/**
 * Demo data is OPT-IN. Until 2026-09-27 every failed request silently returned
 * invented numbers: the API refused the browser's origin (CORS), so the
 * Overview showed 2,847 users / 187,432 items with a green "LIVE" and
 * "DB: connected" while prod had 10 users and 21 items — and each tab's own
 * error state (which all seven callers already had) could never fire.
 * Now a failure throws with the server's reason; set NEXT_PUBLIC_ADMIN_DEMO=true
 * to browse sample data on purpose (the demo banner then says so).
 */
const DEMO_MODE = process.env.NEXT_PUBLIC_ADMIN_DEMO === "true";

/** Shared by every backend call, including the components that fetch directly. */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  return fetch(`${BASE}${path}`, {
    ...init,
    headers: { ...headers, ...(init.headers as Record<string, string> | undefined) },
    credentials: "same-origin",
    cache: "no-store",
    signal: init.signal ?? AbortSignal.timeout(25000),
  });
}

/** The server's own reason ({"detail": ...}) when there is one, else the status. */
async function failureReason(res: Response): Promise<string> {
  const text = await res.text().catch(() => "");
  try {
    const body = JSON.parse(text) as { detail?: unknown; error?: unknown };
    const d = body.detail ?? body.error;
    if (d) return `${path(res)} — HTTP ${res.status}: ${typeof d === "string" ? d : JSON.stringify(d)}`;
  } catch { /* not JSON */ }
  return `${path(res)} — HTTP ${res.status}${text ? `: ${text.slice(0, 200)}` : ""}`;
}

function path(res: Response): string {
  try { return new URL(res.url).pathname.replace(BASE, ""); } catch { return res.url; }
}

async function tryFetchJSON<T>(p: string, fallback: T): Promise<T> {
  if (DEMO_MODE) {
    noteDemo("api", "NEXT_PUBLIC_ADMIN_DEMO=true — sample data", fallback);
    return fallback;
  }
  const res = await apiFetch(p);
  if (!res.ok) throw new Error(await failureReason(res));
  clearDemo("api");
  return res.json() as Promise<T>;
}

/**
 * Unwrap `{ <key>: [...] }` and FAIL if the shape is not that. /admin/models
 * returns {"models": [...]} and /admin/worker-health {"workers": [...], ...},
 * but both were typed as bare arrays — a cast, not a check. Hidden while every
 * request fell back to demo arrays; the first real response crashed ML Models
 * ("models.map is not a function") and took the whole page down (2026-09-27).
 */
async function fetchList<T>(p: string, key: string, fallback: T[]): Promise<T[]> {
  const body = await tryFetchJSON<unknown>(p, { [key]: fallback });
  const list = Array.isArray(body) ? body : (body as Record<string, unknown> | null)?.[key];
  if (!Array.isArray(list)) {
    throw new Error(`${p} — unexpected response shape: expected an array under "${key}"`);
  }
  return list as T[];
}

export function isUsingDemoData(): boolean {
  return DEMO_MODE || isDemoSource("api");
}

/** Which endpoint failed, for the banner to name rather than hand-wave. */
export function getApiDemoReason(): string | null {
  return getDemoReason("api");
}

// ─── Time helpers for demo data ─────────────────────────────────────────────

function minutesAgo(m: number): string { return new Date(Date.now() - m * 60000).toISOString(); }
function hoursAgo(h: number): string { return new Date(Date.now() - h * 3600000).toISOString(); }
function daysAgo(d: number): string { return new Date(Date.now() - d * 86400000).toISOString(); }

// ─── Dashboard Stats ─────────────────────────────────────────────────────────

export interface DashboardStats {
  version: string;
  dev_mode: boolean;
  db_enabled: boolean;
  db_status: string;
  timestamp: string;
  total_users: number;
  recent_signups: number;
  subscriptions: Record<string, number>;
  active_mandates: number;
  total_items: number;
  total_events: number;
  beta_signups: number;
  catalog_suggestions_pending: number;
  catalog_suggestions_mapped_week: number;
  category_candidates_watching: number;
  category_candidates_candidate: number;
  db_error?: string;
}

function getDemoStats(): DashboardStats {
  return {
    version: "2.4.1", dev_mode: false, db_enabled: true, db_status: "connected",
    timestamp: new Date().toISOString(),
    total_users: 2847, recent_signups: 156,
    subscriptions: { free: 2103, pro: 584, premium: 160 },
    active_mandates: 744, total_items: 187432, total_events: 342,
    beta_signups: 89,
    catalog_suggestions_pending: 47, catalog_suggestions_mapped_week: 23,
    category_candidates_watching: 8, category_candidates_candidate: 3,
  };
}

export function fetchDashboardStats(): Promise<DashboardStats> {
  return tryFetchJSON("/ops/dashboard/stats", getDemoStats());
}

// ─── Users ───────────────────────────────────────────────────────────────────

export interface UserRow {
  id: string;
  email: string;
  created_at: string | null;
  plan: string;
  sub_status: string;
  mandate_count: number;
  item_count: number;
}

export interface UsersResponse {
  users: UserRow[];
  total: number;
  page: number;
  per_page?: number;
  error?: string;
}

function getDemoUsers(): UsersResponse {
  return {
    users: Array.from({ length: 12 }, (_, i) => ({
      id: `demo-${i}`, email: `user${i + 1}@example.com`,
      created_at: new Date(Date.now() - (i * 3 * 86400000)).toISOString(),
      plan: ["free","free","free","pro","pro","premium","free","pro","free","free","pro","premium"][i],
      sub_status: ["active","active","active","active","active","active","canceled","active","active","past_due","active","active"][i],
      mandate_count: i % 3, item_count: 20 + i * 15,
    })),
    total: 12, page: 1,
  };
}

export function fetchUsers(page = 1, perPage = 50): Promise<UsersResponse> {
  return tryFetchJSON(`/ops/dashboard/users?page=${page}&per_page=${perPage}`, getDemoUsers());
}

// ─── Worker Health ───────────────────────────────────────────────────────────

export interface WorkerStatus {
  name: string;
  last_run_at: string | null;
  last_status: string;
  run_count: number;
  average_duration_s: number | null; // null = no run since the restart
  /** "disabled" (2026-09-27): in SCHEDULES but deliberately not started by the
   *  bake orchestrator. Those 15 used to be reported as "never_run". */
  status: "ok" | "overdue" | "never_run" | "on_demand" | "disabled";
  minutes_overdue: number;
  expected_interval_minutes: number;
}

function getDemoWorkers(): WorkerStatus[] {
  return [
    { name: "price_prediction_worker", last_run_at: minutesAgo(3), last_status: "ok", run_count: 14820, average_duration_s: 2.1, status: "ok", minutes_overdue: 0, expected_interval_minutes: 5 },
    { name: "catalog_crawler_worker", last_run_at: minutesAgo(45), last_status: "ok", run_count: 892, average_duration_s: 38.4, status: "ok", minutes_overdue: 0, expected_interval_minutes: 60 },
    { name: "marketplace_refresh_worker", last_run_at: minutesAgo(12), last_status: "ok", run_count: 4210, average_duration_s: 5.7, status: "ok", minutes_overdue: 0, expected_interval_minutes: 15 },
    { name: "auction_alert_worker", last_run_at: minutesAgo(2), last_status: "ok", run_count: 28440, average_duration_s: 1.3, status: "ok", minutes_overdue: 0, expected_interval_minutes: 5 },
    { name: "watchlist_calibration_worker", last_run_at: minutesAgo(118), last_status: "ok", run_count: 720, average_duration_s: 12.5, status: "overdue", minutes_overdue: 58, expected_interval_minutes: 60 },
    { name: "event_scraper_scheduler", last_run_at: hoursAgo(5), last_status: "ok", run_count: 124, average_duration_s: 142.0, status: "ok", minutes_overdue: 0, expected_interval_minutes: 360 },
    { name: "notification_digest_worker", last_run_at: hoursAgo(1), last_status: "ok", run_count: 1680, average_duration_s: 3.8, status: "ok", minutes_overdue: 0, expected_interval_minutes: 60 },
    { name: "model_retrain_worker", last_run_at: hoursAgo(23), last_status: "ok", run_count: 52, average_duration_s: 320.0, status: "ok", minutes_overdue: 0, expected_interval_minutes: 1440 },
    { name: "adapter_health_worker", last_run_at: minutesAgo(28), last_status: "ok", run_count: 2880, average_duration_s: 8.2, status: "ok", minutes_overdue: 0, expected_interval_minutes: 30 },
    { name: "deal_completion_worker", last_run_at: minutesAgo(8), last_status: "ok", run_count: 8640, average_duration_s: 1.9, status: "ok", minutes_overdue: 0, expected_interval_minutes: 10 },
    { name: "scarcity_score_worker", last_run_at: hoursAgo(3), last_status: "ok", run_count: 480, average_duration_s: 45.2, status: "ok", minutes_overdue: 0, expected_interval_minutes: 360 },
    { name: "leaderboard_refresh_worker", last_run_at: minutesAgo(14), last_status: "ok", run_count: 4320, average_duration_s: 2.4, status: "ok", minutes_overdue: 0, expected_interval_minutes: 15 },
    { name: "push_token_cleanup_worker", last_run_at: hoursAgo(23), last_status: "ok", run_count: 365, average_duration_s: 0.5, status: "ok", minutes_overdue: 0, expected_interval_minutes: 1440 },
    { name: "stale_listing_worker", last_run_at: hoursAgo(6), last_status: "ok", run_count: 240, average_duration_s: 18.7, status: "ok", minutes_overdue: 0, expected_interval_minutes: 720 },
    { name: "currency_fx_worker", last_run_at: hoursAgo(2), last_status: "ok", run_count: 1440, average_duration_s: 1.1, status: "ok", minutes_overdue: 0, expected_interval_minutes: 180 },
    { name: "data_moat_export_worker", last_run_at: null, last_status: "never", run_count: 0, average_duration_s: 0, status: "on_demand", minutes_overdue: 0, expected_interval_minutes: 0 },
    { name: "catalog_candidate_worker", last_run_at: hoursAgo(12), last_status: "ok", run_count: 60, average_duration_s: 85.0, status: "ok", minutes_overdue: 0, expected_interval_minutes: 720 },
    { name: "miss_capture_worker", last_run_at: minutesAgo(55), last_status: "ok", run_count: 1440, average_duration_s: 4.2, status: "ok", minutes_overdue: 0, expected_interval_minutes: 60 },
    { name: "demand_signal_worker", last_run_at: null, last_status: "never", run_count: 0, average_duration_s: 0, status: "never_run", minutes_overdue: 0, expected_interval_minutes: 360 },
  ];
}

export function fetchWorkerHealth(): Promise<WorkerStatus[]> {
  return fetchList<WorkerStatus>("/admin/worker-health", "workers", getDemoWorkers());
}

// ─── Demand Signals ──────────────────────────────────────────────────────────

export interface DemandItem {
  name: string;
  suggested_category: string;
  total_requests: number;
  unique_users: number;
  last_requested: string | null;
}

export interface DemandCategory {
  name: string;
  slug: string;
  signal_count: number;
  unique_users: number;
  status: string;
  first_seen: string | null;
  last_seen: string | null;
}

export interface DemandDailyCount {
  day: string;
  requests: number;
  unique_users: number;
}

export interface DemandSummary {
  pending_suggestions: number;
  new_categories_watching: number;
  top_requested_items: DemandItem[];
  top_requested_categories: DemandCategory[];
  daily_request_counts: DemandDailyCount[];
}

function getDemoDemand(): DemandSummary {
  return {
    pending_suggestions: 47, new_categories_watching: 8,
    top_requested_items: [
      { name: "Charizard VMAX Alt Art", suggested_category: "pokemon_tcg", total_requests: 89, unique_users: 67, last_requested: daysAgo(0) },
      { name: "Air Jordan 1 Retro High OG", suggested_category: "sneakers", total_requests: 72, unique_users: 54, last_requested: daysAgo(1) },
      { name: "Black Lotus (Beta)", suggested_category: "mtg", total_requests: 45, unique_users: 38, last_requested: daysAgo(0) },
      { name: "Funko Pop! Freddy Funko", suggested_category: "funko", total_requests: 41, unique_users: 33, last_requested: daysAgo(2) },
      { name: "Rolex Submariner 126610LN", suggested_category: "watches", total_requests: 38, unique_users: 29, last_requested: daysAgo(1) },
    ],
    top_requested_categories: [
      { name: "Board Games", slug: "board_games", signal_count: 234, unique_users: 142, status: "watching", first_seen: daysAgo(45), last_seen: daysAgo(0) },
      { name: "Sports Memorabilia", slug: "sports_memorabilia", signal_count: 189, unique_users: 118, status: "candidate", first_seen: daysAgo(30), last_seen: daysAgo(1) },
      { name: "Coins & Banknotes", slug: "numismatics", signal_count: 156, unique_users: 95, status: "watching", first_seen: daysAgo(60), last_seen: daysAgo(2) },
      { name: "Art Prints", slug: "art_prints", signal_count: 98, unique_users: 72, status: "watching", first_seen: daysAgo(20), last_seen: daysAgo(3) },
      { name: "Model Trains", slug: "model_trains", signal_count: 67, unique_users: 41, status: "rejected", first_seen: daysAgo(90), last_seen: daysAgo(15) },
    ],
    daily_request_counts: Array.from({ length: 7 }, (_, i) => ({
      day: new Date(Date.now() - (6 - i) * 86400000).toISOString().slice(0, 10),
      requests: 20 + ((i * 7 + 13) % 40),
      unique_users: 10 + ((i * 5 + 7) % 25),
    })),
  };
}

export function fetchDemandSummary(): Promise<DemandSummary> {
  return tryFetchJSON("/admin/demand-summary", getDemoDemand());
}

// ─── Intelligence Summary (real /intelligence/* aggregation) ─────────────────

export interface IntelSummary {
  days: number;
  top_searches: { query: string; category: string; searches: number; unique_users: number }[];
  no_results_searches: { query: string; searches: number; unique_users: number }[];
  top_watchlists: { title: string; category: string; watchers: number; unique_users: number; avg_target: number | null }[];
  top_events: { event_id: string; title: string | null; category_id: string | null; starts_at: string | null; engagement_score: number }[];
  top_regret_categories: { category: string; regret_rate_30d: number | null; items_added: number; items_regretted: number; computed_at: string | null }[];
  top_affiliates: { source: string; category: string; clicks: number; unique_users: number }[];
  top_paywall_rejections: { feature: string; views: number; dismissals: number; unique_users: number }[];
  sources: { source: string; rows: number; latest: string | null }[];
}

function getDemoIntelSummary(): IntelSummary {
  return {
    days: 14,
    top_searches: [
      { query: "charizard base set", category: "pokemon", searches: 47, unique_users: 38 },
      { query: "rolex submariner", category: "watches", searches: 22, unique_users: 18 },
      { query: "black lotus", category: "mtg", searches: 18, unique_users: 15 },
    ],
    no_results_searches: [
      { query: "vintage transformers g1", searches: 8, unique_users: 7 },
      { query: "1986 rookie cards", searches: 5, unique_users: 4 },
    ],
    top_watchlists: [
      { title: "Charizard VMAX Alt Art", category: "pokemon", watchers: 34, unique_users: 31, avg_target: 1450 },
      { title: "Air Jordan 1 Retro High OG", category: "sneakers", watchers: 28, unique_users: 25, avg_target: 220 },
    ],
    top_events: [
      { event_id: "demo-1", title: "Magic: The Gathering Pro Tour", category_id: "mtg", starts_at: daysAgo(-7), engagement_score: 184 },
      { event_id: "demo-2", title: "Funko HQ Grand Opening", category_id: "funko", starts_at: daysAgo(-3), engagement_score: 92 },
    ],
    top_regret_categories: [
      { category: "designer_toys", regret_rate_30d: 0.18, items_added: 22, items_regretted: 4, computed_at: minutesAgo(30) },
      { category: "anime_figures", regret_rate_30d: 0.12, items_added: 41, items_regretted: 5, computed_at: minutesAgo(30) },
    ],
    top_affiliates: [
      { source: "ebay", category: "pokemon", clicks: 47, unique_users: 38 },
      { source: "tcgplayer", category: "mtg", clicks: 22, unique_users: 18 },
    ],
    top_paywall_rejections: [
      { feature: "deal_desk_pro", views: 38, dismissals: 31, unique_users: 24 },
      { feature: "advanced_analytics", views: 22, dismissals: 18, unique_users: 16 },
    ],
    sources: [
      { source: "demand_signals", rows: 1247, latest: minutesAgo(5) },
      { source: "watchlist_items", rows: 89, latest: hoursAgo(2) },
      { source: "notification_impressions", rows: 412, latest: minutesAgo(15) },
      { source: "notification_interactions", rows: 87, latest: minutesAgo(15) },
      { source: "notification_outcomes", rows: 12, latest: hoursAgo(1) },
    ],
  };
}

export function fetchIntelSummary(days = 14): Promise<IntelSummary> {
  return tryFetchJSON(`/ops/dashboard/intel-summary?days=${days}`, getDemoIntelSummary());
}

// ─── Sponsor Analytics ───────────────────────────────────────────────────────

export interface SponsoredEvent {
  id: string;
  title: string;
  sponsor_name: string;
  sponsor_tier: string | null;
  category_id: string | null;
  sponsor_paid_at: string | null;
  sponsor_expires_at: string | null;
  impressions: number;
  clicks: number;
  rsvps: number;
}

export interface SponsorAnalyticsResponse {
  sponsored_events: SponsoredEvent[];
  total: number;
}

function getDemoSponsors(): SponsorAnalyticsResponse {
  return {
    sponsored_events: [
      { id: "sp-1", title: "Pokemon TCG Championship Series", sponsor_name: "PokeCollect Pro", sponsor_tier: "gold", category_id: "pokemon_tcg", sponsor_paid_at: daysAgo(30), sponsor_expires_at: daysAgo(-60), impressions: 24500, clicks: 1840, rsvps: 312 },
      { id: "sp-2", title: "Sneaker Drop Preview Night", sponsor_name: "KickCheck", sponsor_tier: "silver", category_id: "sneakers", sponsor_paid_at: daysAgo(15), sponsor_expires_at: daysAgo(-45), impressions: 18200, clicks: 1250, rsvps: 189 },
      { id: "sp-3", title: "Vintage Watch Fair 2026", sponsor_name: "ChronoVault", sponsor_tier: "gold", category_id: "watches", sponsor_paid_at: daysAgo(7), sponsor_expires_at: daysAgo(-90), impressions: 31200, clicks: 2100, rsvps: 445 },
      { id: "sp-4", title: "Funko Swap Meet", sponsor_name: "PopKing", sponsor_tier: "bronze", category_id: "funko", sponsor_paid_at: daysAgo(20), sponsor_expires_at: daysAgo(-10), impressions: 8900, clicks: 620, rsvps: 87 },
      { id: "sp-5", title: "MTG Draft Night Series", sponsor_name: "CardVault", sponsor_tier: "silver", category_id: "mtg", sponsor_paid_at: daysAgo(5), sponsor_expires_at: daysAgo(-55), impressions: 15400, clicks: 980, rsvps: 156 },
    ],
    total: 5,
  };
}

export function fetchSponsorAnalytics(): Promise<SponsorAnalyticsResponse> {
  return tryFetchJSON("/ops/dashboard/sponsor-analytics", getDemoSponsors());
}

// ─── ML Models ───────────────────────────────────────────────────────────────

/** One SERVED model — `artifacts/<category>/active/model.json` on the API
 *  server — plus its last retrain decision (model_promotion_log).
 *  Until 2026-09-27 this tab read model_metrics / model_registry: dead CLIP
 *  rows from April and test rows, not the models serving uses. */
export interface ModelRow {
  category: string;
  version: string;
  model_type: string | null;
  fitted_at: string;
  age_days: number;
  train_size: number | null;
  /** Cross-validated error at training time. In LOG-price units when log_scale. */
  cv_mae: number | null;
  log_scale: boolean;
  versions_on_disk: number;
  last_decision: {
    promoted: boolean | null;
    holdout_n: number | null;
    old_mae: number | null;
    new_mae: number | null;
    reason: string | null;
    at: string | null;
  } | null;
}

export interface ModelSummary {
  root: string | null;
  models: ModelRow[];
  /** Category folders with no resolvable active model — listed, not hidden. */
  unresolved: string[];
  promotion_error: string | null;
}

export interface CountsRow {
  category: string;
  model_version: string;
  day: string;
  n: number;
}

export interface MetricsResponse {
  counts_7d: CountsRow[];
  warming?: boolean;
  stale?: boolean;
  detail?: string;
}

function getDemoModelSummary(): ModelSummary {
  const fitted = new Date(Date.now() - 2 * 86400000).toISOString();
  return {
    root: "(demo)",
    unresolved: [],
    promotion_error: null,
    models: ["pokemon", "mtg", "funko", "lego"].map((category, i) => ({
      category, version: "20260101_000000", model_type: "ridge_v2", fitted_at: fitted, age_days: 2,
      train_size: 1000 * (i + 1), cv_mae: 0.8 + i / 10, log_scale: true, versions_on_disk: 2,
      last_decision: { promoted: true, holdout_n: 0, old_mae: null, new_mae: null, reason: "demo", at: fitted },
    })),
  };
}

function getDemoMetrics(): MetricsResponse {
  const day = new Date().toISOString().slice(0, 10);
  return {
    counts_7d: ["pokemon", "mtg", "funko", "lego"].map((category, i) => ({
      category, model_version: "", day, n: 300 - i * 50,
    })),
  };
}

export async function fetchModelSummary(): Promise<ModelSummary> {
  const body = await tryFetchJSON<ModelSummary>("/admin/models", getDemoModelSummary());
  if (!body || !Array.isArray(body.models)) {
    throw new Error("/admin/models — unexpected response shape: expected { models: [...] }");
  }
  return body;
}

export function fetchMetrics(): Promise<MetricsResponse> {
  return tryFetchJSON("/admin/metrics", getDemoMetrics());
}




// ─── API availability check ─────────────────────────────────────────────────

