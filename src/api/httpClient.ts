/**
 * Shared HTTP client utilities used by all domain API modules.
 *
 * Provides authenticated fetch with retry, timeout, and error handling.
 */
import { API_BASE } from "./config";
import { supabase } from "@/lib/supabase";

const REQUEST_TIMEOUT_MS = 15_000; // 15 seconds
const MAX_RETRIES = 2;
const RETRY_BASE_MS = 500; // exponential backoff base

export { API_BASE };

export async function getAuthHeaders(): Promise<Record<string, string>> {
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

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function fetchWithTimeout(
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

export async function fetchWithRetry(
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

export async function parseErrorResponse(method: string, path: string, res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const detail = typeof body?.detail === "string" ? body.detail : `${method} ${path} failed`;
    const code = typeof body?.code === "string" ? body.code : null;
    return new ApiError(method, path, res.status, detail, code);
  } catch {
    return new ApiError(method, path, res.status, `${method} ${path} failed`);
  }
}

export async function get<T = unknown>(path: string): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    headers: { ...auth },
  });
  if (!res.ok) throw await parseErrorResponse("GET", path, res);
  return res.json() as Promise<T>;
}

export async function post<T = unknown>(path: string, body: Record<string, unknown> = {}): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...auth },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await parseErrorResponse("POST", path, res);
  return res.json() as Promise<T>;
}

export async function del<T = unknown>(path: string): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: { ...auth },
  });
  if (!res.ok) throw await parseErrorResponse("DELETE", path, res);
  if (res.status === 204) return {} as T;
  return res.json() as Promise<T>;
}

export async function patch<T = unknown>(path: string, body: Record<string, unknown> = {}): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...auth },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await parseErrorResponse("PATCH", path, res);
  return res.json() as Promise<T>;
}

export async function put<T = unknown>(path: string, body: Record<string, unknown> = {}): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...auth },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await parseErrorResponse("PUT", path, res);
  return res.json() as Promise<T>;
}

export async function postMultipart<T = unknown>(path: string, formData: FormData): Promise<T> {
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

export { REQUEST_TIMEOUT_MS };
