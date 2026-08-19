import { API_BASE } from "./config";
import { getAuthHeaders } from "./httpClient";
import { logger } from '@/lib/logger';

const REQUEST_TIMEOUT_MS = 15_000;

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

// ⚠️ EVERY call here needs a bearer.
//
// `/storage/objects` is `Depends(get_current_user_id)` on the server
// (storage_router.py:170, :256) and these three helpers sent no Authorization
// header at all — so every one of them would have returned 401. It has never
// shown up because NOTHING CALLS `storageApi`; it is wired to no screen. That
// makes it the same defect as the CSV import found on 2026-08-19, minus the
// user report, and it would have surfaced on the day someone connected it.
//
// Caught by `npm run check:authed-fetch`, written for the import bug.
async function get(path: string) {
  const auth = await getAuthHeaders();
  const res = await fetchWithTimeout(`${API_BASE}${path}`, { headers: { ...auth } });
  if (!res.ok) throw new Error(`GET ${path} failed (${res.status})`);
  return res.json();
}

async function post(path: string, body: Record<string, unknown> = {}) {
  const auth = await getAuthHeaders();
  const res = await fetchWithTimeout(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...auth },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed (${res.status})`);
  return res.json();
}

async function del(path: string) {
  const auth = await getAuthHeaders();
  const res = await fetchWithTimeout(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: { ...auth },
  });
  if (!res.ok) {
    let message = `DELETE ${path} failed (${res.status})`;
    try {
      const body = await res.text();
      if (body) {
        const parsed = JSON.parse(body);
        if (parsed.detail) message = `${message}: ${parsed.detail}`;
        else if (parsed.message) message = `${message}: ${parsed.message}`;
      }
    } catch (e) {
      logger.error('[silent-catch] storageApi.ts:47:', e);
      // ignore parse errors — use default message
    }
    throw new Error(message);
  }
  return res.json();
}

export interface PresignedUploadResponse {
  upload_url: string;
  s3_key: string;
  pointer_id: string;
  expires_in: number;
}

export interface PresignedDownloadResponse {
  download_url: string;
  content_type: string | null;
  size_bytes: number | null;
}

export interface ObjectPointer {
  id: string;
  s3_key: string;
  bucket: string;
  content_type: string | null;
  size_bytes: number | null;
  object_type: string;
  related_item_id: string | null;
  created_at: string;
  metadata: Record<string, unknown>;
}

export const storageApi = {
  /** Get a presigned upload URL for uploading a file to S3 */
  getUploadUrl: (
    objectType: string,
    contentType: string,
    filename: string,
    relatedItemId?: string,
    relatedCategory?: string,
  ) =>
    post("/storage/presign-upload", {
      object_type: objectType,
      content_type: contentType,
      filename,
      related_item_id: relatedItemId,
      related_category: relatedCategory,
    }) as Promise<PresignedUploadResponse>,

  /** Get a presigned download URL for a stored object */
  getDownloadUrl: (pointerId: string) =>
    get(
      `/storage/presign-download/${encodeURIComponent(pointerId)}`,
    ) as Promise<PresignedDownloadResponse>,

  /** List objects by type and/or item */
  listObjects: (objectType?: string, relatedItemId?: string, limit = 50) => {
    const params = new URLSearchParams();
    if (objectType) params.set("object_type", objectType);
    if (relatedItemId) params.set("related_item_id", relatedItemId);
    params.set("limit", String(limit));
    return get(`/storage/objects?${params.toString()}`) as Promise<{
      objects: ObjectPointer[];
      total: number;
    }>;
  },

  /** Soft-delete an object pointer */
  deleteObject: (pointerId: string) =>
    del(`/storage/objects/${encodeURIComponent(pointerId)}`),
};
