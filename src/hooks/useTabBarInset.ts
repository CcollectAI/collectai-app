/**
 * useTabBarInset — bottom space a `(tabs)` screen must reserve for the tab bar.
 *
 * `ExternalTabBar` is rendered at the root stack, OUTSIDE the Tabs navigator
 * (the navigator's own bar dropped touches in production — see
 * memory/project_tab_bar_bug_saga.md), and it is `position: 'absolute';
 * bottom: 0`. Nothing reserves layout space for it, so any scroll content that
 * ends with a hand-picked `paddingBottom` has its last rows drawn UNDERNEATH
 * the bar. `EXTERNAL_TAB_BAR_HEIGHT` was exported but nothing consumed it.
 *
 * Derive the number from the bar instead of guessing it: the bar's own height
 * is `EXTERNAL_TAB_BAR_HEIGHT + Math.max(insets.bottom, 10)`, so this returns
 * exactly that, plus a little breathing room.
 *
 * Only for screens inside `(tabs)` — the bar returns null everywhere else, and
 * on those screens this would just add dead space.
 */
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { EXTERNAL_TAB_BAR_HEIGHT } from '@/components/ExternalTabBar';

export function useTabBarInset(extra = 16): number {
  const insets = useSafeAreaInsets();
  return EXTERNAL_TAB_BAR_HEIGHT + Math.max(insets.bottom, 10) + extra;
}
