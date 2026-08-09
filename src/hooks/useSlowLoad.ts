/**
 * useSlowLoad — say something when a wait stops feeling instant.
 *
 * A spinner answers "is it working?" but never "is it stuck?". Past a few
 * seconds a silent skeleton reads as a frozen screen, and the user's next move
 * is to background the app or kill it — which is exactly when a fetch that was
 * about to land gets thrown away. Claude and ChatGPT solve this by talking to
 * you while you wait; this is that, for any loading path in the app.
 *
 * TWO TIERS, because one message that never changes starts to look frozen too:
 *   - `isSlow`      after 3s  — "we're on it"
 *   - `isVerySlow`  after 10s — "still going, and we know it's long"
 *
 * The timers key off a loading flag GOING TRUE, and are cleared the moment it
 * goes false, so a fast load never flashes a message. Nothing here bounds or
 * cancels the request — `withTimeout` and `installRequestTimeouts` own that.
 * This is presentation only, and deliberately so: a message that also cancelled
 * would turn a slow success into a failure.
 *
 * NOTE both thresholds sit BELOW the bounds that would end the wait — 8s on
 * listItems, 12s in usePaginatedList, 15s on the client backstop — so the
 * notice always appears before a timeout resolves, never after the screen has
 * already moved on.
 */
import { useEffect, useState } from 'react';

/** "This is no longer instant." */
export const SLOW_AFTER_MS = 3_000;
/** "This is genuinely taking a while." */
export const VERY_SLOW_AFTER_MS = 10_000;

export type SlowLoadState = {
  /** True once the wait has passed 3s and is still going. */
  isSlow: boolean;
  /** True once the wait has passed 10s and is still going. */
  isVerySlow: boolean;
};

export function useSlowLoad(
  isLoading: boolean,
  opts?: { slowAfterMs?: number; verySlowAfterMs?: number },
): SlowLoadState {
  const slowAfter = opts?.slowAfterMs ?? SLOW_AFTER_MS;
  const verySlowAfter = opts?.verySlowAfterMs ?? VERY_SLOW_AFTER_MS;

  const [isSlow, setIsSlow] = useState(false);
  const [isVerySlow, setIsVerySlow] = useState(false);

  useEffect(() => {
    if (!isLoading) {
      // Reset synchronously with the flag rather than on a timer, so a refresh
      // that completes quickly starts from silence instead of inheriting the
      // previous wait's message.
      setIsSlow(false);
      setIsVerySlow(false);
      return;
    }

    // `isLoading` is the ONLY dependency, and this effect never writes it —
    // writing a value the effect also depends on tears the effect down on its
    // own render and disarms what follows (learning_effect_cancels_its_own_request,
    // npm run check:effects). isSlow/isVerySlow are outputs, never deps.
    const slowTimer = setTimeout(() => setIsSlow(true), slowAfter);
    const verySlowTimer = setTimeout(() => setIsVerySlow(true), verySlowAfter);

    return () => {
      clearTimeout(slowTimer);
      clearTimeout(verySlowTimer);
    };
  }, [isLoading, slowAfter, verySlowAfter]);

  return { isSlow, isVerySlow };
}
