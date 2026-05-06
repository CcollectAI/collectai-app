/**
 * Items-related API methods: provenance, progress, attributes, images, photos, for-sale toggle.
 */
import { get, post, del, patch, put, postMultipart, API_BASE } from "./httpClient";
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
  }>(`/dossier/${encodeURIComponent(itemId)}`);

export const getDossierSummary = (itemId: string) =>
  get<{
    item_id: string;
    identity: Record<string, unknown>;
    valuation: Record<string, unknown>;
    completeness_score: number;
  }>(`/dossier/${encodeURIComponent(itemId)}/summary`);

export const getDossierExportUrl = (itemId: string) =>
  `${API_BASE}/dossier/${encodeURIComponent(itemId)}/export`;

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
