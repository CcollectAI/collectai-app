/**
 * Shared HTTP client utilities used by all domain API modules.
 *
 * Provides authenticated fetch with retry, timeout, and error handling.
 */
import { API_BASE } from "./config";
import { supabase } from "@/lib/supabase";
import { popSellerAgeGate } from "./sellerAgeGate";
import logger from "@/utils/logger";

// Guarded Sentry — telemetry for the auth-refresh failure path so the actual
// reason (refresh-token revoked / network / timeout) is visible in prod rather
// than only in unread device logs. No-ops when Sentry isn't installed.
let Sentry: { captureMessage?: (msg: string, level?: string) => void } | null = null;
try {
  Sentry = require("@sentry/react-native");
} catch {
  /* not installed */
}

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
// After a TOKENLESS 401 we already know the request needs auth and failed, so
// on the recovery path we wait out session hydration with a much larger budget
// than the fast race above. On cold-start (fresh launch / just after login)
// getSession() can sit behind processLock while autoRefresh holds it, so the
// first request of a screen — the portfolio graph's /portfolio/timeseries —
// would otherwise 401 permanently while a later request in the same batch
// (/portfolio/overview) succeeds once the session finally resolves ~5 s in.
// This only extends the WAIT (no extra refresh), so it cannot cause a refresh
// storm. Kept modest: a stuck (not merely slow) session must NOT hang the
// screen's loading state for long — fail fast, then useFocusEffect refetches on
// the next focus once the session has resolved. 6s catches a slow cold-start
// hydration without pinning a skeleton when the session is genuinely wedged.
const AUTH_HEADER_COLDSTART_RECOVERY_MS = 6_000;

async function readAccessToken(timeoutMs: number): Promise<string | null> {
  const result = await Promise.race([
    supabase.auth.getSession(),
    new Promise<{ data: { session: null } }>((resolve) =>
      setTimeout(() => resolve({ data: { session: null } }), timeoutMs),
    ),
  ]);
  // Return whatever supabase has stored. Keeping it fresh is supabase-js's job
  // (autoRefreshToken + the AppState start/stopAutoRefresh wired in
  // AuthProvider). We deliberately do NOT refresh here: a per-request refresh
  // raced against a timeout abandons an in-flight refresh that keeps running,
  // so a retry fires a SECOND concurrent refresh — two refreshes on one
  // rotating refresh-token can trip Supabase's reuse detection and revoke the
  // session. Staleness is recovered once, centrally, on a real 401 (below).
  return result.data?.session?.access_token ?? null;
}

// One-shot 401 recovery. An authenticated request was rejected, which almost
// always means the stored access token is expired/stale. Force a SINGLE
// refresh (no racing) and return fresh auth headers for one retry. If the
// refresh itself fails the session is unrecoverable on this device, so sign
// out — AuthProvider's onAuthStateChange routes to login and a fresh sign-in
// writes a valid, persisted session — rather than looping on "try again".
async function recoverAuthAfter401(): Promise<Record<string, string> | null> {
  try {
    const { data, error } = await supabase.auth.refreshSession();
    const token = data?.session?.access_token;
    if (token && !error) return { Authorization: `Bearer ${token}` };
    // Definitive auth failure (refresh token revoked/expired/not-found): the
    // stored session is unrecoverable, so sign out → AuthProvider routes to
    // login and a fresh sign-in writes a valid, persisted session.
    logger.warn("[auth] 401 recovery: refreshSession failed:", error?.message);
    Sentry?.captureMessage?.(`auth refresh failed after 401: ${error?.message ?? "no session"}`, "warning");
    try {
      await supabase.auth.signOut();
    } catch {
      /* best effort */
    }
  } catch (e) {
    // Transient (network) failure — surface the 401 but do NOT sign the user
    // out; supabase retries the refresh on its own cadence / next launch.
    logger.warn("[auth] 401 recovery: refreshSession threw:", e);
    Sentry?.captureMessage?.(`auth refresh threw after 401: ${String(e)}`, "warning");
  }
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
    // DIAG: no token even after the slow path — this is the exact state that
    // produces "401 Authentication required" on authenticated writes. logger.error
    // survives TestFlight (info/warn are stripped). Greppable in Console.app.
    logger.error('[DIAG auth] getAuthHeaders: NO TOKEN after refresh window — request will go unauthenticated');
  } catch (e) {
    // Supabase mock mode or genuinely no session — proceed without auth.
    logger.error(`[DIAG auth] getAuthHeaders threw: ${e instanceof Error ? e.message : String(e)}`);
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

// Single-flight guard around recoverAuthAfter401's refresh. A screen that
// mounts fires ~10 authenticated requests at once; if the session was
// momentarily null they ALL 401 together. Without this guard each would call
// refreshSession() concurrently — N refreshes on one rotating refresh-token
// trips Supabase's reuse detection and revokes the session. The guard collapses
// a concurrent burst into ONE refresh whose result every caller shares.
let inFlightRecovery: Promise<Record<string, string> | null> | null = null;
function recoverAuthAfter401Once(): Promise<Record<string, string> | null> {
  if (!inFlightRecovery) {
    inFlightRecovery = recoverAuthAfter401().finally(() => {
      inFlightRecovery = null;
    });
  }
  return inFlightRecovery;
}

// Attach auth headers, run, and recover ONCE from a 401 on an authenticated
// request, then replay with a valid token. `makeInit` rebuilds the request from
// the (possibly refreshed) headers so the retry carries the new token.
//
// Two 401 shapes are recovered (see the httpClient tokenless-401 root cause):
//   1. A token WAS attached but rejected (expired/stale) → force a refresh.
//   2. NO token was attached — getAuthHeaders() returned {} because getSession()
//      was still null when the request fired (cold-start hydration, or a refresh
//      stuck past the 2s+8s window). This is the DOMINANT case in prod: the
//      backend rejects it with a silent 401 (no Authorization header). Re-read
//      the session cheaply first (it has usually hydrated by now → no refresh
//      needed), and only force a refresh if it is still null.
async function authedRequest(
  method: string,
  path: string,
  makeInit: (auth: Record<string, string>) => RequestInit,
  timeoutMs?: number,
): Promise<Response> {
  const auth = await getAuthHeaders();
  let res = await runWithGate(method, path, makeInit(auth), timeoutMs);
  if (res.status === 401) {
    let fresh: Record<string, string> | null = null;
    if (!auth.Authorization) {
      // Tokenless 401: the session is very likely still hydrating (cold-start /
      // just-after-login, behind processLock). Wait it out with the generous
      // cold-start budget rather than the fast 2s/8s race getAuthHeaders uses —
      // otherwise the first request of a screen permanently 401s. This only
      // waits for the EXISTING session to resolve (no refresh → no storm).
      const token = await readAccessToken(AUTH_HEADER_COLDSTART_RECOVERY_MS);
      if (token) fresh = { Authorization: `Bearer ${token}` };
    }
    // Token was rejected, or the cheap re-read still yielded nothing → force a
    // SINGLE shared refresh (signs out if the refresh-token is unrecoverable).
    if (!fresh) fresh = await recoverAuthAfter401Once();
    if (fresh) res = await runWithGate(method, path, makeInit(fresh), timeoutMs);
  }
  return res;
}

export async function get<T = unknown>(path: string, opts?: ReqOpts): Promise<T> {
  const res = await authedRequest("GET", path, (auth) => ({ headers: { ...auth } }), opts?.timeoutMs);
  if (!res.ok) throw await parseErrorResponse("GET", path, res);
  return res.json() as Promise<T>;
}

export async function post<T = unknown>(path: string, body: Record<string, unknown> = {}, opts?: ReqOpts): Promise<T> {
  const res = await authedRequest("POST", path, (auth) => ({
    method: "POST",
    headers: { "Content-Type": "application/json", ...auth },
    body: JSON.stringify(body),
  }), opts?.timeoutMs);
  if (!res.ok) throw await parseErrorResponse("POST", path, res);
  return res.json() as Promise<T>;
}

export async function del<T = unknown>(path: string, opts?: ReqOpts): Promise<T> {
  const res = await authedRequest("DELETE", path, (auth) => ({ method: "DELETE", headers: { ...auth } }), opts?.timeoutMs);
  if (!res.ok) throw await parseErrorResponse("DELETE", path, res);
  if (res.status === 204) return {} as T;
  return res.json() as Promise<T>;
}

export async function patch<T = unknown>(path: string, body: Record<string, unknown> = {}, opts?: ReqOpts): Promise<T> {
  const res = await authedRequest("PATCH", path, (auth) => ({
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...auth },
    body: JSON.stringify(body),
  }), opts?.timeoutMs);
  if (!res.ok) throw await parseErrorResponse("PATCH", path, res);
  return res.json() as Promise<T>;
}

export async function put<T = unknown>(path: string, body: Record<string, unknown> = {}, opts?: ReqOpts): Promise<T> {
  const res = await authedRequest("PUT", path, (auth) => ({
    method: "PUT",
    headers: { "Content-Type": "application/json", ...auth },
    body: JSON.stringify(body),
  }), opts?.timeoutMs);
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
