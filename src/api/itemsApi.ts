/**
 * Items-related API methods: provenance, progress, attributes, images, photos, for-sale toggle.
 */
import { get, post, del, patch, put, postMultipart, API_BASE, getAuthHeaders } from "./httpClient";
import type { ServerUploadResponse } from "./types";

// Photo upload — server-side optimized (preferred)
export const uploadPhoto = (itemId: string, uri: string, mimeType: string) => {
  const formData = new FormData();
  const filename = uri.split("/").pop() || "photo.jpg";
  // React Native's FormData accepts this shape for file uploads
   
  formData.append("file", { uri, name: filename, type: mimeType } as any);
  formData.append("item_id", itemId);
  return postMultipart<ServerUploadResponse>("/photos/upload", formData);
};

// Photo upload — presigned URL fallback (client-side upload)
export const getPresignedUploadUrl = (itemId: string, contentType: string) =>
  post<{
    upload_url: string;
    photo_key: string;
    cdn_url: string;
  }>("/photos/presign-upload", {
    item_id: itemId,
    content_type: contentType,
  });

export const deletePhoto = (photoKey: string) =>
  del(`/photos/${photoKey}`);

export const listItemPhotos = (itemId: string) =>
  get<{
    photos: {
      photo_key: string;
      cdn_url: string;
      size?: number;
      last_modified?: string;
    }[];
    item_id: string;
  }>(`/photos/list/${itemId}`);

// Provenance
export const getProvenance = (itemId: string) =>
  get<{
    item_id: string;
    events: {
      id: string;
      event_type: string;
      timestamp: string;
      note: string | null;
      source: string | null;
      metadata: Record<string, unknown>;
    }[];
    authenticity_signals: string[];
    created_at: string | null;
  }>(`/provenance/items/${encodeURIComponent(itemId)}`);

// Dossier
// The dossier is a heavy server-side aggregation (identity + valuation +
// provenance + price_history + market_comps + completeness). Cold, it routinely
// exceeds the 5 s default REQUEST_TIMEOUT_MS, which aborted the fetch and made
// the "Valuation Report" section render "Could not load report" on every open
// (AbortError, seen 2026-07-22). Give it a report-sized budget; the section
// shows a loading spinner meanwhile.
const DOSSIER_TIMEOUT_MS = 30_000;
export const getDossier = (itemId: string) =>
  get<{
    item_id: string;
    generated_at: string;
    identity: Record<string, unknown>;
    valuation: Record<string, unknown>;
    provenance: Record<string, unknown>[];
    price_history: Record<string, unknown>[];
    market_comps: Record<string, unknown>[];
    photos: string[];
    collections: string[];
    authenticity_signals: string[];
    completeness_score: number;
  }>(`/dossier/${encodeURIComponent(itemId)}`, { timeoutMs: DOSSIER_TIMEOUT_MS });

export const getDossierSummary = (itemId: string) =>
  get<{
    item_id: string;
    identity: Record<string, unknown>;
    valuation: Record<string, unknown>;
    completeness_score: number;
  }>(`/dossier/${encodeURIComponent(itemId)}/summary`);

export const getDossierExportUrl = (itemId: string) =>
  `${API_BASE}/dossier/${encodeURIComponent(itemId)}/export`;

/**
 * Fetch the dossier export as HTML, WITH the bearer token.
 *
 * `getDossierExportUrl` above was being handed straight to `Linking.openURL`,
 * which opens the system browser — and the system browser has no session. The
 * endpoint is `Depends(get_current_user_id)` + `require_plan("pro")`, so a Pro
 * member tapping "Export Report" left the app and landed on a white page
 * reading `{"detail":"Authentication required"}`. A sold feature, on the tier
 * that pays for it, that has never worked.
 *
 * The URL helper is kept because the URL itself is fine; what was wrong was
 * giving an authenticated address to something that cannot authenticate.
 */
export const fetchDossierExportHtml = async (itemId: string): Promise<string> => {
  const res = await fetch(getDossierExportUrl(itemId), {
    headers: await getAuthHeaders(),
  });
  if (!res.ok) {
    // Carry the server's own reason. A 403 here means the plan gate rejected
    // them, which is a different conversation from a 500, and the caller can
    // only say something useful if it knows which.
    throw new Error(`Export failed (${res.status})`);
  }
  return res.text();
};

// Progress Tracking
export const getItemProgress = (itemId: string) =>
  get<{
    item_id: string;
    progress_status: string | null;
    progress_pct: number | null;
    progress_notes: string | null;
  }>(`/items/${encodeURIComponent(itemId)}/progress`);

export const updateItemProgress = (itemId: string, payload: {
  progress_status?: string;
  progress_pct?: number;
  progress_notes?: string;
}) =>
  patch<{
    item_id: string;
    progress_status: string | null;
    progress_pct: number | null;
    progress_notes: string | null;
  }>(`/items/${encodeURIComponent(itemId)}/progress`, payload as Record<string, unknown>);

// Item Attributes / Size
export const updateItemAttributes = (itemId: string, attributes: Record<string, unknown>, itemSize?: string, sizeSystem?: string) =>
  patch<{ ok: boolean; item_id: string }>(
    `/items/${encodeURIComponent(itemId)}/attributes`,
    {
      attributes,
      ...(itemSize !== undefined ? { item_size: itemSize } : {}),
      ...(sizeSystem !== undefined ? { size_system: sizeSystem } : {}),
    },
  );

// Purchase price — the COST BASIS capture path.
//
// Deliberately a server call, not a `supabase.from('items').update()`. `items`
// carries purchase_price (raw) AND purchase_price_eur (FX-normalised), every
// EUR reader sums the second, and the database CANNOT convert: the paired-
// column trigger only copies raw -> eur when the currency is EUR, treating a
// NULL currency AS EUR. A client patch that wrote the amount without the
// currency would therefore file a JPY figure as euros — the ~170x error this
// repo has already shipped from this exact pair. The server converts with
// `convert_to_eur` and writes both halves plus the currency together.
//
// `purchasePrice: null` CLEARS the cost basis (both halves).
export const updateItemPurchase = (
  itemId: string,
  purchasePrice: number | null,
  purchaseCurrency: string,
  purchasedAt?: string,
) =>
  patch<{
    ok: boolean;
    item_id: string;
    purchase_price: number | null;
    purchase_price_eur: number | null;
    purchase_currency: string;
  }>(`/items/${encodeURIComponent(itemId)}/purchase`, {
    purchase_price: purchasePrice,
    purchase_currency: purchaseCurrency,
    ...(purchasedAt !== undefined ? { purchased_at: purchasedAt } : {}),
  });

// Item Images (multi-photo per item)
export const listItemImages = (itemId: string) =>
  get<{
    images: {
      id: string;
      item_id: string;
      image_url: string;
      label: string | null;
      position: number;
      created_at: string | null;
    }[];
    item_id: string;
    total: number;
  }>(`/items/${encodeURIComponent(itemId)}/images`);

export const uploadItemImage = (itemId: string, uri: string, label?: string) => {
  const formData = new FormData();
  const filename = uri.split("/").pop() || "photo.jpg";
  // React Native's FormData accepts this shape for file uploads
   
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
};

export const deleteItemImage = (itemId: string, imageId: string) =>
  del<{ success: boolean; message: string }>(
    `/items/${encodeURIComponent(itemId)}/images/${encodeURIComponent(imageId)}`
  );

export const reorderItemImages = (itemId: string, imageIds: string[]) =>
  put<{ success: boolean; reordered_count: number }>(
    `/items/${encodeURIComponent(itemId)}/images/reorder`,
    { image_ids: imageIds }
  );

// Toggle item for sale
export const toggleItemForSale = (itemId: string, payload: { for_sale: boolean; asking_price?: number }) =>
  put(`/items/${encodeURIComponent(itemId)}/for-sale`, payload as Record<string, unknown>);

// Catalog match — returns best item_key for (title, category) so manual-add
// can populate items.canonical_key. Without this, manually-added items ship
// with canonical_key=null and every Premium JOIN returns empty for them.
export type CatalogMatchHit = {
  item_key: string | null;
  catalog_item_id: string | null;
  title: string | null;
  match_score: number;
  brand: string | null;
  set_code: string | null;
  rarity: string | null;
  image_url: string | null;
};

export type CatalogMatchResponse = {
  best: CatalogMatchHit | null;
  alternatives: CatalogMatchHit[];
};

export const matchCatalog = (title: string, category: string, opts?: { brand?: string; set_code?: string }) =>
  post<CatalogMatchResponse>("/catalog/match", {
    title,
    category,
    ...(opts?.brand ? { brand: opts.brand } : {}),
    ...(opts?.set_code ? { set_code: opts.set_code } : {}),
  });

/**
 * Compute the card valuation for a just-saved item from the catalog market
 * price. The manual-add screen inserts items client-side (direct Supabase), so
 * it calls this right after saving so a catalog-linked item shows a value on
 * its card immediately. Best-effort; `valued=false` when not catalog-linked.
 */
export const revalueItem = (itemId: string) =>
  post<{ ok: boolean; valued: boolean }>(`/items/${encodeURIComponent(itemId)}/revalue`, {});
