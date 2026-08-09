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

## `router.back()` is a SILENT no-op — always use `safeGoBack`

`router.back()` does nothing when the navigation stack has nothing to pop. The
handler still runs: the haptic fires, the button animates, the screen doesn't
move. It reads as "the back button is broken", and it strands the user on a
pushed screen with no way out but the tab bar.

A screen can legitimately have an empty stack: a push-notification tap, any
`sparrow://` deep link, a cold start restored onto a non-tab route, or a
`router.replace` (`QuickNavBar` uses replace for all five tabs). None of that is
visible from the call site, which is why the rule is *always guard*, not *guard
where it matters*.

```tsx
import { safeGoBack } from '@/lib/goBack';

onPress={() => safeGoBack(router)}                      // → falls back to /(tabs)
onPress={() => safeGoBack(router, '/(auth)/login')}     // auth screens: never the tab stack
```

Reported on three separate screens before anyone traced it to the shared
pattern. A sweep found **39 bare `router.back()` calls across 24 files, zero
guarded**, and nothing in the repo used `canGoBack()`.

`npm run check:back` (`scripts/check-unguarded-back.mjs`) fails on any bare
`router.back()`. It strips comments **and string literals** with a real scanner
— an `indexOf('//')` version truncated at the `//` inside a URL, so

```ts
const help = 'https://example.com'; router.back();   // was scanned CLEAN
```

slipped through. A gate with a false negative is worse than no gate.

**The native header back button has the same defect.** `headerTintColor` only
styles the native chevron; it still calls the navigator's `goBack()`. Screens
registered with `iconOnlyHeader` get a custom `headerLeft` that routes through
`safeGoBack`. Any header options object that overrides `headerRight` for colour
must override `headerLeft` too — `cameraHeader` renders on black, and the
inherited default (`colors.text`) is invisible there in light mode.

## iOS 26 wraps header buttons in a circular capsule — keep padding SYMMETRIC

iOS 26 draws a translucent "liquid glass" pill around every native bar-button
item, sized to the button's frame. Asymmetric padding or margin offsets the
glyph inside that circle and reads as a mis-aligned icon.

```tsx
style={{ padding: 8, marginRight: 4 }}   // gear sits 4pt left of its circle
style={{ padding: 8 }}                   // centred
```

**The one legal exception is a TRANSFORM.** The back chevron carries
`BACK_CHEVRON_OPTICAL` (`app/_layout.tsx`), a `translateX: -1.5`. Measured with
fontTools against `Ionicons.ttf` (upem 512), `chevron-back`'s ink spans
x[160,352] inside a 512 advance — geometrically centred, dx = 0.00pt. A "<" is
still *optically* right-of-centre inside a circle (one vertex on the left, two
arm ends on the right), which is what reads as mis-aligned. A transform is
layout-neutral, so the capsule stays where the 40×40 frame puts it and only the
glyph moves. Do **not** convert it back into padding or margin.

The same applies to the flat in-body header (`ScreenHeader`): its left/right
clusters are equal-width boxes, so their **contents** must be pinned to the
outer edge (`justifyContent: 'flex-start'` / `'flex-end'`). Otherwise a cluster
that doesn't fill its box drifts inward — which is what happened when
`COMMUNITY_GATED` suppressed the chat icon and left the settings gear floating
~46pt from the screen edge.

## The splash logo: `imageWidth` sizes the CANVAS, and `icon.png` is opaque

`assets/icon.png` is 1024×1024 with an **opaque cream background** (sampled
248,249,244, flat to ±2 across the whole border) and the bird+chest art only
spans x[207,819] — **60% of the canvas**. Two consequences for the
`expo-splash-screen` plugin block in `app.json`:

- `imageWidth` is the width of the whole canvas, not of the logo. The old
  `imageWidth: 64` therefore drew a ~38pt logo. It is now **300** → art ≈180pt
  wide / 229pt tall, which still fits a 320pt-wide iPhone SE.
- `backgroundColor` must be the icon's **own** background (`#F8F9F4`). It used
  to be Tiffany blue `#81D8D0`, and because the PNG is opaque that framed the
  logo in a visible cream square — the "tiny square box". Making the image
  bigger without fixing the colour just makes a *bigger* square.

Swap in a transparent-background asset and this constraint goes away — but keep
a light splash background if you do, because the art is Tiffany blue and would
vanish on a Tiffany-blue field. `src/components/SplashScreen.tsx` (the animated
overlay that follows the native splash) sizes the same asset independently;
change both or the logo jumps size mid-launch.

Splash changes are **native config**: they need a new build, not a reload.

## Never put a tall interactive component in a FlashList `ListHeaderComponent`

FlashList v2 positions **every** cell with `position: 'absolute'`, header
included (`dist/recyclerview/ViewHolder.js:44`), inside a container it sizes
from measured layout. When a tall header measures short, the overflow is still
**drawn** — but on iOS a subview outside its parent's frame is not hit-tested.
It renders perfectly and receives no touches.

The events calendar hit exactly this: the month grid sat at the bottom of a
header that also held the title, search box, filter chips and view-mode tabs.
The grid was visible and completely dead, while everything above it kept
working. Reading `CalendarGrid.tsx` found nothing wrong, because nothing was
wrong — the touch never reached it.

- RN's `VirtualizedList` (`FlatList`, `SectionList`) renders
  `ListHeaderComponent` as a normal in-flow child and is **not** affected.
- Calendar mode now uses `FlatList`; the week view keeps its header outside the
  list entirely. Both are fine.
- Symptom to recognise: **the top of a long header works and the bottom
  doesn't.** That is a hit-area/bounds problem, never a wiring problem — stop
  reading the child component.

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
- [ ] **No bare `router.back()`** — `npm run check:back` is green
- [ ] **Header button padding is symmetric** (iOS 26 capsule centring)
- [ ] **No tall/interactive `ListHeaderComponent` on a FlashList** (hit-area bug)
- [ ] **Pagination stops on a short page**, not on a `total` that counts a different set

## Import Pattern

```tsx
// Theme
import { useAppTheme } from '@/hooks/useAppTheme';

// Motion
import { AnimatedPressable, useEnterReveal } from '@/motion';

// Safe area
import { SafeAreaView } from 'react-native-safe-area-context';
```

## Type scale: the app's `xs` is 10pt, and 10pt is not readable (2026-08-09)

`src/theme/tokens.ts` is `xs:10 sm:12 md:14 lg:16 xl:20 2xl:24`. Reported on
`app/offers.tsx`: *"that screen is very small letters"* — and it was, because the
status line, role pill, confirm row, tracking code, sheet hints and carrier chips
were all on `xs` (10pt), below Apple's ~11pt floor, with body copy on `sm` (12).

Corrected by moving that screen **one step up the existing scale** rather than
inventing sizes — `xs`→`sm`, `sm`→`md`, titles `md`→`lg`, the amount `lg`→`xl`,
and the two hardcoded literals (`11`, `10`) onto tokens. Line-heights tuned with
them.

**Two rules that follow:**

1. **`xs` (10pt) is for nothing a user needs to read.** Not status, not prices,
   not hints. It survives only where a glyph-sized label sits beside an icon.
2. **A new screen starts at `md` for body copy.** `app/tax-reporting.tsx` was
   written at `sm`/`xs` first and had to be corrected the same day — the default
   is what to fix, not each screen.

Whitespace was never the problem. The offers cards had plenty; the type was
simply too small to fill it.
