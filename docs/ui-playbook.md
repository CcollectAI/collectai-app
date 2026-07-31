# Sparrow Collect UI Playbook

A practical guide to building consistent, polished screens in the Sparrow Collect app.

## Screen Template

Every screen should follow this structure:

```tsx
import React from 'react';
import { ScrollView, View, Text, Animated } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable, useEnterReveal } from '@/motion';

export default function MyScreen() {
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
      <ScrollView contentContainerStyle={{ padding: 16 }}>
        <Animated.View style={animatedStyle}>
          {/* Screen content goes here */}
        </Animated.View>
      </ScrollView>
    </SafeAreaView>
  );
}
```

## Theme Integration

Always use theme colors from `useAppTheme()`:

```tsx
const { colors, isDark, toggleTheme } = useAppTheme();

// Available colors:
colors.background  // Screen background
colors.card        // Card/surface background
colors.text        // Primary text
colors.muted       // Secondary/subtle text
colors.accent      // Tiffany accent (#40C9C6)
colors.border      // Borders and dividers
```

## Interactive Elements

### Buttons & Tappable Cards

Always use `AnimatedPressable` instead of `TouchableOpacity` or `Pressable`:

```tsx
<AnimatedPressable
  onPress={() => router.push('/details')}
  style={{
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.border,
  }}
>
  <Text style={{ color: colors.text }}>Card Content</Text>
</AnimatedPressable>
```

### Icon Buttons

```tsx
<AnimatedPressable
  onPress={handleAction}
  style={{
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.card,
    alignItems: 'center',
    justifyContent: 'center',
  }}
>
  <Ionicons name="settings-outline" size={20} color={colors.text} />
</AnimatedPressable>
```

## Loading states

Any screen that fetches has to answer one question: **what happens if the fetch
never comes back?** Get this wrong and the screen shows a skeleton forever, with
no error and nothing in the logs. That shipped twice and was reported as "the app
is stuck loading" (2026-07-25).

The cause is worth knowing: **supabase-js has no per-request timeout**, and a
query fired while the auth session is hydrating doesn't fail fast — it *stalls*
behind the auth lock for the full duration.

```tsx
// 1. Bound every direct Supabase read that gates a skeleton.
const res = await withTimeout(
  supabase.from('items').select(ITEMS_SELECT),
  8_000,
  'listItems',
);
// Log timeouts with logger.error — info/warn are STRIPPED in release builds,
// so a warn here is invisible on the builds where it matters most.

// 2. Don't fetch until auth has hydrated.
const { loading: authLoading } = useAuthContext();
usePaginatedList(fetcher, { enabled: !authLoading });

// 3. In a hand-rolled loader, gate the effect the same way.
useFocusEffect(useCallback(() => {
  if (authLoading) return;
  loadData();
}, [loadData, authLoading]));
```

`usePaginatedList` already enforces the timeout and the gate deadline for every
caller, so prefer it over a hand-rolled list loader.

**If you gate on something, give the gate a deadline.** Waiting on auth means a
wedged session can pin the skeleton by a different route. The hook uses a 5s cap
and fetches anyway.

**Empty ≠ loading.** A screen with no data should render its empty state
("No history yet…"), never a skeleton. If you can't tell them apart on screen,
neither can the user.

**This applies to SAVE paths too, not just loads.** `add-manual.tsx` had three
unbounded `await supabase` calls sitting between `setSaveState("saving")` and
anything that clears it — so a stalled auth lock left the button on "Saving…"
forever: nothing saved, no error, nothing logged. Reported as "impossible to
manually add an item and have it save". Any await between a spinner going up and
coming down must be bounded.

**⚠️ Auth calls are the exception — do not bound them casually.** `withTimeout`
is `Promise.race` and abandons rather than cancels. If that leads to a second
concurrent auth op it can revoke the session (see CLAUDE.md "Loading states" and
`docs/AUTH_AND_WEB_DEPLOY.md`). Safe only when the call neither refreshes nor
retries and there is a recovery path.

## Never hardcode a colour on a themed background

`'#FFFFFF'` looks safe on a brand-coloured button. It is not. The palette
swaps underneath it:

| Palette | `brand.darker` | `accentText` |
|---------|----------------|--------------|
| light | `#44A9A1` | `#ffffff` |
| dark | `#44A9A1` | `#0b1120` |
| high-contrast light | `#002966` | `#FFFFFF` |
| **high-contrast dark** | **`#FFFFFF`** | `#000000` |

`app/subscription.tsx` hardcoded white on a `brand.darker` button, so in
high-contrast dark the primary CTA was **white text on a white button —
invisible**, and the spinner inside it vanished the same way (fixed
2026-07-28). Use `colors.accentText` for any label sitting on `accent` or a
`brand.*` fill; 40+ files already do.

The screen gutter is **16**. `analytics.tsx`, `(tabs)/index.tsx`,
`purchase/index.tsx` and the template above all use it. Subscription used 20
and its buttons sat 4pt narrower per side than the rest of the app — small
enough to look like nothing, obvious when you navigate between screens.

**On `SafeAreaView`:** the checklist below asks for it, but `app/_layout.tsx`
sets `headerShown: true` globally, so screens rendered inside that navigator
already get their insets from the header. `analytics.tsx` and
`subscription.tsx` have no `SafeAreaView` and are correct. Check how a screen
gets its header before "fixing" this.

**But when you do use one, it must come from `react-native-safe-area-context`.**
react-native ships its own `SafeAreaView`, and importing that one is a bug that
is invisible on iOS: it applies insets there and renders as a **plain `View` on
Android**, so the screen looks correct on the platform you develop on and sits
under the status bar and gesture nav on the other. Four files had it (found
2026-07-31 by the deprecation warning in an Android logcat, not by review):
`app/(tabs)/marketplace.tsx`, `BottomSheetModal`, `ContextMenu`,
`MarketplaceFilterPanel`.

```tsx
// WRONG — silently no-ops on Android
import { View, SafeAreaView } from 'react-native';

// RIGHT
import { SafeAreaView } from 'react-native-safe-area-context';
```

`scripts/preflight_android.mjs` fails the build on any `SafeAreaView` imported
from `react-native`, so this cannot come back.

## `accessibilityRole` — an iOS-only value CRASHES Android

Most iOS-only props no-op on Android. `accessibilityRole` does not: react-native
validates it while creating the view and throws `IllegalArgumentException` from
`ReactAccessibilityDelegate`, which is an **uncatchable FATAL EXCEPTION** on the
main thread.

`accessibilityRole="tabbar"` in `QuickNavBar.tsx` did exactly that on
2026-08-01. **38 screens** mount that component, so every screen past the root
tabs killed the app on Android — while two logged-out launch tests reported it
healthy.

```tsx
<View accessibilityRole="tabbar">   // iOS-only → FATAL EXCEPTION on Android
<View accessibilityRole="tablist">  // valid on both
```

Android supports: `none, button, link, search, image, imagebutton, keyboardkey,
text, adjustable, header, summary, alert, checkbox, combobox, menu, menubar,
menuitem, progressbar, radio, radiogroup, scrollbar, spinbutton, switch, tab,
tablist, timer, list, grid, pager, scrollview, horizontalscrollview, viewgroup,
webview, drawerlayout, slidingdrawer, iconmenu, toolbar`. Anything else crashes.
`preflight_android.mjs` checks every value against that set.

## Component Checklist

Before shipping a screen, verify:

- [ ] Uses `SafeAreaView` from `react-native-safe-area-context`
- [ ] Uses `useAppTheme()` for all colors
- [ ] Wraps content in `Animated.View` with `useEnterReveal`
- [ ] Replaces `TouchableOpacity`/`Pressable` with `AnimatedPressable`
- [ ] No hardcoded colors (use theme colors)
- [ ] Responsive to dark mode toggle
- [ ] **Every fetch that gates a skeleton is bounded** (`withTimeout`, or via `usePaginatedList`)
- [ ] **First fetch waits for `!authLoading`**, and the gate has a deadline
- [ ] **Empty state is distinguishable from loading** on screen

## Import Pattern

```tsx
// Theme
import { useAppTheme } from '@/hooks/useAppTheme';

// Motion
import { AnimatedPressable, useEnterReveal } from '@/motion';

// Safe area
import { SafeAreaView } from 'react-native-safe-area-context';
```
