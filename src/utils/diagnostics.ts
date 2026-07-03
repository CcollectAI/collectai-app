/**
 * On-device diagnostics for the "backend is green but the device shows
 * nothing" class of bug (expired auth token / silent empty / stalled query).
 *
 * IMPORTANT: these intentionally use `logger.error`, NOT info/warn. info/warn
 * are gated behind `__DEV__` and stripped from production / TestFlight builds
 * (see utils/logger.ts), so they would be invisible exactly where we need
 * them. error always logs. The `[DIAG]` tag is greppable in Console.app
 * (macOS) when a TestFlight build is attached — filter by "DIAG".
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
    logger.error(
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
    logger.error(`[DIAG ${tag}] ${parts.join(' ')}`);
  } catch {
    // diagnostics must never break a screen
  }
}

/** Monotonic-ish elapsed-ms helper for load timing. */
export function startTimer(): () => number {
  const t0 = Date.now();
  return () => Date.now() - t0;
}
