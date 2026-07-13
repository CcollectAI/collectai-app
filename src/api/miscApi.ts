/**
 * Miscellaneous API methods: barcode, geo, FX, feedback, build-paint, task queue,
 * watchlist, insights, export, account, billing, activity, search, quickscan feedback.
 */
import { get, post, del, patch, postMultipart } from "./httpClient";
import { API_BASE } from "./httpClient";
import type { CurrencyCode } from "@/data/types";
import type { BillingStatus, IntakeResultResponse, NotificationHistoryResponse } from "./types";

// Watchlist
export const fetchWatchlist = () => get("/watchlist/mine");
// DO NOT call this directly from screens — use dataProvider.addWatchlistItem.
// The server contract (WatchlistCreate) reads `name`, NOT `title`; calling
// this raw helper with `{title}` silently stores a junk row title. That bug
// shipped twice (watchlistProvider 2026-04-30, catalog museum 2026-06-05) —
// the provider does the field mapping and cache invalidation.
export const addToWatchlist = (p: Record<string, unknown>) => post("/watchlist/mine", p);

// Insights (duplicated entries in collectorsApi object)
export const fetchInsights = () => get("/insights/personalized");
export const fetchHomeWidget = () => get("/insights/home-widget");
export const getPersonalizedInsights = () => get("/insights/personalized");
export const getHomeWidget = () => get("/insights/home-widget");

// Feedback
export const submitFeedback = (payload: {
  item_id: string;
  feedback_type: string;
  value?: string;
  notes?: string;
}) => post("/feedback/submit", payload);

export const submitCorrection = (payload: {
  item_id: string;
  corrected_price?: number;
  corrected_condition?: string;
  corrected_category?: string;
  notes?: string;
}) => post("/feedback/correction", payload);

// Barcode / Market Data
export const lookupByBarcode = (barcode: string, codeType?: string) =>
  post("/barcode/lookup", { barcode, code_type: codeType });

// FX rates (public, no auth)
export const getFxRates = () => get<{
  base: string;
  rates: Record<string, number>;
  rates_from_eur: Record<string, number>;
}>("/fx/rates");

// Geolocation (no auth required — called during onboarding)
export const detectRegion = () =>
  get<{
    region: string;
    currency: CurrencyCode;
    country_code: string | null;
  }>("/geo/detect");

// Items Export — returns the canonical 12-col CSV inline.
// Matches /api/imports/template so users can export, edit in
// Excel/Numbers, and re-import without column drift.
//
// Currency: defaults to user_settings.currency. Pass `?currency=USD`
// (etc.) to override. estimated_value is FX-converted; purchase_price
// stays in its own purchase_currency (historical purchase price).
export const exportItemsOverview = (currency?: string) =>
  get<{ download_url: string | null; csv_inline: string }>(
    `/items-export/overview${currency ? `?currency=${encodeURIComponent(currency)}` : ""}`,
  );

// Items Export — comprehensive 30-col inventory snapshot.
// NOT round-trip with import (extra columns won't survive re-import).
// Use for insurance, accountants, full collection records. Surfaces
// brand/set/rarity from attrs, q10/q90 price range, ownership flags
// (for_sale, asking_price), collection grouping, timestamps. Photo URLs
// intentionally excluded per product decision.
export const exportItemsFull = (currency?: string) =>
  get<{ download_url: string | null; csv_inline: string }>(
    `/items-export/full${currency ? `?currency=${encodeURIComponent(currency)}` : ""}`,
  );

// Insurance Valuation Export
export const getInsuranceReportUrl = (format: 'html' | 'json' = 'html', currency?: string) => {
  const params = new URLSearchParams({ format });
  if (currency) params.set('currency', currency);
  return `${API_BASE}/export/insurance-report?${params.toString()}`;
};

// Build & Paint Step Templates
export const getStepTemplates = (categoryId?: string) =>
  get(`/build-paint/step-templates${categoryId ? `/${encodeURIComponent(categoryId)}` : ""}`);

// Task Queue
export const enqueueTask = (payload: { task_type: string; payload?: Record<string, unknown> }) =>
  post("/tasks/enqueue", payload as Record<string, unknown>);

export const getTaskStatus = (taskId: string) =>
  get(`/tasks/${encodeURIComponent(taskId)}/status`);

// Verified Sales (Ground Truth)
export const submitVerifiedSale = (payload: {
  item_id: string;
  sale_price: number;
  currency?: string;
  sale_date?: string;
  marketplace?: string;
}) => post("/feedback/verified-sale", payload as Record<string, unknown>);

export const listVerifiedSales = () =>
  get("/feedback/verified-sales");

// Trends & Deep-Dive
export const getCollectionTrends = (days = 30) =>
  get(`/analytics/collection/trends?days=${days}`);

// Served from a server-side cache that a background warmer keeps primed, so
// this is normally a ~ms response. A cold miss (e.g. a category not yet warmed
// after a backend restart) runs a heavy aggregation that can take 10s+, so use
// a longer-than-default timeout to let Market Insights load rather than failing
// silently at the 5s default.
export const getCategoryDeepDive = (categoryId: string) =>
  get(`/analytics/categories/${encodeURIComponent(categoryId)}/deep-dive`, { timeoutMs: 20_000 });

export const getItemTrends = (itemId: string) =>
  get(`/analytics/items/${encodeURIComponent(itemId)}/trends`);

// Account Management
// Backend requires ?confirm=DELETE_MY_ACCOUNT to guard against accidental
// destructive calls. The FE confirms via a typed-confirmation modal in
// ProfileEditSection before invoking this.
export async function deleteAccount(): Promise<{ success: boolean; message: string }> {
  return del("/account?confirm=DELETE_MY_ACCOUNT");
}

// Billing / Subscriptions
export async function getBillingStatus(): Promise<BillingStatus> {
  return get("/billing/status");
}

export async function createCheckoutSession(plan: "pro" | "premium"): Promise<{ url: string; session_id: string }> {
  return post("/billing/checkout-session", { plan });
}

export async function createPortalSession(): Promise<{ url: string }> {
  return post("/billing/portal-session", {});
}

// Activity Feed
export async function getUserActivity(userId: string, limit = 20, offset = 0) {
  return get(`/activity/${userId}?limit=${limit}&offset=${offset}`);
}

export async function logActivity(payload: {
  activity_type: string;
  title: string;
  description?: string;
  metadata?: Record<string, unknown>;
  is_public?: boolean;
}) {
  return post("/activity/log", payload);
}

// Unified Search
export async function unifiedSearch(q: string, limit = 5) {
  return get(`/search/unified?q=${encodeURIComponent(q)}&limit=${limit}`);
}

// Event Search
export async function searchEvents(params: {
  q?: string;
  category?: string;
  eventType?: string;
  location?: string;
  upcomingOnly?: boolean;
  limit?: number;
  offset?: number;
}) {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.category) sp.set("category", params.category);
  if (params.eventType) sp.set("event_type", params.eventType);
  if (params.location) sp.set("location", params.location);
  if (params.upcomingOnly !== undefined) sp.set("upcoming_only", String(params.upcomingOnly));
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.offset) sp.set("offset", String(params.offset));
  return get(`/events/search?${sp.toString()}`);
}

// QuickScan feedback & multi-detect

type FeedbackApiResponse = {
  id: string;
  accepted: boolean;
  retrain_flagged: boolean;
};

export async function submitScanFeedback(feedback: {
  scanSessionId: string;
  correctedName?: string;
  correctedCategory?: string;
  correctedCondition?: string;
}): Promise<{ id: string; accepted: boolean; retrainFlagged: boolean }> {
  const resp = await post<FeedbackApiResponse>("/intake/feedback", {
    scan_session_id: feedback.scanSessionId,
    corrected_name: feedback.correctedName,
    corrected_category: feedback.correctedCategory,
    corrected_condition: feedback.correctedCondition,
  });
  return {
    id: resp.id,
    accepted: resp.accepted,
    retrainFlagged: resp.retrain_flagged,
  };
}

type MultiDetectApiResponse = {
  items: {
    item_index: number;
    bounding_box: { x: number; y: number; w: number; h: number };
    category_hint: string | null;
    suggested_name: string | null;
    confidence: number;
  }[];
  total_detected: number;
};

export async function multiDetect(
  imageUri: string,
): Promise<{
  items: {
    itemIndex: number;
    boundingBox: { x: number; y: number; w: number; h: number };
    categoryHint: string | null;
    suggestedName: string | null;
    confidence: number;
  }[];
  totalDetected: number;
}> {
  const form = new FormData();
  form.append("file", {
    uri: imageUri,
    type: "image/jpeg",
    name: "multi.jpg",
  } as any);
  const resp = await postMultipart<MultiDetectApiResponse>("/intake/multi-detect", form);
  return {
    items: (resp.items || []).map((i) => ({
      itemIndex: i.item_index,
      boundingBox: i.bounding_box || { x: 0, y: 0, w: 1, h: 1 },
      categoryHint: i.category_hint,
      suggestedName: i.suggested_name,
      confidence: i.confidence || 0,
    })),
    totalDetected: resp.total_detected || 0,
  };
}

// Value Summary (retention notification)
export type ValueSummaryData = {
  total_scans: number;
  total_items_tracked: number;
  total_alerts_triggered: number;
  duplicates_prevented: number;
  hours_saved: number;
  deal_savings: number;
  deal_count: number;
  smart_buy_savings: number;
  smart_buy_count: number;
  total_money_saved: number;
  best_find_name: string | null;
  best_find_category: string | null;
  best_find_value: number;
  best_find_saved: number;
  member_since: string | null;
  days_as_member: number;
  currency: string;
  top_smart_buys: {
    item_name: string;
    category: string;
    purchase_price: number;
    market_value: number;
    saved: number;
  }[];
};

export const getValueSummary = () => get<ValueSummaryData>("/value-summary");
