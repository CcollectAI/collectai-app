import { API_BASE } from "./config";

async function get(path: string) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed (${res.status})`);
  return res.json();
}

async function post(path: string, body: any = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed (${res.status})`);
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
};
