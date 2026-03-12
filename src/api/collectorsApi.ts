import { API_BASE } from "./config";
import { supabase } from "@/lib/supabase";
import type { CurrencyCode } from "@/data/types";

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

export class ApiError extends Error {
  status: number;
  code: string | null;
  detail: string;

  constructor(method: string, path: string, status: number, detail: string, code: string | null = null) {
    super(`${method} ${path} failed (${status}): ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.code = code;
  }
}

async function parseErrorResponse(method: string, path: string, res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const detail = typeof body?.detail === "string" ? body.detail : `${method} ${path} failed`;
    const code = typeof body?.code === "string" ? body.code : null;
    return new ApiError(method, path, res.status, detail, code);
  } catch {
    return new ApiError(method, path, res.status, `${method} ${path} failed`);
  }
}

async function get<T = unknown>(path: string): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    headers: { ...auth },
  });
  if (!res.ok) throw await parseErrorResponse("GET", path, res);
  return res.json() as Promise<T>;
}

async function post<T = unknown>(path: string, body: Record<string, unknown> = {}): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...auth },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await parseErrorResponse("POST", path, res);
  return res.json() as Promise<T>;
}

async function del<T = unknown>(path: string): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: { ...auth },
  });
  if (!res.ok) throw await parseErrorResponse("DELETE", path, res);
  if (res.status === 204) return {} as T;
  return res.json() as Promise<T>;
}

async function patch<T = unknown>(path: string, body: Record<string, unknown> = {}): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...auth },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await parseErrorResponse("PATCH", path, res);
  return res.json() as Promise<T>;
}

async function put<T = unknown>(path: string, body: Record<string, unknown> = {}): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...auth },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await parseErrorResponse("PUT", path, res);
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
  if (!res.ok) throw await parseErrorResponse("POST", path, res);
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

  // Intake — image-only (vision pipeline: CLIP + GPT-4o-mini + heuristic)
  intakeImageOnly: (imageUri: string) => {
    const formData = new FormData();
    const filename = imageUri.split("/").pop() || "scan.jpg";
    // React Native's FormData accepts this shape for file uploads
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    formData.append("file", { uri: imageUri, name: filename, type: "image/jpeg" } as any);
    return postMultipart<IntakeResultResponse>("/intake/image-only", formData);
  },
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
  }) => post("/marketplace/search", { query, ...opts }),

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

  // Price trend (per-item price history chart)
  getItemPriceTrend: (itemId: string, days = 90) =>
    get<{
      data_points: Array<{ date: string; q50: number; q10: number; q90: number }>;
      direction: 'up' | 'down' | 'flat';
      pct_change: number;
      current_q50: number;
      period_days: number;
    }>(`/predict/${encodeURIComponent(itemId)}/trend?days=${days}`),

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
  uploadPhoto: (itemId: string, uri: string, mimeType: string) => {
    const formData = new FormData();
    const filename = uri.split("/").pop() || "photo.jpg";
    // React Native's FormData accepts this shape for file uploads
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    formData.append("file", { uri, name: filename, type: mimeType } as any);
    formData.append("item_id", itemId);
    return postMultipart<ServerUploadResponse>("/photos/upload", formData);
  },

  // Photo upload — presigned URL fallback (client-side upload)
  getPresignedUploadUrl: (itemId: string, contentType: string) =>
    post<{
      upload_url: string;
      photo_key: string;
      cdn_url: string;
    }>("/photos/presign-upload", {
      item_id: itemId,
      content_type: contentType,
    }),

  deletePhoto: (photoKey: string) =>
    del(`/photos/${photoKey}`),

  listItemPhotos: (itemId: string) =>
    get<{
      photos: Array<{
        photo_key: string;
        cdn_url: string;
        size?: number;
        last_modified?: string;
      }>;
      item_id: string;
    }>(`/photos/list/${itemId}`),

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
  marketplaceSearch: (query: string, opts?: {
    category?: string;
    limit?: number;
    region?: string;
    source?: string[];
    condition?: string[];
    min_price?: number;
    max_price?: number;
    sort?: string;
  }) =>
    post("/marketplace/search", { query, ...opts }),

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

  getNotificationPreferences: () =>
    get("/notifications/preferences"),

  updateNotificationPreferences: (prefs: Record<string, boolean>) =>
    put("/notifications/preferences", prefs),

  unregisterPushToken: async (token: string) => {
    const auth = await getAuthHeaders();
    const res = await fetchWithRetry(`${API_BASE}/notifications/register`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json", ...auth },
      body: JSON.stringify({ push_token: token }),
    });
    if (!res.ok) throw await parseErrorResponse("DELETE", "/notifications/register", res);
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
      if (!res.ok) throw await parseErrorResponse("POST", "/intake/process", res);
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

  // Catalog Learning — submit suggestion for unrecognized items
  submitCatalogSuggestion: (payload: {
    source: "barcode" | "photo" | "manual" | "url";
    input_data: Record<string, unknown>;
    suggested_name: string;
    suggested_category?: string;
  }) =>
    post<{
      id: string;
      status: string;
      matched_existing: boolean;
    }>("/catalog/suggest", payload),

  // Geolocation (no auth required — called during onboarding)
  detectRegion: () =>
    get<{
      region: string;
      currency: CurrencyCode;
      country_code: string | null;
    }>("/geo/detect"),

  // Affiliate links (no auth required — works for all users)
  getAffiliateLinks: (query: string, category?: string, limit = 6, region?: string) =>
    get<{
      links: Array<{
        source: string;
        url: string;
        affiliate_url: string;
        label: string;
      }>;
    }>(`/marketplace/affiliate-links?query=${encodeURIComponent(query)}${category ? `&category=${encodeURIComponent(category)}` : ""}&limit=${limit}${region ? `&region=${encodeURIComponent(region)}` : ""}`),

  // Tag any raw URL with affiliate params (no auth required)
  tagAffiliateUrl: (url: string, source: string) =>
    post<{ url: string; affiliate_url: string; source: string }>(
      '/marketplace/affiliate-url', { url, source }
    ),

  // ── Deal Desk (P2P Offers) ──────────────────────────────────────────────

  proposeOffer: (payload: { item_id: string; price: number; message?: string }) =>
    post("/deals/offer", payload as Record<string, unknown>),

  counterOffer: (offerId: string, payload: { price: number; message?: string }) =>
    post(`/deals/${encodeURIComponent(offerId)}/counter`, payload as Record<string, unknown>),

  respondToOffer: (offerId: string, payload: { accept: boolean; message?: string }) =>
    post(`/deals/${encodeURIComponent(offerId)}/respond`, payload as Record<string, unknown>),

  cancelOffer: (offerId: string) =>
    post(`/deals/${encodeURIComponent(offerId)}/cancel`),

  markShipped: (offerId: string, payload: { tracking_info?: string }) =>
    post(`/deals/${encodeURIComponent(offerId)}/ship`, payload as Record<string, unknown>),

  completeDeal: (offerId: string, payload: { stars: number; comment?: string }) =>
    post(`/deals/${encodeURIComponent(offerId)}/complete`, payload as Record<string, unknown>),

  listActiveOffers: () => get("/deals/active"),

  listDealHistory: () => get("/deals/history"),

  getOfferDetail: (offerId: string) =>
    get(`/deals/${encodeURIComponent(offerId)}`),

  getOfferEvidence: (offerId: string) =>
    get(`/deals/${encodeURIComponent(offerId)}/evidence`),

  getUserReputation: (userId: string) =>
    get(`/deals/reputation/${encodeURIComponent(userId)}`),

  toggleItemForSale: (itemId: string, payload: { for_sale: boolean; asking_price?: number }) =>
    put(`/items/${encodeURIComponent(itemId)}/for-sale`, payload as Record<string, unknown>),

  // ── Item Images (multi-photo per item) ───────────────────────────────────

  listItemImages: (itemId: string) =>
    get<{
      images: Array<{
        id: string;
        item_id: string;
        image_url: string;
        label: string | null;
        position: number;
        created_at: string | null;
      }>;
      item_id: string;
      total: number;
    }>(`/items/${encodeURIComponent(itemId)}/images`),

  uploadItemImage: (itemId: string, uri: string, label?: string) => {
    const formData = new FormData();
    const filename = uri.split("/").pop() || "photo.jpg";
    // React Native's FormData accepts this shape for file uploads
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    formData.append("file", { uri, name: filename, type: "image/jpeg" } as any);
    if (label) formData.append("label", label);
    return postMultipart<{
      id: string;
      item_id: string;
      image_url: string;
      label: string | null;
      position: number;
      created_at: string | null;
    }>(`/items/${encodeURIComponent(itemId)}/images`, formData);
  },

  deleteItemImage: (itemId: string, imageId: string) =>
    del<{ success: boolean; message: string }>(
      `/items/${encodeURIComponent(itemId)}/images/${encodeURIComponent(imageId)}`
    ),

  reorderItemImages: (itemId: string, imageIds: string[]) =>
    put<{ success: boolean; reordered_count: number }>(
      `/items/${encodeURIComponent(itemId)}/images/reorder`,
      { image_ids: imageIds }
    ),

  // ── Drop Alerts ─────────────────────────────────────────────────────────

  subscribeDropAlert: (eventId: string, notifyBeforeHours = 24) =>
    post<{
      user_id: string;
      event_id: string;
      notify_before_hours: number;
      created_at: string | null;
    }>(`/events/${encodeURIComponent(eventId)}/alert`, {
      notify_before_hours: notifyBeforeHours,
    }),

  unsubscribeDropAlert: (eventId: string) =>
    del(`/events/${encodeURIComponent(eventId)}/alert`),

  listMyDropAlerts: () =>
    get<Array<{
      user_id: string;
      event_id: string;
      notify_before_hours: number;
      created_at: string | null;
    }>>("/events/my-alerts"),

  // ── Onboarding / User Settings ─────────────────────────────────────────

  saveFollowedCategories: (categories: string[]) =>
    put("/settings", { followed_categories: categories }),

  getFollowedCategories: () =>
    get<{ followed_categories: string[] }>("/settings"),

  // ── Catalog Browser ────────────────────────────────────────────────────
  browseCatalogItems: (categoryId: string, opts?: {
    q?: string;
    limit?: number;
    offset?: number;
    rarity?: string;
  }) => {
    const sp = new URLSearchParams();
    if (opts?.q) sp.set('q', opts.q);
    if (opts?.limit) sp.set('limit', String(opts.limit));
    if (opts?.offset) sp.set('offset', String(opts.offset));
    if (opts?.rarity) sp.set('rarity', opts.rarity);
    const query = sp.toString();
    return get<{
      items: Array<{
        id: string;
        category: string;
        item_key: string;
        title: string;
        brand: string | null;
        rarity: string | null;
        notes: string | null;
        image_url: string | null;
        external_id: string | null;
        set_code: string | null;
        estimated_price: number | null;
      }>;
      total: number;
      limit: number;
      offset: number;
      category_id: string;
    }>(`/catalog/${encodeURIComponent(categoryId)}/items${query ? `?${query}` : ''}`);
  },

  // ── Progress Tracking ─────────────────────────────────────────────────
  getItemProgress: (itemId: string) =>
    get<{
      item_id: string;
      progress_status: string | null;
      progress_pct: number | null;
      progress_notes: string | null;
    }>(`/items/${encodeURIComponent(itemId)}/progress`),

  updateItemProgress: (itemId: string, payload: {
    progress_status?: string;
    progress_pct?: number;
    progress_notes?: string;
  }) =>
    patch<{
      item_id: string;
      progress_status: string | null;
      progress_pct: number | null;
      progress_notes: string | null;
    }>(`/items/${encodeURIComponent(itemId)}/progress`, payload as Record<string, unknown>),

  // ── Item Attributes / Size ──────────────────────────────────────────────
  updateItemAttributes: (itemId: string, attributes: Record<string, unknown>, itemSize?: string, sizeSystem?: string) =>
    patch<{ ok: boolean; item_id: string }>(
      `/items/${encodeURIComponent(itemId)}/attributes`,
      {
        attributes,
        ...(itemSize !== undefined ? { item_size: itemSize } : {}),
        ...(sizeSystem !== undefined ? { size_system: sizeSystem } : {}),
      },
    ),

  // ── Grading Service Integration ─────────────────────────────────────────

  gradingLookup: (certNumber: string, service: 'psa' | 'cgc' | 'bgs' | 'beckett') =>
    get<{
      cert_number: string;
      service: string;
      service_name: string;
      item_name: string | null;
      grade: string | null;
      grade_numeric: number | null;
      sub_grades: Record<string, number> | null;
      population_at_grade: number | null;
      population_higher: number | null;
      cert_verified: boolean;
      cert_url: string | null;
      label_type: string | null;
      year: string | null;
      error: string | null;
    }>(`/grading/lookup?cert_number=${encodeURIComponent(certNumber)}&service=${encodeURIComponent(service)}`),

  gradingPopulation: (itemName: string, category: string, service?: string) =>
    get<{
      item_name: string;
      category: string;
      service: string;
      total_graded: number;
      population: Array<{
        grade: string;
        count: number;
        pct_of_total: number | null;
      }>;
      avg_grade: number | null;
      highest_grade: string | null;
      last_updated: string | null;
    }>(`/grading/population?item_name=${encodeURIComponent(itemName)}&category=${encodeURIComponent(category)}${service ? `&service=${encodeURIComponent(service)}` : ''}`),

  gradingServices: (category?: string) =>
    get<{
      services: Array<{
        id: string;
        name: string;
        short_name: string;
        website: string;
        submission_url: string;
        grade_scale: string;
        categories: string[];
        turnaround: string;
        price_range: string;
      }>;
      eligible_categories: string[];
    }>(`/grading/services${category ? `?category=${encodeURIComponent(category)}` : ''}`),

  // ── Gamification ──────────────────────────────────────────────────────

  getGamificationProfile: () =>
    get<{
      user_id: string;
      xp: number;
      level: number;
      streak_days: number;
      badges: string[];
    }>("/gamification/profile"),

  getAchievements: () =>
    get<{
      achievements: Array<{
        id: string;
        title: string;
        description: string;
        tier: string;
        earned: boolean;
        earned_at: string | null;
      }>;
    }>("/gamification/achievements"),

  getRecentAchievements: () =>
    get<{
      achievements: Array<{
        id: string;
        title: string;
        tier: string;
        earned_at: string;
      }>;
    }>("/gamification/achievements/recent"),

  getActiveChallenges: () =>
    get<{
      challenges: Array<{
        id: string;
        title: string;
        description: string;
        progress: number;
        target: number;
        reward_xp: number;
        expires_at: string | null;
      }>;
    }>("/gamification/challenges"),

  getLeaderboard: (scope?: string, category?: string) => {
    const sp = new URLSearchParams();
    if (scope) sp.set("scope", scope);
    if (category) sp.set("category", category);
    const q = sp.toString();
    return get<{
      entries: Array<{
        rank: number;
        user_id: string;
        display_name: string;
        xp: number;
        level: number;
        avatar_url: string | null;
      }>;
    }>(`/gamification/leaderboard${q ? `?${q}` : ""}`);
  },

  // ── Marketplace Listings (Multi-Marketplace Selling) ─────────────────

  createMarketplaceListing: (payload: {
    item_id: string;
    marketplace_id: string;
    price: number;
    currency?: string;
    format?: string;
    condition_description?: string;
  }) => post("/marketplace/listings", payload as Record<string, unknown>),

  listMarketplaceListings: (opts?: { status?: string; marketplace_id?: string; limit?: number; offset?: number }) => {
    const sp = new URLSearchParams();
    if (opts?.status) sp.set("status", opts.status);
    if (opts?.marketplace_id) sp.set("marketplace_id", opts.marketplace_id);
    if (opts?.limit) sp.set("limit", String(opts.limit));
    if (opts?.offset) sp.set("offset", String(opts.offset));
    const q = sp.toString();
    return get(`/marketplace/listings${q ? `?${q}` : ""}`);
  },

  updateMarketplaceListing: (listingId: string, payload: Record<string, unknown>) =>
    patch(`/marketplace/listings/${encodeURIComponent(listingId)}`, payload),

  deleteMarketplaceListing: (listingId: string) =>
    del(`/marketplace/listings/${encodeURIComponent(listingId)}`),

  publishMarketplaceListing: (listingId: string) =>
    post(`/marketplace/listings/${encodeURIComponent(listingId)}/publish`),

  calculateMarketplaceFees: (payload: { price: number; marketplace_id: string; category?: string }) =>
    post("/marketplace/listings/fees/calculate", payload as Record<string, unknown>),

  // ── Portfolio Analytics ──────────────────────────────────────────────

  getPortfolioOverview: () => get("/portfolio/overview"),

  getPortfolioTimeseries: (range?: string) =>
    get(`/portfolio/timeseries${range ? `?range=${encodeURIComponent(range)}` : ""}`),

  getPortfolioCategoryBreakdown: () => get("/portfolio/category-breakdown"),

  getPortfolioCategoryStats: () => get("/portfolio/category-stats"),

  getCategoryHealth: () => get("/portfolio/category-health"),

  getCategoryCrossCorrelation: (category: string) =>
    get(`/portfolio/category-correlation?category=${encodeURIComponent(category)}`),

  // ── Collections ─────────────────────────────────────────────────────

  listCollections: (category?: string) =>
    get(`/collections${category ? `?category=${encodeURIComponent(category)}` : ""}`),

  getCollectionDetail: (collectionId: string) =>
    get(`/collections/${encodeURIComponent(collectionId)}`),

  getCollectionProgress: (collectionId: string) =>
    get(`/collections/${encodeURIComponent(collectionId)}/progress`),

  getUserCollectionProgress: (category?: string) =>
    get(`/collections/user/progress${category ? `?category=${encodeURIComponent(category)}` : ""}`),

  // ── Insights ────────────────────────────────────────────────────────

  getPersonalizedInsights: () => get("/insights/personalized"),

  getHomeWidget: () => get("/insights/home-widget"),

  // ── Items Export ────────────────────────────────────────────────────

  exportItemsOverview: () => get("/items-export/overview"),

  // ── Insurance Valuation Export ─────────────────────────────────────────

  getInsuranceReportUrl: (format: 'html' | 'json' = 'html', currency?: string) => {
    const params = new URLSearchParams({ format });
    if (currency) params.set('currency', currency);
    return `${API_BASE}/export/insurance-report?${params.toString()}`;
  },

  // ── Social ──────────────────────────────────────────────────────────

  searchUsers: (query: string, limit = 10) =>
    get<{
      users: Array<{
        user_id: string;
        display_name: string;
        handle: string | null;
        avatar_url: string | null;
      }>;
    }>(`/social/users/search?q=${encodeURIComponent(query)}&limit=${limit}`),

  blockUser: (userId: string) =>
    post(`/social/block/${encodeURIComponent(userId)}`),

  unblockUser: (userId: string) =>
    del(`/social/block/${encodeURIComponent(userId)}`),

  listBlockedUsers: () =>
    get<{
      blocked: Array<{
        user_id: string;
        display_name: string | null;
        blocked_at: string;
      }>;
    }>("/social/blocked"),

  // ── Data Moat Analytics ────────────────────────────────────────────

  getSupplyTrends: (category?: string, days = 30) => {
    const sp = new URLSearchParams();
    if (category) sp.set("category", category);
    sp.set("days", String(days));
    return get<{
      trends: Array<{
        date: string;
        listing_count: number;
        avg_price: number;
        category: string;
      }>;
    }>(`/data-moat/supply-trends?${sp.toString()}`);
  },

  getDemandHeat: (category?: string) =>
    get<{
      items: Array<{
        item_key: string;
        title: string;
        category: string;
        demand_score: number;
        search_count: number;
      }>;
    }>(`/data-moat/demand-heat${category ? `?category=${encodeURIComponent(category)}` : ""}`),

  getScarcityScores: (category?: string) =>
    get<{
      items: Array<{
        item_key: string;
        title: string;
        scarcity_score: number;
        listing_count: number;
        supply_trend: string;
      }>;
    }>(`/data-moat/scarcity${category ? `?category=${encodeURIComponent(category)}` : ""}`),

  // ── Trends & Deep-Dive ──────────────────────────────────────────────

  getCollectionTrends: (days = 30) =>
    get(`/analytics/collection/trends?days=${days}`),

  getCategoryDeepDive: (categoryId: string) =>
    get(`/analytics/categories/${encodeURIComponent(categoryId)}/deep-dive`),

  getItemTrends: (itemId: string) =>
    get(`/analytics/items/${encodeURIComponent(itemId)}/trends`),

  // ── Events — Core CRUD ─────────────────────────────────────────────

  createEvent: (payload: Record<string, unknown>) =>
    post("/events", payload),

  getEventById: (eventId: string) =>
    get(`/events/${encodeURIComponent(eventId)}`),

  updateEvent: (eventId: string, updates: Record<string, unknown>) =>
    patch(`/events/${encodeURIComponent(eventId)}`, updates),

  deleteEvent: (eventId: string) =>
    del(`/events/${encodeURIComponent(eventId)}`),

  duplicateEvent: (eventId: string) =>
    post(`/events/${encodeURIComponent(eventId)}/duplicate`),

  // ── Events — RSVP ────────────────────────────────────────────────

  rsvpEvent: (eventId: string, status: string = "going") =>
    post(`/events/${encodeURIComponent(eventId)}/rsvp`, { status }),

  unrsvpEvent: (eventId: string) =>
    del(`/events/${encodeURIComponent(eventId)}/rsvp`),

  // ── Events — Ticketing ────────────────────────────────────────────

  createTicketCheckout: (eventId: string) =>
    post(`/events/${encodeURIComponent(eventId)}/ticket-checkout`),

  // ── Events — Announcements ────────────────────────────────────────

  listEventAnnouncements: (eventId: string) =>
    get(`/events/${encodeURIComponent(eventId)}/announcements`),

  postEventAnnouncement: (eventId: string, payload: { body: string; title?: string; image_url?: string }) =>
    post(`/events/${encodeURIComponent(eventId)}/announcements`, payload as Record<string, unknown>),

  markAnnouncementRead: (eventId: string, announcementId: string) =>
    post(`/events/${encodeURIComponent(eventId)}/announcements/${encodeURIComponent(announcementId)}/read`),

  batchMarkAnnouncementsRead: (eventId: string, announcementIds: string[]) =>
    post(`/events/${encodeURIComponent(eventId)}/announcements/batch-read`, { announcement_ids: announcementIds }),

  getUnreadAnnouncementCount: () =>
    get<{ unread_count: number }>("/events/my-announcements/unread-count"),

  // ── Events — Templates ────────────────────────────────────────────

  listEventTemplates: () =>
    get("/events/templates"),

  createEventTemplate: (name: string, fromEventId: string) =>
    post("/events/templates", { name, from_event_id: fromEventId }),

  deleteEventTemplate: (templateId: string) =>
    del(`/events/templates/${encodeURIComponent(templateId)}`),

  // ── Events — Drop Alerts & Categories ─────────────────────────────

  getNearbyEvents: (lat?: number, lng?: number, radiusKm = 50) => {
    const sp = new URLSearchParams();
    if (lat != null) sp.set("lat", String(lat));
    if (lng != null) sp.set("lng", String(lng));
    sp.set("radius_km", String(radiusKm));
    return get(`/events/nearby?${sp.toString()}`);
  },

  getFollowedEventCategories: () =>
    get<{ categories: string[] }>("/events/categories/followed"),

  followEventCategory: (categoryId: string) =>
    post(`/events/categories/${encodeURIComponent(categoryId)}/follow`),

  unfollowEventCategory: (categoryId: string) =>
    del(`/events/categories/${encodeURIComponent(categoryId)}/follow`),

  // ── Set / Collection Tracking ────────────────────────────────────────

  listSets: (categoryId?: string) =>
    get(`/sets${categoryId ? `?category_id=${encodeURIComponent(categoryId)}` : ""}`),

  getSetDetail: (setId: string) =>
    get(`/sets/${encodeURIComponent(setId)}`),

  getSetProgress: (setId: string) =>
    get(`/sets/${encodeURIComponent(setId)}/progress`),

  updateSetProgress: (setId: string, payload: { item_ids: string[]; action: "add" | "remove" }) =>
    put(`/sets/${encodeURIComponent(setId)}/progress`, payload as Record<string, unknown>),

  getMySetProgress: () =>
    get("/sets/my-progress"),

  // ── Sponsor Companies ────────────────────────────────────────────────

  listMySponsorCompanies: () =>
    get("/sponsor-companies/mine"),

  createSponsorCompany: (payload: { name: string; contact_email: string; logo_url?: string; website_url?: string; description?: string }) =>
    post("/sponsor-companies", payload as Record<string, unknown>),

  getSponsorCompany: (companyId: string) =>
    get(`/sponsor-companies/${encodeURIComponent(companyId)}`),

  updateSponsorCompany: (companyId: string, payload: Record<string, unknown>) =>
    patch(`/sponsor-companies/${encodeURIComponent(companyId)}`, payload),

  deleteSponsorCompany: (companyId: string) =>
    del(`/sponsor-companies/${encodeURIComponent(companyId)}`),

  createSponsorEventCheckout: (companyId: string, payload: Record<string, unknown>) =>
    post(`/sponsor-companies/${encodeURIComponent(companyId)}/create-event-checkout`, payload),

  createSponsorSubscriptionCheckout: (companyId: string, payload: { tier: string }) =>
    post(`/sponsor-companies/${encodeURIComponent(companyId)}/create-subscription-checkout`, payload as Record<string, unknown>),

  // ── Build & Paint Step Templates ────────────────────────────────────

  getStepTemplates: (categoryId?: string) =>
    get(`/build-paint/step-templates${categoryId ? `/${encodeURIComponent(categoryId)}` : ""}`),

  // ── Task Queue ──────────────────────────────────────────────────────

  enqueueTask: (payload: { task_type: string; payload?: Record<string, unknown> }) =>
    post("/tasks/enqueue", payload as Record<string, unknown>),

  getTaskStatus: (taskId: string) =>
    get(`/tasks/${encodeURIComponent(taskId)}/status`),

  // ── Marketplace Listing Accounts ──────────────────────────────────

  listMarketplaceAccounts: () =>
    get("/marketplace/listings/accounts"),

  connectMarketplaceAccount: (payload: { marketplace_id: string; seller_name?: string; api_key?: string }) =>
    post("/marketplace/listings/accounts", payload as Record<string, unknown>),

  disconnectMarketplaceAccount: (accountId: string) =>
    del(`/marketplace/listings/accounts/${encodeURIComponent(accountId)}`),

  getMarketplaceFeeSchedules: () =>
    get("/marketplace/listings/fees"),

  listMarketplaceSales: (opts?: { marketplace_id?: string; limit?: number; offset?: number }) => {
    const sp = new URLSearchParams();
    if (opts?.marketplace_id) sp.set("marketplace_id", opts.marketplace_id);
    if (opts?.limit) sp.set("limit", String(opts.limit));
    if (opts?.offset) sp.set("offset", String(opts.offset));
    const q = sp.toString();
    return get(`/marketplace/listings/sales${q ? `?${q}` : ""}`);
  },

  recordMarketplaceSale: (listingId: string, payload: { sale_price: number; buyer_name?: string }) =>
    post(`/marketplace/listings/sales/${encodeURIComponent(listingId)}/record`, payload as Record<string, unknown>),

  // ── Deal Risk Flags ────────────────────────────────────────────────

  getDealRiskFlags: (offerId: string) =>
    get(`/deals/${encodeURIComponent(offerId)}/risk-flags`),

  // ── Mandate Forecast ──────────────────────────────────────────────

  getMandateForecast: (mandateId: string) =>
    get(`/purchase/mandates/${encodeURIComponent(mandateId)}/forecast`),

  // ── Verified Sales (Ground Truth) ──────────────────────────────────

  submitVerifiedSale: (payload: {
    item_id: string;
    sale_price: number;
    currency?: string;
    sale_date?: string;
    marketplace?: string;
  }) => post("/feedback/verified-sale", payload as Record<string, unknown>),

  listVerifiedSales: () =>
    get("/feedback/verified-sales"),

  // ── Sponsor Analytics ──────────────────────────────────────────────

  getSponsorAnalytics: (companyId: string) =>
    get(`/sponsor-companies/${encodeURIComponent(companyId)}/analytics`),

  // ── Supply & Demand Indicators ────────────────────────────────────

  getDemandHeatByRegion: (category?: string, days = 7) => {
    const sp = new URLSearchParams({ days: String(days) });
    if (category) sp.set("category", category);
    return get(`/data-moat/demand-heat/by-region?${sp.toString()}`);
  },

  getPredictionAccuracy: (category?: string, days = 30) => {
    const sp = new URLSearchParams({ days: String(days) });
    if (category) sp.set("category", category);
    return get(`/data-moat/prediction-accuracy?${sp.toString()}`);
  },

  // ── Generic HTTP helpers (used by DataProvider implementations) ──────────
  get: <T = unknown>(path: string) => get<T>(path),
  post: <T = unknown>(path: string, body: Record<string, unknown> = {}) => post<T>(path, body),
  patch: <T = unknown>(path: string, body: Record<string, unknown> = {}) => patch<T>(path, body),
  delete: <T = unknown>(path: string) => del<T>(path),
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
    currency: CurrencyCode;
  } | null;
  image_url: string | null;
  catalog_miss: boolean;
  catalog_match_id: string | null;
  catalog_match_key: string | null;
  alternatives: Array<{
    catalog_item_id: string | null;
    item_key: string | null;
    title: string | null;
    category: string | null;
    brand: string | null;
    rarity: string | null;
    set_code: string | null;
    image_url: string | null;
    match_score: number;
    match_reason: string | null;
  }>;
  field_confidence: {
    category: number;
    name: number;
    condition: number;
  } | null;
  chain_of_thought: string | null;
  rationale: string[];
  // QuickScan enhancement fields
  scan_session_id: string | null;
  social_proof: {
    collector_count: number;
    is_trending: boolean;
    trend_rank: number | null;
    recent_sold: Array<{
      title: string | null;
      price: number | null;
      currency: string;
      sold_at: string | null;
      source: string | null;
    }>;
    scarcity: {
      listing_count: number;
      supply_trend: string;
      scarcity_score: number;
    } | null;
  } | null;
  duplicate_info: {
    owned_count: number;
    owned_item_ids: string[];
    is_variant: boolean;
    variant_of: string | null;
    set_completion: { owned: number; total: number; pct: number } | null;
  } | null;
  defect_annotations: Array<{
    type: string | null;
    severity: string | null;
    location: string | null;
    description: string | null;
  }>;
  suggested_grade: {
    scale: string | null;
    grade_value: string | null;
    reasoning: string | null;
  } | null;
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

// ---------------------------------------------------------------------------
// Activity Feed
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Unified Search
// ---------------------------------------------------------------------------

export async function unifiedSearch(q: string, limit = 5) {
  return get(`/search/unified?q=${encodeURIComponent(q)}&limit=${limit}`);
}

// ---------------------------------------------------------------------------
// Event Search
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Notification History
// ---------------------------------------------------------------------------

export type NotificationItem = {
  id: string;
  type: string;
  title: string;
  body: string | null;
  data: Record<string, unknown>;
  deep_link: string | null;
  read_at: string | null;
  created_at: string;
};

export type NotificationHistoryResponse = {
  notifications: NotificationItem[];
  total_count: number;
  unread_count: number;
};

export async function getNotificationHistory(params?: {
  limit?: number;
  offset?: number;
  unread_only?: boolean;
}): Promise<NotificationHistoryResponse> {
  const sp = new URLSearchParams();
  if (params?.limit) sp.set("limit", String(params.limit));
  if (params?.offset) sp.set("offset", String(params.offset));
  if (params?.unread_only) sp.set("unread_only", "true");
  const qs = sp.toString();
  return get(`/notifications/history${qs ? `?${qs}` : ""}`);
}

export async function markNotificationRead(notificationId: string) {
  return patch(`/notifications/${notificationId}/read`, {});
}

export async function markAllNotificationsRead() {
  return post("/notifications/mark-all-read", {});
}

// ---------------------------------------------------------------------------
// QuickScan feedback & multi-detect
// ---------------------------------------------------------------------------

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
  items: Array<{
    item_index: number;
    bounding_box: { x: number; y: number; w: number; h: number };
    category_hint: string | null;
    suggested_name: string | null;
    confidence: number;
  }>;
  total_detected: number;
};

export async function multiDetect(
  imageUri: string,
): Promise<{
  items: Array<{
    itemIndex: number;
    boundingBox: { x: number; y: number; w: number; h: number };
    categoryHint: string | null;
    suggestedName: string | null;
    confidence: number;
  }>;
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
