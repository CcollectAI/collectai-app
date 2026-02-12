import { API_BASE_URL, API_KEY } from '@/config/api';

export interface PortfolioOverview {
  total_value: number;
  currency: string;
  change_1d?: number;
  change_7d?: number;
  change_30d?: number;
  [key: string]: unknown;
}

export interface PortfolioItem {
  id: string;
  name: string;
  category: string;
  estimated_value: number;
  image_url?: string;
  change_1d?: number;
  change_7d?: number;
  change_30d?: number;
  [key: string]: unknown;
}

export interface PortfolioTimeseriesPoint {
  t: string; // ISO timestamp or date label
  value: number;
  [key: string]: unknown;
}

export interface PortfolioTimeseriesResponse {
  range: string;
  points: PortfolioTimeseriesPoint[];
  [key: string]: unknown;
}

export interface ScanAndAddPayload {
  source?: 'portfolio' | 'watchlist' | string;
  name?: string;
  category?: string;
  estimated_value?: number;
  notes?: string;
  image_base64?: string;
  [key: string]: unknown;
}

export interface ScanAndAddResult {
  success?: boolean;
  item?: PortfolioItem;
  [key: string]: unknown;
}

export interface MarketplaceListing {
  id: string;
  title: string;
  price: number;
  currency?: string;
  category?: string;
  image_url?: string;
  [key: string]: unknown;
}

export interface EvalSummary {
  updated_at?: string;
  metrics?: Record<string, number>;
  [key: string]: unknown;
}

export interface HealthStatus {
  status?: string;
  [key: string]: unknown;
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${path}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  };

  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }

  const res = await fetch(url, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let message = `Request failed with status ${res.status}`;
    try {
      const text = await res.text();
      if (text) message = text;
    } catch {
      // ignore
    }
    throw new Error(message);
  }

  return (await res.json()) as T;
}

export function getPortfolioOverview(): Promise<PortfolioOverview> {
  return request<PortfolioOverview>('/portfolio/overview');
}

export function getPortfolioItems(): Promise<PortfolioItem[]> {
  return request<PortfolioItem[]>('/portfolio/items');
}

export function getPortfolioTimeseries(
  range: '1d' | '7d' | '30d'
): Promise<PortfolioTimeseriesResponse> {
  const qs = `?range=${encodeURIComponent(range)}`;
  return request<PortfolioTimeseriesResponse>(`/portfolio/timeseries${qs}`);
}

export function scanAndAddItem(
  payload: ScanAndAddPayload
): Promise<ScanAndAddResult> {
  return request<ScanAndAddResult>('/portfolio/scan_and_add', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getMarketplaceListings(): Promise<MarketplaceListing[]> {
  return request<MarketplaceListing[]>('/marketplace/listings');
}

export function getEvalSummary(): Promise<EvalSummary> {
  return request<EvalSummary>('/eval/summary');
}

export function getHealth(): Promise<HealthStatus> {
  // If your primary readiness endpoint is /readyz, change this path.
  return request<HealthStatus>('/healthz');
}


export interface ItemPredictionBand {
  currency: string;
  low?: number;
  mid?: number;
  high?: number;
  as_of?: string;
  model_name?: string;
}

export interface ItemCategoryMeta {
  slug: string;
  label: string;
  wave?: string;
  active?: boolean;
  avg_value?: number;
  item_count?: number;
}

export interface ItemSignal {
  name: string;
  value: number | string;
  unit?: string;
}

export interface ItemDetail {
  item: PortfolioItem;
  category?: ItemCategoryMeta;
  prediction?: ItemPredictionBand;
  signals?: ItemSignal[];
  [key: string]: unknown;
}

/**
 * Fetch rich item detail, including category meta, prediction band and signals.
 * Expected backend route (to be implemented): GET /items/{id}/detail
 */
export function getItemDetail(id: string): Promise<ItemDetail> {
  return request<ItemDetail>(`/items/${encodeURIComponent(id)}/detail`);
}
export async function createAlert(body: Record<string, unknown>) {
  const res = await fetch(`${API_BASE_URL}/alerts`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function getAlerts(userId: string) {
  const res = await fetch(`${API_BASE_URL}/alerts?user_id=${userId}`, {
    method: "GET",
    headers: { "X-API-Key": API_KEY },
  });
  return res.json();
}

// --- CollectAI: portfolio & trends extensions --- //

export type PortfolioTrendPoint = {
  ts: string;
  value: number;
  high: number;
  low: number;
};

export async function getPortfolioTrends(
  window: '1d' | '7d' | '30d' = '30d',
) {
  const qs = `?window=${window}`;
  return request<{
    window: string;
    points: PortfolioTrendPoint[];
  }>(`/portfolio/trends${qs}`);
}

// --- CollectAI: per-item trends --- //

export type ItemTrendPoint = {
  ts: string;
  predicted_value: number;
  confidence: number;
  volume: number;
  category_health: number;
};

export async function getItemTrends(
  itemId: string,
  window: '1d' | '7d' | '30d' = '30d',
) {
  const qs = `?window=${window}`;
  return request<{
    item_id: string;
    window: string;
    points: ItemTrendPoint[];
  }>(`/items/${itemId}/trends${qs}`);
}

// --- CollectAI: category deep-dive --- //

export type CategoryOverview = {
  id: string;
  name: string;
  avg_market_price: number;
  value_distribution: { p10: number; p50: number; p90: number };
  volume_trend: { direction: string; change_pct: number };
  top_sets: { name: string; avg_price: number }[];
  top_movers: { name: string; change_pct: number }[];
};

export async function getCategoryOverview(
  categoryId: string,
) {
  return request<CategoryOverview>(`/categories/${categoryId}/overview`);
}

// --- CollectAI: provenance & ownership history --- //

export type ProvenanceEvent = {
  ts: string;
  type: string;
  actor: string;
  description: string;
};

export type ItemProvenance = {
  item_id: string;
  added_at: string;
  owner_since_days: number;
  current_owner: { kind: string; label: string };
  previous_owner: { kind: string; label: string } | null;
  events: ProvenanceEvent[];
  authenticity: {
    receipt_uploaded: boolean;
    receipt_last_checked_at: string | null;
    image_match_confidence: number;
    market_history_match: string;
    risk_score: number;
    notes: string;
  };
};

export async function getItemProvenance(
  itemId: string,
) {
  return request<ItemProvenance>(`/provenance/items/${itemId}`);
}

// --- CollectAI: advanced alerts v2 --- //

export type AdvancedAlertType =
  | 'item_below_threshold'
  | 'category_trend'
  | 'prediction_unusual';

export type AdvancedAlertPayload = {
  type: AdvancedAlertType;
  item_id?: string;
  category_id?: string;
  threshold_value?: number;
  trend_direction?: 'up' | 'down';
  zscore_threshold?: number;
  channel_email?: boolean;
  channel_push?: boolean;
  channel_telegram?: boolean;
};

export async function createAdvancedAlert(
  body: AdvancedAlertPayload,
) {
  return request<{ ok: boolean; alert: Record<string, unknown> }>('/alerts/advanced/create', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// --- CollectAI: alerts demo runner --- //

export type DemoAlertRunResult = {
  ok: boolean;
  count: number;
  sent: {
    id: string;
    type: string;
    channels: {
      email?: boolean;
      push?: boolean;
      telegram?: boolean;
      [key: string]: unknown;
    };
    [key: string]: unknown;
  }[];
};

export async function runDemoAlerts(): Promise<DemoAlertRunResult> {
  return request<DemoAlertRunResult>('/alerts/advanced/run-demo', {
    method: 'POST',
  });
}

// --- CollectAI: item insights (detail + trends + provenance) --- //

export type ItemDetailSummary = {
  id: string;
  name: string;
  category: string;
  category_label: string;
  estimated_value: number;
  currency: string;
  condition: string;
  rarity: string;
  acquired_at: string;
  notes?: string;
};

export type ItemInsightsResponse = {
  item_id: string;
  window: string;
  detail: ItemDetailSummary;
  trends: {
    item_id: string;
    window: string;
    points: {
      ts: string;
      predicted_value: number;
      confidence: number;
      volume: number;
      category_health: number;
    }[];
  };
  provenance: {
    item_id: string;
    added_at: string;
    owner_since_days: number;
    current_owner: { kind: string; label: string };
    previous_owner: { kind: string; label: string } | null;
    events: {
      ts: string;
      type: string;
      actor: string;
      description: string;
    }[];
    authenticity: {
      receipt_uploaded: boolean;
      receipt_last_checked_at: string | null;
      image_match_confidence: number;
      market_history_match: string;
      risk_score: number;
      notes: string;
    };
  };
};

export async function getItemInsights(
  itemId: string,
  window: '1d' | '7d' | '30d' = '7d',
): Promise<ItemInsightsResponse> {
  const qs = `?window=${window}`;
  return request<ItemInsightsResponse>(`/items/${itemId}/insights${qs}`);
}

// --- CollectAI: watchlist insights --- //

export type WatchlistInsightItem = {
  item_id: string;
  name: string;
  category: string;
  category_label: string;
  latest_value: number;
  currency: string;
  window: string;
  change_pct: number;
  category_health: number;
  is_from_screenshot: boolean;
  is_alert_armed: boolean;
  last_updated_at: string;
};

export type WatchlistInsightsResponse = {
  window: string;
  count: number;
  items: WatchlistInsightItem[];
  generated_at: string;
};

export async function getWatchlistInsights(
  window: '1d' | '7d' | '30d' = '7d',
): Promise<WatchlistInsightsResponse> {
  const qs = `?window=${window}`;
  return request<WatchlistInsightsResponse>(`/watchlist/insights${qs}`);
}

// --- CollectAI: marketplace trust & price guidance --- //

export type MarketplaceTrustBadge = {
  id: string;
  label: string;
};

export type MarketplaceTrustProfile = {
  user_id: string;
  display_name: string;
  reputation_score: number;
  completed_trades: number;
  dispute_rate: number;
  badges: MarketplaceTrustBadge[];
  risk_flags: { id: string; severity: string; label: string; detail: string }[];
  joined_at: string;
  last_active_at: string;
};

export type MarketplaceListingTrust = {
  listing_id: string;
  title: string;
  category: string;
  category_label: string;
  currency: string;
  seller_id: string;
  fair_price: { p10: number; p50: number; p90: number };
  model_confidence: number;
  recommended_price_range: { min: number; max: number };
  risk_flags: { id: string; severity: string; label: string; detail: string }[];
  trust_score: number;
  guidance_text: string;
  last_scored_at: string;
};

export async function getMarketplaceTrustProfile(
  userId: string,
): Promise<{ ok: boolean; profile: MarketplaceTrustProfile }> {
  return request<{ ok: boolean; profile: MarketplaceTrustProfile }>(
    `/marketplace/trust/profile/${userId}`,
  );
}

export async function getMarketplaceListingTrust(
  listingId: string,
): Promise<{
  ok: boolean;
  listing: MarketplaceListingTrust;
  seller_profile: {
    user_id: string;
    reputation_score: number;
    completed_trades: number;
    dispute_rate: number;
    badges: MarketplaceTrustBadge[];
  };
}> {
  return request<{
    ok: boolean;
    listing: MarketplaceListingTrust;
    seller_profile: {
      user_id: string;
      reputation_score: number;
      completed_trades: number;
      dispute_rate: number;
      badges: MarketplaceTrustBadge[];
    };
  }>(`/marketplace/trust/listing/${listingId}`);
}

// --- CollectAI: screenshot intelligence (demo) --- //

export type ScreenshotIntelDemoRequest = {
  source?: string;
  screenshot_id?: string | null;
  note?: string | null;
};

export type ScreenshotIntelDetectedItem = {
  item_id: string;
  title: string;
  category: string;
  category_label: string;
  estimated_value: number;
  currency: string;
  confidence: number;
  thumb_url?: string | null;
  listing_url?: string | null;
  suggest_watchlist: boolean;
  suggest_alert: boolean;
};

export type ScreenshotIntelDemoResponse = {
  request: ScreenshotIntelDemoRequest;
  primary_item: ScreenshotIntelDetectedItem;
  detected_items: ScreenshotIntelDetectedItem[];
  suggested_actions: {
    add_primary_to_watchlist: boolean;
    create_price_alert_for_primary: boolean;
    watchlist_reason: string;
    alert_reason: string;
    [key: string]: unknown;
  };
  generated_at: string;
};

export async function runScreenshotIntelDemo(
  payload: ScreenshotIntelDemoRequest,
): Promise<ScreenshotIntelDemoResponse> {
  return request<ScreenshotIntelDemoResponse>('/screenshot-intel/demo', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// --- CollectAI: categories deep-dive (all categories) --- //

export type CategoryDeepDive = {
  id: string;
  name: string;
  avg_market_price: number;
  value_distribution: {
    p10: number;
    p50: number;
    p90: number;
  };
  volume_trend: {
    direction: string;
    change_pct: number;
  };
  top_sets: {
    name: string;
    avg_price: number;
  }[];
  top_movers: {
    name: string;
    change_pct: number;
  }[];
};

export type CategoriesDeepDiveResponse = {
  window: string;
  generated_at: string;
  categories: CategoryDeepDive[];
};

export async function getCategoriesDeepDive(
  window: '1d' | '7d' | '30d' = '7d',
): Promise<CategoriesDeepDiveResponse> {
  const qs = `?window=${window}`;
  return request<CategoriesDeepDiveResponse>(`/categories/deepdive${qs}`);
}

// --- CollectAI: categories deep-dive (all categories) --- //


// ---- Collection leaderboard & anti-fraud types ----

export interface CollectionLeaderboardEntry {
  id: string;
  name: string;
  owner_label?: string | null;
  total_value: number;
  item_count: number;
  trust_score?: number | null;      // 0–100, higher = better
  anomaly_count?: number | null;    // how many suspicious signals
  coverage_score?: number | null;   // 0–100, data coverage
}

/**
 * Fetch a leaderboard of the most valuable collections.
 * Expected backend shape:
 *   { leaderboard: CollectionLeaderboardEntry[] }
 * or a bare array.
 */
export async function getCollectionsLeaderboard(): Promise<CollectionLeaderboardEntry[]> {
  const data = await request<Record<string, unknown> | CollectionLeaderboardEntry[]>(
    '/portfolio/leaderboard',
  );
  const raw =
    (data && ((data as Record<string, unknown>).leaderboard || (data as Record<string, unknown>).items || (data as Record<string, unknown>).rows || data)) ?? [];
  return (Array.isArray(raw) ? raw : []) as CollectionLeaderboardEntry[];
}
