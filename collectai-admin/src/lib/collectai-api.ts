// ---------------------------------------------------------------------------
// CollectAI Backend API Client
// Connects to the FastAPI backend for admin data
// ---------------------------------------------------------------------------

import { APP_CONFIG } from "../../admin.config";

const BASE = APP_CONFIG.api.baseUrl;

function headers(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (APP_CONFIG.api.opsKey) h["X-Ops-Key"] = APP_CONFIG.api.opsKey;
  if (APP_CONFIG.api.adminSecret) h["x-admin-secret"] = APP_CONFIG.api.adminSecret;
  return h;
}

// ─── Demo-aware fetch helper ────────────────────────────────────────────────

let _apiAvailable: boolean | null = null;

async function tryFetchJSON<T>(path: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(`${BASE}${path}`, { headers: headers(), signal: AbortSignal.timeout(5000) });
    if (!res.ok) throw new Error(`${res.status}`);
    _apiAvailable = true;
    return res.json();
  } catch (err) {
    _apiAvailable = false;
    // Surface the fallback so admin users can tell when they're looking at demo data
    // (consumed via isUsingDemoData() in components — wire a banner where useful).
    // eslint-disable-next-line no-console
    console.warn(`[collectai-api] using demo fallback for ${path}:`, err);
    return fallback;
  }
}

export function isUsingDemoData(): boolean {
  return _apiAvailable === false;
}

async function postJSON<T = unknown>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "POST", headers: headers() });
  const text = await res.text();
  if (!res.ok) throw new Error(text || `${res.status} ${res.statusText}`);
  try { return JSON.parse(text); } catch { return { ok: true, raw: text } as T; }
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
  average_duration_s: number;
  status: "ok" | "overdue" | "never_run" | "on_demand";
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
  return tryFetchJSON("/admin/worker-health", getDemoWorkers());
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

export interface ModelRow {
  category: string;
  version: string;
  status: string;
  artifact_uri?: string;
}

export interface MaeRow {
  category: string;
  model_version: string;
  mae: number | null;
  n: number;
}

export interface CountsRow {
  category: string;
  model_version: string;
  day: string;
  n: number;
}

export interface MetricsResponse {
  counts_7d: CountsRow[];
  mae: MaeRow[];
}

const DEMO_MODELS: readonly ModelRow[] = [
  { category: "pokemon_tcg", version: "v2.3", status: "active" },
  { category: "mtg", version: "v2.1", status: "active" },
  { category: "funko", version: "v2.2", status: "active" },
  { category: "sneakers", version: "v2.0", status: "active" },
  { category: "watches", version: "v1.8", status: "active" },
  { category: "lego", version: "v2.1", status: "active" },
  { category: "vinyl", version: "v1.9", status: "active" },
  { category: "hot_toys", version: "v1.7", status: "active" },
  { category: "warhammer", version: "v2.0", status: "active" },
  { category: "yugioh", version: "v1.6", status: "active" },
  { category: "kpop", version: "v1.5", status: "active" },
  { category: "anime_figures", version: "v1.4", status: "active" },
];

function getDemoMetrics(): MetricsResponse {
  const today = new Date().toISOString().slice(0, 10);
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  return {
    counts_7d: [
      { category: "pokemon_tcg", model_version: "v2.3", day: today, n: 342 },
      { category: "pokemon_tcg", model_version: "v2.3", day: yesterday, n: 318 },
      { category: "mtg", model_version: "v2.1", day: today, n: 215 },
      { category: "funko", model_version: "v2.2", day: today, n: 187 },
      { category: "sneakers", model_version: "v2.0", day: today, n: 156 },
      { category: "watches", model_version: "v1.8", day: today, n: 134 },
      { category: "lego", model_version: "v2.1", day: today, n: 112 },
      { category: "vinyl", model_version: "v1.9", day: today, n: 98 },
      { category: "hot_toys", model_version: "v1.7", day: today, n: 67 },
      { category: "warhammer", model_version: "v2.0", day: today, n: 89 },
      { category: "yugioh", model_version: "v1.6", day: today, n: 145 },
      { category: "kpop", model_version: "v1.5", day: today, n: 76 },
    ],
    mae: [
      { category: "pokemon_tcg", model_version: "v2.3", mae: 12.4, n: 1850 },
      { category: "mtg", model_version: "v2.1", mae: 18.7, n: 1200 },
      { category: "funko", model_version: "v2.2", mae: 8.2, n: 980 },
      { category: "sneakers", model_version: "v2.0", mae: 22.1, n: 870 },
      { category: "watches", model_version: "v1.8", mae: 145.3, n: 620 },
      { category: "lego", model_version: "v2.1", mae: 11.8, n: 750 },
      { category: "vinyl", model_version: "v1.9", mae: 6.3, n: 540 },
      { category: "hot_toys", model_version: "v1.7", mae: 35.6, n: 380 },
      { category: "warhammer", model_version: "v2.0", mae: 14.9, n: 450 },
      { category: "yugioh", model_version: "v1.6", mae: 9.1, n: 680 },
      { category: "kpop", model_version: "v1.5", mae: 7.8, n: 420 },
      { category: "anime_figures", model_version: "v1.4", mae: 19.5, n: 310 },
    ],
  };
}

export function fetchModels(): Promise<ModelRow[]> {
  return tryFetchJSON("/admin/models", [...DEMO_MODELS]);
}

export function fetchMetrics(): Promise<MetricsResponse> {
  return tryFetchJSON("/admin/metrics", getDemoMetrics());
}

export function activateBest(category: string) {
  return postJSON(`/admin/activate_best?category=${encodeURIComponent(category)}`);
}

export function reloadCategory(category: string) {
  return postJSON(`/admin/reload?category=${encodeURIComponent(category)}`);
}

export function trainNow(category?: string) {
  const q = category
    ? `?category=${encodeURIComponent(category)}&min_rows=150`
    : "?min_rows=150";
  return postJSON(`/admin/train_now${q}`);
}

// ─── API availability check ─────────────────────────────────────────────────

export async function isApiAvailable(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/health`, { signal: AbortSignal.timeout(5000) });
    return res.ok;
  } catch {
    return false;
  }
}
