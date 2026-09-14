/**
 * userErrorMessage — the ONE way a caught error becomes member-facing text.
 *
 * WHY (2026-09-14): `err.message` is for the log, never the screen. ~80 toasts,
 * banners and alerts did `err?.message || 'Failed to …'`. For a backend call the
 * fallback never ran, because `ApiError.message` is always set and reads
 *   "POST /purchase/mandates failed (409): Mandate limit reached (3). …"
 * — method, path and status in front of the sentence the server wrote. Other
 * errors carried "Request timed out after 15000ms", "Network request failed" or
 * Postgres text naming a table.
 *
 * Rules, in order:
 *  1. An `ApiError` below 500 gives its server-written `detail` — unless that
 *     detail is the client's synthetic "<METHOD> <path> failed" or internal text.
 *     A 5xx always gives the fallback: that detail is the server's plumbing.
 *  2. A message that looks like plumbing gives the fallback.
 *  3. Any other message is a sentence someone wrote on purpose — Supabase auth's
 *     "Invalid login credentials", usePhotoUpload's own timeout sentence — and
 *     is kept.
 *
 * The raw error still belongs in the log. A call site that already logs its
 * error passes no label. One that does not passes `logLabel`, and the helper
 * logs the raw text exactly when it WITHHOLDS it — so nothing the member used
 * to see is lost, and nothing is reported twice (`logger.error` is a Sentry
 * event, see app/_layout.tsx). A written sentence reaches the member and is
 * not logged, so a wrong password does not page anyone.
 * Gate: `check:raw-error-copy`.
 */
import { logger } from '@/lib/logger';

const SYNTHETIC_API_DETAIL = /^(GET|POST|PUT|PATCH|DELETE|HEAD) \S+ failed$/;

const INTERNAL_SHAPES: RegExp[] = [
  // ApiError.message, or one re-thrown as a plain Error
  /\b(GET|POST|PUT|PATCH|DELETE|HEAD) \/\S*/,
  /\bfailed \(\d{3}\)/,
  // "S3 upload failed with status 403: <?xml …" (usePhotoUpload)
  /\bstatus \d{3}\b/i,
  /<\/?[A-Za-z?!][^>]*>/,
  // timeouts with a millisecond count (withTimeout, supabase.ts)
  /timed out after \d+ ?ms/i,
  // transport
  /network request failed|failed to fetch|^load failed$|aborterror|the (operation|user) aborted/i,
  // Postgres / PostgREST / JWT
  /\bviolates\b|constraint|row-level security|permission denied|relation "|column "|\bPGRST\d*|\bJWT\b|syntax error|invalid input syntax|duplicate key/i,
  // JS runtime errors
  /undefined is not|null is not|cannot read propert|is not a function|unexpected token|json parse error/i,
  /\bsupabase\b|\bpostgrest\b|traceback|\bexception\b/i,
];

const MAX_SENTENCE_LENGTH = 240;

function looksInternal(text: string): boolean {
  return text.length > MAX_SENTENCE_LENGTH || INTERNAL_SHAPES.some((re) => re.test(text));
}

function isApiError(err: unknown): err is { status: number; detail: string } {
  if (!err || typeof err !== 'object') return false;
  const e = err as { name?: unknown; status?: unknown; detail?: unknown };
  return e.name === 'ApiError' && typeof e.status === 'number' && typeof e.detail === 'string';
}

function rawMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (err && typeof err === 'object' && typeof (err as { message?: unknown }).message === 'string') {
    return (err as { message: string }).message;
  }
  return err == null ? '' : String(err);
}

function resolve(err: unknown, fallback: string): { text: string; withheld: boolean } {
  if (isApiError(err)) {
    const detail = err.detail.trim();
    if (err.status >= 500 || !detail || SYNTHETIC_API_DETAIL.test(detail) || looksInternal(detail)) {
      return { text: fallback, withheld: true };
    }
    return { text: detail, withheld: false };
  }
  const trimmed = err instanceof Error || (err && typeof err === 'object') ? rawMessage(err).trim() : '';
  if (!trimmed || looksInternal(trimmed)) return { text: fallback, withheld: true };
  return { text: trimmed, withheld: false };
}

export function userErrorMessage(err: unknown, fallback: string, logLabel?: string): string {
  const { text, withheld } = resolve(err, fallback);
  if (logLabel && withheld && err != null) {
    logger.error(`[${logLabel}] ${fallback} — ${rawMessage(err) || 'no message'}`);
  }
  return text;
}
