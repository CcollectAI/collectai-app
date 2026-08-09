/**
 * On-device diagnostics for the "backend is green but the device shows
 * nothing" class of bug (expired auth token / silent empty / stalled query).
 *
 * IMPORTANT: FAILURE diagnostics intentionally use `logger.error`, NOT
 * info/warn. info/warn are gated behind `__DEV__` and stripped from production
 * / TestFlight builds (see utils/logger.ts), so they would be invisible exactly
 * where we need them. error always logs. The `[DIAG]` tag is greppable in
 * Console.app (macOS) when a TestFlight build is attached — filter by "DIAG".
 *
 * SUCCESS diagnostics (a load that returned fine, an auth check that passed)
 * log at `logger.info` instead: they're only useful while actively debugging on
 * a dev machine (visible in the Metro console), and logging them at `error`
 * popped a red LogBox on EVERY category/screen load in dev. Downgrading success
 * to info keeps the noise out of dev and out of prod while errors still surface.
 *
 * Every function is best-effort and self-contained: a diagnostic must never
 * throw into, slow, or otherwise change the behaviour of the screen it probes.
 */
import { supabase } from '../lib/supabase';
import logger from './logger';

/**
 * Snapshot the current Supabase auth session. This is the single most useful
 * signal for the recurring 401/empty-list reports: it tells us whether the
 * device actually has a live, non-expired token at the moment a screen loads.
 */
export async function logAuthState(tag: string): Promise<void> {
  try {
    const { data: { session }, error } = await supabase.auth.getSession();
    if (error) {
      logger.error(`[DIAG ${tag}] getSession error: ${error.message}`);
      return;
    }
    if (!session) {
      logger.error(`[DIAG ${tag}] NO SESSION — unauthenticated; RLS reads will return []`);
      return;
    }
    const expMs = session.expires_at ? session.expires_at * 1000 : 0;
    const now = Date.now();
    const ttlS = expMs ? Math.round((expMs - now) / 1000) : null;
    const expired = expMs ? expMs < now : null;
    // Success path — info only (dev console), so it doesn't pop a red LogBox on
    // every screen load. An actually-expired token is still worth an error.
    const log = expired ? logger.error : logger.info;
    log(
      `[DIAG ${tag}] auth ok` +
        ` user=${(session.user?.id ?? '?').slice(0, 8)}` +
        ` token=${session.access_token ? 'present' : 'MISSING'}` +
        ` ttl=${ttlS}s` +
        ` expired=${expired}`,
    );
  } catch (e) {
    logger.error(`[DIAG ${tag}] logAuthState threw: ${e instanceof Error ? e.message : String(e)}`);
  }
}

/**
 * Structured one-liner for a load outcome. Pass whatever is diagnostic for the
 * surface — counts, an error message, elapsed ms, whether it timed out, etc.
 * Renders as `[DIAG <tag>] k1=v1 k2=v2` so it's both greppable and scannable.
 */
export function logLoad(tag: string, info: Record<string, unknown>): void {
  try {
    const parts = Object.entries(info).map(([k, v]) => {
      const val =
        v instanceof Error ? v.message : typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v);
      return `${k}=${val}`;
    });
    // Only an actual failure (an `error` key, by convention) logs at error level
    // — that's the case worth a red LogBox in dev and worth surviving into
    // TestFlight. A successful load logs at info (dev console only, stripped in
    // prod) so it stops popping LogBox on every screen load.
    const failed = 'error' in info && info.error != null;
    const log = failed ? logger.error : logger.info;
    log(`[DIAG ${tag}] ${parts.join(' ')}`);
  } catch (e) {
    logger.error('[silent-catch] diagnostics.ts:77:', e);
    // diagnostics must never break a screen
  }
}

/** Monotonic-ish elapsed-ms helper for load timing. */
export function startTimer(): () => number {
  const t0 = Date.now();
  return () => Date.now() - t0;
}
