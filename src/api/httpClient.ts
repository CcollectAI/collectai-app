/**
 * Shared HTTP client utilities used by all domain API modules.
 *
 * Provides authenticated fetch with retry, timeout, and error handling.
 */
import { API_BASE } from "./config";
import { supabase } from "@/lib/supabase";
import { popSellerAgeGate } from "./sellerAgeGate";
import logger from "@/utils/logger";

// Default 5 s — fast DB-backed endpoints (billing/status, portfolio/*,
// /events, watchlist reads) respond in <2 s on a healthy network. A 5 s
// ceiling means users never see a spinner sit past "this feels slow"; the
// caller's catch fires fast and shows an error/empty state with retry.
// Endpoints that legitimately need longer (marketplace_search across 44
// adapters, intake/scan ML pipelines) pass `timeoutMs:
// LONG_REQUEST_TIMEOUT_MS` explicitly AND own the user-facing progress UI.
const REQUEST_TIMEOUT_MS = 5_000;
export const LONG_REQUEST_TIMEOUT_MS = 90_000;
// Multipart requests are always file uploads (raw image bytes → server-side
// resize + blurhash + S3 put). That routinely exceeds the 5 s fast-read
// default on mobile/cellular, so without a longer budget the upload aborts
// mid-flight and surfaces to the user as "image upload failed". Callers can
// still override via opts.timeoutMs.
export const UPLOAD_TIMEOUT_MS = 60_000;
const MAX_RETRIES = 2;
const RETRY_BASE_MS = 500; // exponential backoff base

export type ReqOpts = { timeoutMs?: number };

export { API_BASE };

// Hard cap on supabase.auth.getSession(). Normally returns from cached
// storage in <50 ms; can occasionally trigger an auto-refresh that hits
// the network, and supabase-js does not have its own per-call timeout on
// that refresh path. Without this cap, a stuck refresh would silently
// freeze every authenticated HTTP call (and therefore every screen's
// loading state) until the OS killed the socket. 2 s lets a normal call
// land while refusing to wait on a hung one.
const AUTH_HEADER_TIMEOUT_MS = 2_000;
// When the fast path above times out, getSession() is almost always mid
// network refresh (expired access token). Firing the request unauthenticated
// here means a protected route rejects it with 401 — which is exactly the
// Delete-Account failure users hit. So before giving up we wait out the
// in-flight refresh with a longer budget. This slower path runs ONLY after
// the 2 s fast path already failed, so normal calls are never delayed.
const AUTH_HEADER_REFRESH_TIMEOUT_MS = 8_000;

// Refresh the token if it's within this window of expiry. supabase-js v2's
// getSession() returns the STORED session without refreshing, so an expired
// access_token comes back verbatim and the API rejects it with 401
// "Authentication required" (the Follow / Add-to-watchlist failures). The
// AppState auto-refresh in AuthProvider keeps it fresh in the common case;
// this is the per-request guard so a stale token never goes out.
const AUTH_EXPIRY_SKEW_MS = 30_000;

async function readAccessToken(timeoutMs: number): Promise<string | null> {
  const result = await Promise.race([
    supabase.auth.getSession(),
    new Promise<{ data: { session: null } }>((resolve) =>
      setTimeout(() => resolve({ data: { session: null } }), timeoutMs),
    ),
  ]);
  const session = result.data?.session;
  if (!session?.access_token) return null;

  // expires_at is epoch SECONDS. If valid and not near expiry, use it as-is.
  const expEpochSec = session.expires_at;
  if (typeof expEpochSec !== "number" || expEpochSec * 1000 - Date.now() >= AUTH_EXPIRY_SKEW_MS) {
    return session.access_token;
  }

  // Token is at/past expiry — force a refresh (bounded so a hung refresh can't
  // freeze the request) rather than send a known-401 token.
  try {
    const refreshed = await Promise.race([
      supabase.auth.refreshSession(),
      new Promise<{ data: { session: null }; error: { message: string } }>((resolve) =>
        setTimeout(() => resolve({ data: { session: null }, error: { message: "refresh timeout" } }), timeoutMs),
      ),
    ]);
    const token = refreshed.data?.session?.access_token;
    if (token) return token;
    logger.warn("[auth] expired token; refreshSession returned no session:", refreshed.error?.message);
  } catch (e) {
    logger.warn("[auth] expired token; refreshSession threw:", e);
  }
  // Dead session — send no auth header (caller surfaces a clean error) instead
  // of an expired token. If 401s persist past this, the logs above prove the
  // refresh itself is failing (refresh-token expired → user must re-login).
  return null;
}

export async function getAuthHeaders(): Promise<Record<string, string>> {
  try {
    // Fast path: cached session returns from storage in <50 ms.
    let token = await readAccessToken(AUTH_HEADER_TIMEOUT_MS);
    if (!token) {
      // Fast path timed out mid-refresh — wait it out rather than send the
      // request unauthenticated (→ 401 on protected routes like DELETE /account).
      token = await readAccessToken(AUTH_HEADER_REFRESH_TIMEOUT_MS);
    }
    if (token) {
      return { Authorization: `Bearer ${token}` };
    }
  } catch {
    // Supabase mock mode or genuinely no session — proceed without auth.
  }
  return {};
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function fetchWithTimeout(
  input: RequestInfo,
  init?: RequestInit,
  timeoutMs: number = REQUEST_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchWithRetry(
  input: RequestInfo,
  init?: RequestInit,
  timeoutMs: number = REQUEST_TIMEOUT_MS,
): Promise<Response> {
  let lastError: Error | undefined;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const res = await fetchWithTimeout(input, init, timeoutMs);
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

/**
 * Detects the seller-age-verification gate (412 with a structured detail)
 * and pops the global confirm modal. Returns true if the user confirmed and
 * the server-side verification succeeded; the caller should then retry the
 * original request once.
 */
async function maybeHandleSellerAgeGate(res: Response): Promise<boolean> {
  if (res.status !== 412) return false;
  try {
    const body = await res.clone().json();
    const detail = body?.detail;
    if (
      detail &&
      typeof detail === "object" &&
      (detail as { error?: string }).error === "seller_age_verification_required"
    ) {
      return await popSellerAgeGate();
    }
  } catch {
    // Body wasn't JSON or didn't match — fall through.
  }
  return false;
}

async function runOnce(method: string, path: string, init: RequestInit, timeoutMs?: number): Promise<Response> {
  return fetchWithRetry(`${API_BASE}${path}`, init, timeoutMs);
}

async function runWithGate(method: string, path: string, init: RequestInit, timeoutMs?: number): Promise<Response> {
  const res = await runOnce(method, path, init, timeoutMs);
  if (res.ok) return res;
  const gated = await maybeHandleSellerAgeGate(res);
  if (gated) {
    // User confirmed + server marked age verified; retry the original request once.
    return runOnce(method, path, init, timeoutMs);
  }
  return res;
}

export async function get<T = unknown>(path: string, opts?: ReqOpts): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await runWithGate("GET", path, { headers: { ...auth } }, opts?.timeoutMs);
  if (!res.ok) throw await parseErrorResponse("GET", path, res);
  return res.json() as Promise<T>;
}

export async function post<T = unknown>(path: string, body: Record<string, unknown> = {}, opts?: ReqOpts): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await runWithGate("POST", path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...auth },
    body: JSON.stringify(body),
  }, opts?.timeoutMs);
  if (!res.ok) throw await parseErrorResponse("POST", path, res);
  return res.json() as Promise<T>;
}

export async function del<T = unknown>(path: string, opts?: ReqOpts): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await runWithGate("DELETE", path, { method: "DELETE", headers: { ...auth } }, opts?.timeoutMs);
  if (!res.ok) throw await parseErrorResponse("DELETE", path, res);
  if (res.status === 204) return {} as T;
  return res.json() as Promise<T>;
}

export async function patch<T = unknown>(path: string, body: Record<string, unknown> = {}, opts?: ReqOpts): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await runWithGate("PATCH", path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...auth },
    body: JSON.stringify(body),
  }, opts?.timeoutMs);
  if (!res.ok) throw await parseErrorResponse("PATCH", path, res);
  return res.json() as Promise<T>;
}

export async function put<T = unknown>(path: string, body: Record<string, unknown> = {}, opts?: ReqOpts): Promise<T> {
  const auth = await getAuthHeaders();
  const res = await runWithGate("PUT", path, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...auth },
    body: JSON.stringify(body),
  }, opts?.timeoutMs);
  if (!res.ok) throw await parseErrorResponse("PUT", path, res);
  return res.json() as Promise<T>;
}

export async function postMultipart<T = unknown>(path: string, formData: FormData, opts?: ReqOpts): Promise<T> {
  const auth = await getAuthHeaders();
  // Do NOT set Content-Type — fetch will auto-set multipart/form-data with boundary
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    method: "POST",
    headers: { ...auth },
    body: formData,
  }, opts?.timeoutMs ?? UPLOAD_TIMEOUT_MS);
  if (!res.ok) throw await parseErrorResponse("POST", path, res);
  return res.json() as Promise<T>;
}

export { REQUEST_TIMEOUT_MS };
