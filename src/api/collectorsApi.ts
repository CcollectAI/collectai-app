import { API_BASE } from "./config";
import { supabase } from "@/lib/supabase";

const REQUEST_TIMEOUT_MS = 15_000; // 15 seconds
const MAX_RETRIES = 2;
const RETRY_BASE_MS = 500; // exponential backoff base

async function getAuthHeaders(): Promise<Record<string, string>> {
  try {
    const { data } = await supabase.auth.getSession();
    const token = data?.session?.access_token;
    if (token) {
      return { Authorization: `Bearer ${token}` };
    }
  } catch {
    // Supabase mock mode or no session — proceed without auth
  }
  return {};
}

async function fetchWithTimeout(
  input: RequestInfo,
  init?: RequestInit,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function fetchWithRetry(
  input: RequestInfo,
  init?: RequestInit,
): Promise<Response> {
  let lastError: Error | undefined;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const res = await fetchWithTimeout(input, init);
      // Only retry on server errors (5xx)
      if (res.status >= 500 && attempt < MAX_RETRIES) {
        lastError = new Error(`Server error ${res.status}`);
        await sleep(RETRY_BASE_MS * 2 ** attempt);
        continue;
      }
      return res;
    } catch (err: unknown) {
      lastError = err instanceof Error ? err : new Error(String(err));
      // Retry on network/timeout errors, not on abort by caller
      if (attempt < MAX_RETRIES && (err instanceof Error ? err.name : '') !== "AbortError") {
        await sleep(RETRY_BASE_MS * 2 ** attempt);
        continue;
      }
      throw err;
    }
  }
  throw lastError;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function get<T = unknown>(path: string): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    headers: { ...auth },
  });
  if (!res.ok) throw new Error(`GET ${path} failed (${res.status})`);
  return res.json() as Promise<T>;
}

async function post<T = unknown>(path: string, body: Record<string, unknown> = {}): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...auth },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed (${res.status})`);
  return res.json() as Promise<T>;
}

async function del<T = unknown>(path: string): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: { ...auth },
  });
  if (!res.ok) throw new Error(`DELETE ${path} failed (${res.status})`);
  return res.json() as Promise<T>;
}

async function patch<T = unknown>(path: string, body: Record<string, unknown> = {}): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...auth },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`PATCH ${path} failed (${res.status})`);
  return res.json() as Promise<T>;
}

async function postMultipart<T = unknown>(path: string, formData: FormData): Promise<T> {
  const auth = await getAuthHeaders();
  // Do NOT set Content-Type — fetch will auto-set multipart/form-data with boundary
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    method: "POST",
    headers: { ...auth },
    body: formData,
  });
  if (!res.ok) throw new Error(`POST ${path} failed (${res.status})`);
  return res.json() as Promise<T>;
}

/** Response from the server-side optimized photo upload endpoint */
export type ServerUploadResponse = {
  photo_key: string;
  cdn_url: string;
  blurhash: string;
  width: number;
  height: number;
  original_size: number;
  optimized_size: number;
};

export const collectorsApi = {
  // Watchlist
  fetchWatchlist: () => get("/watchlist/mine"),
  addToWatchlist: (p: Record<string, unknown>) => post("/watchlist/mine", p),

  // QuickScan
  quickscanSingle: () => post("/quickscan-advanced/single"),
  quickscanBatch: (image_ids: string[]) =>
    post("/quickscan-advanced/batch", { image_ids }),

  // Insights
  fetchInsights: () => get("/insights/personalized"),
  fetchHomeWidget: () => get("/insights/home-widget"),

  // Screenshot intelligence
  analyzeScreenshot: (payload: { image_base64?: string; screenshot_id?: string; source?: string; note?: string }) =>
    post("/screenshot-intel/analyze", payload as Record<string, unknown>),

  // Feedback
  submitFeedback: (payload: {
    item_id: string;
    feedback_type: string;
    value?: string;
    notes?: string;
  }) => post("/feedback/submit", payload),

  submitCorrection: (payload: {
    item_id: string;
    corrected_price?: number;
    corrected_condition?: string;
    corrected_category?: string;
    notes?: string;
  }) => post("/feedback/correction", payload),

  // Barcode / Market Data
  lookupByBarcode: (barcode: string, codeType?: string) =>
    post("/barcode/lookup", { barcode, code_type: codeType }),

  marketSearch: (query: string, opts?: {
    category_id?: string;
    subtype_id?: string;
    collections?: string[];
    limit?: number;
    sold_only?: boolean;
    min_price?: number;
    max_price?: number;
  }) => post("/market/search", { query, ...opts }),

  // Price prediction
  predictV2: (payload: {
    item_id: string;
    category?: string;
    attributes?: Record<string, unknown>;
  }) => post<{
    q10: number;
    q50: number;
    q90: number;
    asof: string;
  }>("/predict_v2", payload),

  // Price evidence (for PriceExplanationSheet)
  getPriceEvidence: (itemId: string) =>
    get<{
      explanation: string | null;
      evidence_summary: {
        sources: Array<{ source: string; count: number; avg_price: number; date_range?: string }>;
        total_comps: number;
      } | null;
      evidence_hit_ids: string[];
      prediction_at: string | null;
    }>(`/predict/evidence/${encodeURIComponent(itemId)}`),

  // Photo upload — server-side optimized (preferred)
  uploadPhoto: (itemId: string, userId: string, uri: string, mimeType: string) => {
    const formData = new FormData();
    const filename = uri.split("/").pop() || "photo.jpg";
    // React Native's FormData accepts this shape for file uploads
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    formData.append("file", { uri, name: filename, type: mimeType } as any);
    formData.append("item_id", itemId);
    formData.append("user_id", userId);
    return postMultipart<ServerUploadResponse>("/photos/upload", formData);
  },

  // Photo upload — presigned URL fallback (client-side upload)
  getPresignedUploadUrl: (itemId: string, contentType: string, userId: string) =>
    post<{
      upload_url: string;
      photo_key: string;
      cdn_url: string;
    }>("/photos/presign-upload", {
      item_id: itemId,
      content_type: contentType,
      user_id: userId,
    }),

  deletePhoto: (photoKey: string, userId: string) =>
    del(`/photos/${photoKey}?user_id=${encodeURIComponent(userId)}`),

  listItemPhotos: (itemId: string, userId: string) =>
    get<{
      photos: Array<{
        photo_key: string;
        cdn_url: string;
        size?: number;
        last_modified?: string;
      }>;
      item_id: string;
    }>(`/photos/list/${itemId}?user_id=${encodeURIComponent(userId)}`),

  // Provenance
  getProvenance: (itemId: string) =>
    get<{
      item_id: string;
      events: Array<{
        id: string;
        event_type: string;
        timestamp: string;
        note: string | null;
        source: string | null;
        metadata: Record<string, unknown>;
      }>;
      authenticity_signals: string[];
      created_at: string | null;
    }>(`/provenance/items/${encodeURIComponent(itemId)}`),

  // Alert trigger history
  getAlertTriggerHistory: () =>
    get<{
      triggers: Array<{
        id: string;
        alert_id: string | null;
        item_id: string | null;
        trigger_type: string;
        trigger_value: Record<string, unknown>;
        message: string;
        read: boolean;
        created_at: string;
      }>;
      unread_count: number;
    }>("/alerts/trigger-history"),

  markTriggerRead: (triggerId: string) =>
    post(`/alerts/trigger-history/${encodeURIComponent(triggerId)}/read`),

  // Dossier
  getDossier: (itemId: string) =>
    get<{
      item_id: string;
      generated_at: string;
      identity: Record<string, unknown>;
      valuation: Record<string, unknown>;
      provenance: Array<Record<string, unknown>>;
      price_history: Array<Record<string, unknown>>;
      market_comps: Array<Record<string, unknown>>;
      photos: string[];
      collections: string[];
      authenticity_signals: string[];
      completeness_score: number;
    }>(`/dossier/${encodeURIComponent(itemId)}`),

  getDossierSummary: (itemId: string) =>
    get<{
      item_id: string;
      identity: Record<string, unknown>;
      valuation: Record<string, unknown>;
      completeness_score: number;
    }>(`/dossier/${encodeURIComponent(itemId)}/summary`),

  getDossierExportUrl: (itemId: string) =>
    `${API_BASE}/dossier/${encodeURIComponent(itemId)}/export`,

  // FX rates (public, no auth)
  getFxRates: () => get<{
    base: string;
    rates: Record<string, number>;
    rates_from_eur: Record<string, number>;
  }>("/fx/rates"),

  // Marketplace aggregation
  marketplaceSearch: (query: string, category?: string, limit = 20, region?: string) =>
    post("/marketplace/search", { query, category, limit, region }),

  marketplaceComps: (itemRef: string, category?: string, region?: string) =>
    post(`/marketplace/comps/${encodeURIComponent(itemRef)}`, { category, region }),

  // Taxonomy
  getTaxonomy: () => get("/taxonomy/current"),
  getTaxonomyCategories: () =>
    get<{
      version: string;
      categories: Array<{
        category_id: string;
        display_name: string;
        subtypes: string[];
        collections: string[];
      }>;
    }>("/taxonomy/categories"),

  // URL Import (via Firecrawl)
  processIntakeUrl: (
    url: string,
    hints?: { category?: string; name?: string; condition?: string },
  ) =>
    post<IntakeResultResponse>("/intake/url", {
      url,
      ...(hints ?? {}),
    }),

  // Intake Agent
  processIntake: (
    barcode?: string,
    barcodeType?: string,
    hints?: Record<string, unknown>,
  ) =>
    post<IntakeResultResponse>("/intake/barcode-only", {
      barcode: barcode ?? "",
      barcode_type: barcodeType,
      ...(hints ?? {}),
    }),

  // Save intake result to collection
  intakeSave: (payload: {
    title: string;
    category?: string;
    condition?: string;
    subtype_id?: string;
    taxonomy_version?: string;
    attributes?: Record<string, unknown>;
    images?: string[];
    barcode?: string;
    estimated_price?: number;
  }) =>
    post<{
      id: string;
      title: string;
      category: string | null;
      created: boolean;
    }>("/intake/save", payload),

  // Price alerts
  getMyAlerts: () =>
    get<{
      alerts: Array<{
        id: string;
        user_id: string;
        item_id: string | null;
        category: string | null;
        trigger_type: string;
        threshold_value: number | null;
        direction: string | null;
        active: boolean;
        created_at: string;
      }>;
    }>("/alerts/mine"),

  createAlert: (payload: {
    item_id?: string;
    category?: string;
    trigger_type: string;
    threshold_value?: number;
    direction?: string;
    metadata?: Record<string, unknown>;
  }) =>
    post<{
      id: string;
      trigger_type: string;
      threshold_value: number | null;
      active: boolean;
    }>("/alerts/mine", payload),

  deleteAlert: (alertId: string) =>
    del(`/alerts/mine/${encodeURIComponent(alertId)}`),

  // Push notifications
  registerPushToken: (token: string, platform: string) =>
    post("/notifications/register", { push_token: token, platform }),

  unregisterPushToken: async (token: string) => {
    const auth = await getAuthHeaders();
    const res = await fetchWithRetry(`${API_BASE}/notifications/register`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json", ...auth },
      body: JSON.stringify({ push_token: token }),
    });
    if (!res.ok) throw new Error(`DELETE /notifications/register failed (${res.status})`);
    return res.json();
  },

  processIntakeWithImage: async (formData: FormData): Promise<IntakeResultResponse> => {
    const auth = await getAuthHeaders();
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const res = await fetch(`${API_BASE}/intake/process`, {
        method: "POST",
        headers: { ...auth },
        body: formData,
        signal: controller.signal,
      });
      if (!res.ok) throw new Error(`POST /intake/process failed (${res.status})`);
      return res.json();
    } finally {
      clearTimeout(timer);
    }
  },

  // ── Smart Deal Agent ─────────────────────────────────────────────────────

  // Mandates
  createMandate: (payload: {
    name: string;
    search_query: string;
    category?: string | null;
    condition_filter?: string[];
    min_trust_score?: number;
    max_price: number;
    max_total_budget?: number | null;
    cooldown_hours?: number;
    allowed_sources?: string[];
    region?: string | null;
    expires_at?: string | null;
  }) => post("/purchase/mandates", payload as Record<string, unknown>),

  listMandates: (limit = 20, offset = 0) =>
    get(`/purchase/mandates?limit=${limit}&offset=${offset}`),

  getMandate: (id: string) =>
    get(`/purchase/mandates/${encodeURIComponent(id)}`),

  updateMandate: (id: string, payload: Record<string, unknown>) =>
    patch(`/purchase/mandates/${encodeURIComponent(id)}`, payload),

  deleteMandate: (id: string) =>
    del(`/purchase/mandates/${encodeURIComponent(id)}`),

  // Deals
  listDeals: (params?: { status?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    const query = qs.toString();
    return get(`/purchase/deals${query ? `?${query}` : ""}`);
  },

  getDeal: (id: string) =>
    get(`/purchase/deals/${encodeURIComponent(id)}`),

  clickDeal: (id: string) =>
    post(`/purchase/deals/${encodeURIComponent(id)}/click`),

  confirmDeal: (id: string, confirmedPrice?: number) =>
    post(`/purchase/deals/${encodeURIComponent(id)}/confirm`, {
      confirmed_price: confirmedPrice,
    }),

  declineDeal: (id: string) =>
    post(`/purchase/deals/${encodeURIComponent(id)}/decline`),

  // Stats
  getDealStats: () => get("/purchase/stats"),

  // Affiliate links (no auth required — works for all users)
  getAffiliateLinks: (query: string, category?: string, limit = 3) =>
    get<{
      links: Array<{
        source: string;
        url: string;
        affiliate_url: string;
        label: string;
      }>;
    }>(`/marketplace/affiliate-links?query=${encodeURIComponent(query)}${category ? `&category=${encodeURIComponent(category)}` : ""}&limit=${limit}`),
};

// Intake result type returned by the intake agent endpoints
export type IntakeResultResponse = {
  name: string | null;
  category_id: string | null;
  category_confidence: number;
  subtype_id: string | null;
  attributes: Record<string, unknown>;
  identification_method: string;
  barcode: string | null;
  barcode_type: string | null;
  taxonomy_version: string;
  taxonomy_confidence: number;
  suggested_corrections: Array<{
    from_category: string;
    to_category: string;
    frequency: number;
    user_count: number;
  }>;
  estimated_price: number | null;
  price_source: string | null;
  price_band: {
    q10: number;
    q50: number;
    q90: number;
    confidence: number;
    currency: string;
  } | null;
  image_url: string | null;
  rationale: string[];
};

// ---------------------------------------------------------------------------
// Account Management
// ---------------------------------------------------------------------------

export async function deleteAccount(): Promise<{ success: boolean; message: string }> {
  return del("/account");
}

// ---------------------------------------------------------------------------
// Billing / Subscriptions
// ---------------------------------------------------------------------------

export interface BillingStatus {
  plan: "free" | "pro" | "premium";
  status: "active" | "past_due" | "canceled" | "unpaid" | "trialing";
  current_period_end?: string | null;
  cancel_at_period_end: boolean;
  limits: {
    max_mandates: number;
    deal_discovery: boolean;
    dossier_pdf: boolean;
    advanced_analytics: boolean;
  };
}

export async function getBillingStatus(): Promise<BillingStatus> {
  return get("/billing/status");
}

export async function createCheckoutSession(plan: "pro" | "premium"): Promise<{ url: string; session_id: string }> {
  return post("/billing/checkout-session", { plan });
}

export async function createPortalSession(): Promise<{ url: string }> {
  return post("/billing/portal-session", {});
}
