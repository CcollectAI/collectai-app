import { API_BASE } from "./config";

const REQUEST_TIMEOUT_MS = 15_000; // 15 seconds
const MAX_RETRIES = 2;
const RETRY_BASE_MS = 500; // exponential backoff base

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
    } catch (err: any) {
      lastError = err;
      // Retry on network/timeout errors, not on abort by caller
      if (attempt < MAX_RETRIES && err.name !== "AbortError") {
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

async function get(path: string) {
  const res = await fetchWithRetry(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed (${res.status})`);
  return res.json();
}

async function post(path: string, body: any = {}) {
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed (${res.status})`);
  return res.json();
}

async function del(path: string) {
  const res = await fetchWithRetry(`${API_BASE}${path}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`DELETE ${path} failed (${res.status})`);
  return res.json();
}

export const collectorsApi = {
  // Watchlist
  fetchWatchlist: () => get("/watchlist/mine"),
  addToWatchlist: (p: any) => post("/watchlist/mine", p),

  // QuickScan
  quickscanSingle: () => post("/quickscan-advanced/single"),
  quickscanBatch: (image_ids: string[]) =>
    post("/quickscan-advanced/batch", { image_ids }),

  // Insights
  fetchInsights: () => get("/insights/personalized"),
  fetchHomeWidget: () => get("/insights/home-widget"),

  // Screenshot intelligence
  analyzeScreenshot: (payload: any) =>
    post("/screenshot-intel/analyze", payload),

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
  }) => post("/predict_v2", payload) as Promise<{
    q10: number;
    q50: number;
    q90: number;
    asof: string;
  }>,

  // Photo upload
  getPresignedUploadUrl: (itemId: string, contentType: string, userId: string) =>
    post("/photos/presign-upload", {
      item_id: itemId,
      content_type: contentType,
      user_id: userId,
    }) as Promise<{
      upload_url: string;
      photo_key: string;
      cdn_url: string;
    }>,

  deletePhoto: (photoKey: string, userId: string) =>
    del(`/photos/${photoKey}?user_id=${encodeURIComponent(userId)}`),

  listItemPhotos: (itemId: string, userId: string) =>
    get(`/photos/list/${itemId}?user_id=${encodeURIComponent(userId)}`) as Promise<{
      photos: Array<{
        photo_key: string;
        cdn_url: string;
        size?: number;
        last_modified?: string;
      }>;
      item_id: string;
    }>,
};
