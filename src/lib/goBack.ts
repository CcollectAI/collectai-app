/**
 * safeGoBack — `router.back()` that always does something.
 *
 * `router.back()` is a **silent no-op** when the navigation stack has nothing
 * to pop. The press handler still runs: the haptic fires, the button animates,
 * and the screen sits there. To a user that reads as "the back button is
 * broken", and it leaves them stranded on a pushed screen with no way out
 * except the tab bar.
 *
 * A screen can be entered with an empty stack in several ordinary ways:
 *   - a push-notification tap that deep-links straight into the screen
 *   - any `sparrow://` deep link opened from outside the app
 *   - a cold start restored onto a non-tab route
 *   - `router.replace(...)`, which QuickNavBar uses for all five tabs
 *
 * There is no way to distinguish those from source, which is exactly why the
 * guard belongs at every call site rather than in a case-by-case fix.
 *
 * Enforced by `scripts/check-unguarded-back.mjs` (npm run check:back), which
 * fails on a bare `router.back()` anywhere under app/ or src/.
 */
import type { Router } from 'expo-router';

/** Where to land when there is nothing to pop. The portfolio tab is home. */
const DEFAULT_FALLBACK = '/(tabs)';

export function safeGoBack(
  router: Pick<Router, 'back' | 'canGoBack' | 'replace'>,
  fallback: string = DEFAULT_FALLBACK,
): void {
  if (router.canGoBack()) {
    router.back();
    return;
  }
  router.replace(fallback as Parameters<Router['replace']>[0]);
}
