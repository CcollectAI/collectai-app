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

async function fetchJSON<T = unknown>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: headers() });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function postJSON<T = unknown>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "POST", headers: headers() });
  const text = await res.text();
  if (!res.ok) throw new Error(text || `${res.status} ${res.statusText}`);
  try { return JSON.parse(text); } catch { return { ok: true, raw: text } as T; }
}

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

export function fetchDashboardStats(): Promise<DashboardStats> {
  return fetchJSON("/ops/dashboard/stats");
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

export function fetchUsers(page = 1, perPage = 50): Promise<UsersResponse> {
  return fetchJSON(`/ops/dashboard/users?page=${page}&per_page=${perPage}`);
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

export function fetchWorkerHealth(): Promise<WorkerStatus[]> {
  return fetchJSON("/admin/worker-health");
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

export function fetchDemandSummary(): Promise<DemandSummary> {
  return fetchJSON("/admin/demand-summary");
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

export function fetchSponsorAnalytics(): Promise<SponsorAnalyticsResponse> {
  return fetchJSON("/ops/dashboard/sponsor-analytics");
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

export function fetchModels(): Promise<ModelRow[]> {
  return fetchJSON("/admin/models");
}

export function fetchMetrics(): Promise<MetricsResponse> {
  return fetchJSON("/admin/metrics");
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
