/**
 * Intake, QuickScan, and catalog suggestion API methods.
 */
import { get, post, postMultipart, getAuthHeaders, parseErrorResponse, API_BASE, LONG_REQUEST_TIMEOUT_MS } from "./httpClient";
import type { IntakeResultResponse } from "./types";

// Intake/QuickScan pipelines run OCR + CLIP + GPT-4o-mini + catalog match
// server-side and can legitimately take 30-60 s. Use the long timeout to
// avoid client-side aborts on slow but valid calls.

// QuickScan
export const quickscanSingle = () =>
  post("/quickscan-advanced/single", {}, { timeoutMs: LONG_REQUEST_TIMEOUT_MS });

// Intake — image-only (vision pipeline: CLIP + GPT-4o-mini + heuristic)
export const intakeImageOnly = (imageUri: string) => {
  const formData = new FormData();
  const filename = imageUri.split("/").pop() || "scan.jpg";
  // React Native's FormData accepts this shape for file uploads

  formData.append("file", { uri: imageUri, name: filename, type: "image/jpeg" } as any);
  return postMultipart<IntakeResultResponse>("/intake/image-only", formData, { timeoutMs: LONG_REQUEST_TIMEOUT_MS });
};

export const quickscanBatch = (image_ids: string[]) =>
  post("/quickscan-advanced/batch", { image_ids }, { timeoutMs: LONG_REQUEST_TIMEOUT_MS });

// URL Import (via Firecrawl)
export const processIntakeUrl = (
  url: string,
  hints?: { category?: string; name?: string; condition?: string },
) =>
  post<IntakeResultResponse>("/intake/url", {
    url,
    ...(hints ?? {}),
  }, { timeoutMs: LONG_REQUEST_TIMEOUT_MS });

// Intake Agent
export const processIntake = (
  barcode?: string,
  barcodeType?: string,
  hints?: Record<string, unknown>,
) =>
  post<IntakeResultResponse>("/intake/barcode-only", {
    barcode: barcode ?? "",
    barcode_type: barcodeType,
    ...(hints ?? {}),
  }, { timeoutMs: LONG_REQUEST_TIMEOUT_MS });

// Save intake result to collection
export const intakeSave = (payload: {
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
  }>("/intake/save", payload);

export const processIntakeWithImage = async (formData: FormData): Promise<IntakeResultResponse> => {
  const auth = await getAuthHeaders();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), LONG_REQUEST_TIMEOUT_MS);
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
};

// Catalog Learning — submit suggestion for unrecognized items
export const submitCatalogSuggestion = (payload: {
  source: "barcode" | "photo" | "manual" | "url";
  input_data: Record<string, unknown>;
  suggested_name: string;
  suggested_category?: string;
}) =>
  post<{
    id: string;
    status: string;
    matched_existing: boolean;
  }>("/catalog/suggest", payload);

// Catalog Learning — list own suggestions with status
export interface MySuggestion {
  id: string;
  source: string;
  suggested_name: string;
  suggested_category: string | null;
  matched_category: string | null;
  mapped_item_key: string | null;
  status: 'pending' | 'mapped' | 'rejected' | 'new_category';
  created_at: string;
}

export const getMyCatalogSuggestions = (opts?: { limit?: number; offset?: number }) => {
  const sp = new URLSearchParams();
  if (opts?.limit) sp.set('limit', String(opts.limit));
  if (opts?.offset) sp.set('offset', String(opts.offset));
  const query = sp.toString();
  return get<{
    suggestions: MySuggestion[];
    total: number;
    limit: number;
    offset: number;
  }>(`/catalog/suggestions/mine${query ? `?${query}` : ''}`);
};

// Screenshot intelligence
export const analyzeScreenshot = (payload: { image_base64?: string; screenshot_id?: string; source?: string; note?: string }) =>
  post("/screenshot-intel/analyze", payload as Record<string, unknown>);

// Catalog Browser
export const browseCatalogItems = (categoryId: string, opts?: {
  q?: string;
  limit?: number;
  offset?: number;
  rarity?: string;
  /** Only return items that have a recent market comp (used by New-in-Catalog). */
  pricedOnly?: boolean;
  /** Filter to a single set/collection (raw set_code). Drives the set-detail grid. */
  setCode?: string;
  /**
   * Server-side sort: 'value' (highest price first, implies pricedOnly on the
   * BE), 'newest' (catalog ingest recency), 'set' (set_code grouping),
   * default 'title'. Drives the category overview rail chips.
   */
  sort?: 'title' | 'value' | 'newest' | 'set';
}) => {
  const sp = new URLSearchParams();
  if (opts?.q) sp.set('q', opts.q);
  if (opts?.limit) sp.set('limit', String(opts.limit));
  if (opts?.offset) sp.set('offset', String(opts.offset));
  if (opts?.rarity) sp.set('rarity', opts.rarity);
  if (opts?.setCode) sp.set('set_code', opts.setCode);
  if (opts?.pricedOnly) sp.set('priced_only', 'true');
  if (opts?.sort) sp.set('sort', opts.sort);
  const query = sp.toString();
  return get<{
    items: {
      id: string;
      category: string;
      item_key: string;
      title: string;
      brand: string | null;
      rarity: string | null;
      notes: string | null;
      has_reference_image?: boolean;
      // Canonical card-CDN thumbnail (Scryfall / ygoprodeck / pokemontcg.io).
      // null when the catalog row has no reference image.
      image_url?: string | null;
      external_id: string | null;
      set_code: string | null;
      estimated_price: number | null;
    }[];
    total: number;
    limit: number;
    offset: number;
    category_id: string;
  }>(`/catalog/${encodeURIComponent(categoryId)}/items${query ? `?${query}` : ''}`);
};

// Latest-comp price for a single catalog item. Backs the museum detail
// screen's market-value fallback when it was opened without an
// `estimated_price` nav param (deep link, older build, sibling tap). Reads the
// precomputed mv_catalog_item_price matview server-side — cheap index lookup.
export const getCatalogItemPrice = (categoryId: string, itemKey: string) =>
  get<{ category: string; item_key: string; estimated_price: number | null }>(
    `/catalog/${encodeURIComponent(categoryId)}/items/${encodeURIComponent(itemKey)}/price`,
  );

// Catalog Collections — discovery "Featured Collections" for a category,
// grouped by set_code from the curated catalog (NOT user ownership).
export const getCatalogCollections = (categoryId: string, limit?: number) =>
  get<{
    collections: {
      collection_key: string;
      display_name: string;
      total_items: number;
      cover_image?: string | null;
    }[];
    total: number;
    category_id: string;
  }>(`/catalog/${encodeURIComponent(categoryId)}/collections${limit ? `?limit=${limit}` : ''}`);
