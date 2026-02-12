import { API_BASE } from "./config";

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

async function get(path: string) {
  const res = await fetchWithTimeout(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed (${res.status})`);
  return res.json();
}

async function post(path: string, body: Record<string, unknown> = {}) {
  const res = await fetchWithTimeout(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed (${res.status})`);
  return res.json();
}

async function del(path: string) {
  const res = await fetchWithTimeout(`${API_BASE}${path}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`DELETE ${path} failed (${res.status})`);
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
