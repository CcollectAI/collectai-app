/**
 * withTimeout — Promise.race wrapper that rejects with TimeoutError if the
 * inner promise does not settle within `ms`.
 *
 * Use on direct supabase queries in loading-gating paths. supabase-js does
 * not ship a per-request timeout, so a stalled HTTPS round-trip (captive
 * portal, slow TLS, server hang) would otherwise leave the UI's `loading`
 * state pinned forever.
 */

export class TimeoutError extends Error {
  readonly ms: number;
  readonly label?: string;

  constructor(ms: number, label?: string) {
    super(`Timed out after ${ms}ms${label ? ` (${label})` : ''}`);
    this.name = 'TimeoutError';
    this.ms = ms;
    this.label = label;
  }
}

export function withTimeout<T>(
  promise: Promise<T> | PromiseLike<T>,
  ms: number,
  label?: string,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new TimeoutError(ms, label)), ms);
    Promise.resolve(promise).then(
      (v) => { clearTimeout(timer); resolve(v); },
      (e) => { clearTimeout(timer); reject(e); },
    );
  });
}
