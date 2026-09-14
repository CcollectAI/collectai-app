/**
 * createSharedCount — one number shared by every mounted copy of a control.
 *
 * WHY (2026-09-14, Android walk): the header cluster renders on five tabs plus
 * every `ScreenHeader` screen, and a stack keeps the screens beneath the
 * current one mounted. The inbox badge fetched per instance and polled every
 * 30s per instance; the bell's TTL cache was only written when a response
 * landed, so headers mounting together all fired first. Diagnostics showed
 * nine `chat_dm_requests_v1` timeouts inside three seconds.
 *
 * Three rules, each one of those defects:
 *  - ONE in-flight request: a caller arriving while it is pending joins it.
 *  - A TTL: a fresh value is served without a request.
 *  - Keyed by user: module scope survives a sign-out, and the next account
 *    must not wear the previous one's count.
 *
 * A failed fetch keeps the last value and still uses up the window: with N
 * mounts ticking at different moments, "retry on the next tick" would retry
 * every few seconds through an outage — the storm this module exists to stop.
 * It retries once per window instead. `onError` logs; this module only shares.
 */

type Listener = (value: number) => void;

export type SharedCount = {
  /** The current value for this user, or 0 if none is held for them. */
  peek(userId: string | null): number;
  /** Fetch unless a fresh value or an in-flight request already covers it. */
  refreshIfStale(userId: string | null): Promise<void>;
  subscribe(listener: Listener): () => void;
};

export function createSharedCount(
  fetcher: () => Promise<number>,
  ttlMs: number,
  onError?: (err: unknown) => void,
): SharedCount {
  let value = 0;
  let at = 0;
  let owner: string | null = null;
  let inFlight: Promise<void> | null = null;
  const listeners = new Set<Listener>();

  const emit = () => listeners.forEach((l) => l(value));

  const claim = (userId: string | null) => {
    if (owner === userId) return;
    owner = userId;
    value = 0;
    at = 0;
    inFlight = null; // a request for the previous account must not land here
    emit();
  };

  return {
    peek(userId) {
      return owner === userId ? value : 0;
    },
    refreshIfStale(userId) {
      claim(userId);
      if (!userId) return Promise.resolve();
      if (inFlight) return inFlight;
      if (at > 0 && Date.now() - at < ttlMs) return Promise.resolve();
      const request: Promise<void> = fetcher()
        .then((n) => {
          if (owner !== userId || inFlight !== request) return;
          value = n;
          at = Date.now();
          emit();
        })
        .catch((err) => {
          if (owner === userId && inFlight === request) at = Date.now();
          if (onError) onError(err);
        })
        .finally(() => {
          if (inFlight === request) inFlight = null;
        });
      inFlight = request;
      return request;
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
