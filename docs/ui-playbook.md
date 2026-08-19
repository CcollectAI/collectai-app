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
`MarketplaceFilterPanel` (deleted 2026-08-12 with the market hub).

```tsx
// WRONG — silently no-ops on Android
import { View, SafeAreaView } from 'react-native';

// RIGHT
import { SafeAreaView } from 'react-native-safe-area-context';
```

`scripts/preflight_android.mjs` fails the build on any `SafeAreaView` imported
from `react-native`, so this cannot come back.

### The branding sweep, and the gate — `npm run check:brand-colors` (2026-08-19)

Measured rather than guessed: **858 hex literals**, of which **470** sit in
files that legitimately DEFINE colour (the four palettes, the 54 category
tints, franchise colours). Flagging the other 388 would have been noise — most
are on fixed scrims, camera overlays and photo gradients, where nothing
inverts.

The gate checks the ONE pattern that actually breaks: a hardcoded `color:` /
`tintColor:` near-white or near-black, sitting on a `backgroundColor` taken
from a THEME token. **Three live instances, all fixed** — `app/chat/new.tsx`,
`src/components/PriceFeedbackSection.tsx` (whose comment literally read *"Button
text on brand background"* while doing the thing this rule forbids), and the
vestigial `src/app/+not-found.tsx`.

**The fourth was correctly left alone, and it is the one to remember.**
`Button.tsx`'s `danger` variant hardcodes white on `colors.danger` — and that
is RIGHT: danger is red in all four palettes, while `accentText` is `#000000`
in high-contrast dark, so "fixing" it would put **black on red**. The rule is
about a fill that *inverts*; danger does not. It is allowlisted with that
argument, because the next sweep will find it again.

**And the gate itself was wrong first.** Written with a ±6-line window, it went
GREEN when the defect was reintroduced under a 4-line explanatory comment —
the comment pushed the `backgroundColor` out of range. A gate that passes on
the exact defect it was written for is worse than no gate, because it is
trusted. Widened, then proven red. *Always reintroduce the bug and watch it
fail.*

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

## The tab bar reserves NO space — and there is now a gate

`ExternalTabBar` is `position:absolute` at the ROOT stack (the navigator's own
bar dropped touches in production), so **nothing reserves layout space for it**:
58pt + safe-area = 68pt flat, ~92pt notched. Any `(tabs)` scroll content ending
in a hand-picked `paddingBottom` draws its last row underneath the bar.

Derive it, never guess it:

```tsx
import { useTabBarInset } from '@/hooks/useTabBarInset';
const bottomInset = useTabBarInset();
contentContainerStyle={[styles.content, { paddingBottom: bottomInset }]}
```

**`npm run check:tab-inset`** (in `verify:prebuild`) fails on any vertical
scroller in `app/(tabs)/` whose bottom padding cannot clear the bar. Horizontal
rails and `scrollEnabled={false}` grids are skipped; a scroller genuinely not
under the bar (inside a pageSheet `<Modal>`, say) carries
`// tab-bar-inset-ok: <reason>` — the reason is required.

Written 2026-08-11 after the literal-padding bug was found on 9 scrollers across
5 screens — grep had suggested 5. Two traps it exposed:

- **A trailing spacer view is invisible to the gate.** Portfolio had BOTH a
  100pt spacer and the inset, double-padding by ~190pt. The gate reads
  `contentContainerStyle`, not children — remove the spacer when you add the
  inset.
- **`flexGrow:1 + justifyContent:'center'` still needs it.** A centred empty
  state centres against the full height and sits ~46pt low, half behind the bar.

## Grid cards are already equal height — claim the space, don't fake it (2026-08-12)

The heart/eye cluster on the marketplace tiles sat at a different height on
every card, which reads as sloppy alignment even though each tile was
internally correct. The cluster was simply the last child of a top-down stack,
so its position depended on how much text happened to sit above it: a 1- vs
2-line title, the optional "n watching" row, the optional seller name, the
"You" pill.

**The fix is not a fixed height, a minHeight, or a measured layout.** A
FlatList `columnWrapperStyle` row is a flex row, and a flex row's default is
`alignItems: 'stretch'` — so the two tiles beside each other were **already**
the same height. The shorter one just left its spare height as dead space under
the text and nobody claimed it.

```tsx
// the card body claims the leftover height…
cardBody:    { padding: 11, gap: 4, flex: 1 },
// …so the action cluster has a floor to sit on
cardActions: { marginTop: 'auto', alignSelf: 'flex-end' },
```

`marginTop: 'auto'` pins to the bottom, `alignSelf: 'flex-end'` to the right.
Both tiles in a row then land their controls on one line, for free, at any
content length.

Two things worth carrying to the next card grid:

- **`minHeight` is the wrong instinct here.** It picks a number that is wrong
  for one of the two tiles and re-breaks the moment the type scale changes.
- **A negative margin on the action row is a glyph-alignment tool, not a layout
  one.** A 32pt touch target around a 20pt icon puts 6pt of padding inside the
  box, so the glyph sits ~6pt inboard of the text gutter. `marginRight: -5`
  pulls the *box* out so the *glyph* lines up with the text above it; the touch
  target and `hitSlop` are unchanged.

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
- [ ] **`(tabs)` scrollers clear the bar** — `npm run check:tab-inset` is green

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

### …but a uniform bump flattens the hierarchy (2026-08-11)

Same screen, reported again two days later: *"the text sizes are off, the screen
has unprofessional ui."* Moving **every** style one step up had landed 12 of
`app/offers.tsx`'s 17 text styles on `md` (14) — status line, role pill, confirm
ticks, tracking caption, sheet hints, every button label and the view link, all
the same size as the body copy. Nothing receded, so nothing led. Next to
`/listings` (card title `sm`, meta `xs`) and `/listing/[id]` (title `xl`, body
`md`, meta `xs`) it did not read as the same app.

**A screen needs three levels, and the floor is `sm` — not `md`.** Rule 1 above
still holds: `xs` stays banned for anything a user reads. Build the hierarchy by
pushing the lead UP, not by pushing everything else down:

| level | token | what belongs there |
|---|---|---|
| lead | `xl` / `lg` | the amount, the listing title, a tracking code someone reads aloud |
| body | `md` | status, prose, button labels, links, sheet copy |
| caption | `sm` | pills, confirm ticks, field labels, passive notes |

Two defects the flat pass left behind, both worth grepping for elsewhere:

- **`lineHeight` below its own `fontSize` is never intentional.** `trackHint`
  was `fontSize: 14` / `lineHeight: 15` on a deliberately two-line string, so
  the lines collided. Keep every line-height at **≥1.35×** its font size.
- **Two controls in one form must be one size.** The carrier picker rendered at
  14 with the tracking input directly beneath it at 16.

**CLOSED 2026-08-16.** `app/listings.tsx` carried raw `fontSize: 9`, `10` and
`11` literals — the very thing rule 1 bans — for as long as this section had
said so. All four (`badgeText`, `stockTagText`, `watchText`, `cardSellerName`)
are now `text.sm` with `lineHeight: 17`, so the two screens finally point the
same way.

Worth noting how it was found: not by reading the screen, but by **checking
whether the open items this playbook records were still open.** A doc that
lists known divergences is only useful if something periodically re-runs them —
`grep -cE "fontSize: (9|10|11)\b" app/listings.tsx` took a second and the
answer was still 4.

## A count in a badge is a promise the destination has to keep (2026-08-13)

`/listings` renders an offers badge whose number comes from
`countOffersNeedingAction` (`src/api/p2pApi.ts`). Tapping it opened
`app/offers.tsx` — which never called that helper. The screen listed every
offer in server order, all rendered identically, so a member was told "3 need
you" and then had to read the status line on each card to work out which three.
The helper existed, the badge used it, and the destination didn't.

That is the [[learning_complete_feature_reachable_from_nowhere]] shape at UI
scale: correct code, connected to nothing on the screen where it matters.

**The rule: the destination of a count uses the same predicate the count does.**
Not a re-implementation of it, the same exported function — a second copy of
"needs my action" drifts from the badge and then the badge is a lie.

What that looked like here:

- **Order by rank, not by recency alone.** Your move → live trade → waiting on
  them → finished, newest first inside each rank. Recency-only ordering buries
  a decision under six things you can't act on.
- **Mark the rows, don't just move them.** A `YOUR MOVE` pill in `colors.accent`
  with `colors.accentText`, the same accent the action buttons carry, so "this
  is yours to move" and "this is the button that moves it" read as one thing.
- **Restate the count on arrival.** "2 offers need you" under the segmented
  control, from the same helper. Landing on a screen that never mentions the
  number again is what made the badge feel untrustworthy.
- **Recede what's finished.** `opacity: 0.68` and no shadow for terminal
  offers. De-emphasis, not disabling — the card stays readable, it just stops
  competing.

### Two traps in that de-emphasis, both of which I shipped and had to fix

**A card can be terminal by status and still need you.** A completed trade you
have not graded yet is `status: 'completed'` — terminal — and `can_grade`, which
means it needs action. Written as `!open && !live` it rendered dimmed history
*and* an accent YOUR MOVE pill: two contradictory claims on one card. Needing
action has to win: `!open && !live && !mine`.

**`borderColor` is a four-edge shorthand.** The role stripe is
`borderLeftColor`, and a highlight style applied later in the array set
`borderColor` — which addresses the left edge too. RN's edge-specific props do
take precedence, but relying on that is invisible to the next reader and one
refactor away from erasing the buying/selling signal on exactly the cards a
user studies hardest. Re-assert the stripe in the same object.

### Feedback during an action is not the same as disabling the buttons

Every action on that screen is a request plus a refetch of the whole list, and
the only feedback was `AnimatedPressable`'s `disabled` styling — every button on
the card at 50% opacity. "These went dead" and "this is working" looked
identical, and one of them is alarming. A labelled `ActivityIndicator` in the
action row says which it is. The awaits are bounded by httpClient's request
timeout, per the "Loading states" rule above — a spinner that can outlive its
call is the bug that rule exists for.

## A profile that opens with three card idioms in a row (2026-08-19)

Reported as *"the profile has a very cluttered format… the trading section is
not well integrated… the collects is stacked on top of each other."* All three
are the same underlying problem, and none of them is spacing.

**Three visual languages before the first CTA.** `UserStatsSection` drew a
bordered stats box; `TradeReputationSection` drew *another* bordered box with a
small muted "Trading" label; `UserCategoriesSection` opened with a 16/700
section heading. Same screen, three ways of saying "here is a block".

- **Trading is now a STRIP under the stats row** — no border, no fill, no
  heading. It answers the same question the stats row does ("who is this
  collector"), so it reads as the last line *of* that block instead of the
  first line of a new one. One card fewer, and the integration complaint goes
  with it.
- **Collects is ONE frame with hairline-separated rows.** Every category had
  been rendering its own `borderWidth: 1, borderRadius: 12` box with an 8pt
  gap, so a collector in six categories got six stacked outlines — literally
  "stacked on top of each other". Same failure the watchlist card had: a list
  of framed boxes reads as a wall, not a list. Separators go BETWEEN rows only;
  a trailing hairline reads as a row that never arrives.

Two type violations went with it, both found by re-reading the type-scale
section while in there: `catMeta` at 11pt and `selfNote` at `xs` (10pt).

**The generalisable bit:** "cluttered" almost never means "needs more padding".
Here it meant *three different frames competing to be the page's first block* —
count the borders on a screen before reaching for spacing.

## The collection row lost its share button and its purchase figures (2026-08-19)

Reported as *"the items page has a little listing send button that doesn't
work"* and *"the item is very cluttered"*. Both were right, and the first was
worse than clutter.

**The send button was DEAD.** `app/(tabs)/items.tsx` rendered
`<ShareToChatSheet>` **only inside the first-run `if (loading &&
hasEverHadItems !== true)` branch** — the empty/hero state. On every screen
where a row is actually visible, the sheet does not exist, so tapping the
paper-plane set `shareFor` and opened nothing. Not a broken handler: a correct
handler whose sheet was mounted under a condition that excludes the only screen
the button appears on. The section below still describes share-to-chat on the
**marketplace tile**, which works and stays.

Removed with its whole chain — button, `onShare` prop, `handleShareItem`,
`shareFor`, `sharePayload`, the sheet and the import — because a handler with
no button is how a dead path survives a cleanup.

**And the row carried four figures.** Value, source chip, `Paid EUR X`, and a
P/L delta, stacked in a right column on a ~56pt row. That is a position
blotter, not a reference row — the same rule that took two full-width buttons
off the watchlist card. Both numbers live on the item's own screen, where there
is room to read them, and portfolio-wide P/L has its own surface in analytics.

Seven tests pinned the removed behaviour. They were **replaced, not deleted**:
the useful half of a test for a removed feature is the guard against it coming
back.

### …and then the category pill went too (same day)

The row also carried a `CategoryPill`. The list is grouped BY category and the
section heading sits directly above every row, so the pill repeated that
heading **once per item** — and put N touch targets where the group needs one,
each competing with the row's own tap, which opens the item.

**The heading is the tap target now**, with a chevron, opening
`/categories/[slug]`. Only the collection name survives on the row, as plain
text: it is the one thing the heading does not already say.

Generalisable: **a grouped list should not repeat its group key in every
member.** If a row's metadata is identical to the header above it, the header
is the place for it — including the affordance.

## Share to chat lives on the card, top-right (2026-08-13)

`src/components/share/ShareToChatSheet.tsx`, wired into the marketplace tile
(`app/listings.tsx`) and the collection row (`ItemsListItem`).

A member spots something and wants one specific person to see it. The only
existing route was the OS share sheet, which leaves the app and hands the
recipient a bare link. This sends the item into a Sparrow DM instead, through
`sendChatMessage` (EC2) — **not** the equivalent Supabase RPC, which writes the
row but skips `_notify_new_message`, so the recipient would get a message with
no push.

**Placement.** The heart/eye cluster owns the bottom-right of the tile body (see
"Grid cards are already equal height"), so share takes the opposite corner. On
the tile it is `position: absolute`, so it costs the body no vertical space and
cannot fight `cardActions`' `marginTop: 'auto'`.

**On a row, "top right" is not an overlay.** `ItemsListItem` is ~56pt tall and
centres its children, so an absolutely-positioned button lands on the value.
Putting it at the top of the right-hand column gets the same corner, and on a
flex row it usually costs no height at all — the row is as tall as its tallest
child, and the name/meta/detail column is normally taller than the value stack.
Hidden in multi-select, where every tap belongs to selection.

**Only accepted threads.** `listInboxThreads` reads `v_chat_inbox_v1`, which has
no pending rows. DM requests exist so a stranger cannot put content in your
inbox; a share picker that could reach non-accepted threads would be a hole
straight through that rule. Nothing here needs to filter — the view already did.

**No empty shelf.** A member with no chats gets a sentence saying why and what
to do, plus the OS share as the route that does work — the same objection that
removed the Browse/My-offers segment (P2P spec §10a): do not show someone a
control for something they do not have.

**Formatting stays with the caller.** The sheet takes `priceLabel`, already
formatted, and never touches money itself. The marketplace passes a price
converted to the viewer's currency (a listing can be in any of the 7, and
sending "€8000" for a ¥8000 card is the bug `ListingCard` converts to avoid);
the Items tab passes `null` when `isUnpriced`, because "€0" would state a
valuation the app elsewhere refuses to show.

## Three equal controls read as three equal decisions (2026-08-13)

`app/market-movers.tsx` stacked three identical full-width segmented controls —
direction, window, scope — about 150pt of chrome before the first row of data.
Reported as *"there are like 3 filters, this is visually messy and
unprofessional"*, and the mess was hierarchy, not spacing: every control had the
same width, the same weight and the same type size, so nothing said which one
mattered.

**They are not the same kind of control.** Gainers and losers are different
questions — the list means something different depending on which is selected.
Window and scope only refine the same answer. Give the primary the full-width
segmented treatment and let the refinements shrink to content-width chips that
share one row:

```tsx
<Segmented value={direction} … />          // full width, `md` type
<View style={styles.filterRow}>            // one row, gap 8, wraps
  <MiniSegmented value={metricWindow} … /> // sized to its labels
  <MiniSegmented value={scope} … />
</View>
```

`MiniSegmented` differs from `Segmented` in one property: its buttons have no
`flex: 1`. That is the whole trick — without it a group sizes to its labels and
two fit on one line.

Also bump the primary to `md` while you are there. A 12pt primary next to 12pt
secondaries is the other half of why the three bars read as one undifferentiated
block.

### While you are in a screen like this, check what it says when the fetch fails

The same screen caught a `.catch` that set `movers = []` and fell through to
the empty state, so a failed request rendered **"No movers to show right
now."** — a confident claim about the market made on the strength of a request
that never came back. And it logged with `logger.warn`, which release builds
strip, so there was nothing to find afterwards either.

`None` is not `[]`: could-not-ask and asked-and-got-nothing are different
answers and must render differently
([[learning_empty_answer_rendered_as_zero]]). Failure now gets its own state
with a retry, driven by a nonce so the effect never depends on a value it
writes.

### …and check what the ranking actually surfaces (2026-08-13)

Fixing the filters made the screen tidy and left it saying something silly.
Measured on prod, the top-20 gainers ranked by percentage:

| price | 7d % | actual move | rank |
|---|---|---|---|
| €3.60 | +96.7% | **€1.77** | 1st |
| €2.00 | +75.4% | **€0.86** | 2nd |
| €1,862 | +44.1% | **€569.71** | 13th |
| €1.24 | +37.2% | **€0.34** | 19th |

An 86-cent move outranked a €570 one, and 11 of the top 20 were under €10 — as
the headline of a **paid** feature. Not thin data either: `comps_30d` ran 12–78,
so those are real moves. They are just economically nothing, because a
percentage on a cheap item is mostly rounding.

Three changes, and the first is the one that matters:

- **Show the money next to the percentage.** `+96.7%` and `+€1.77` together are
  honest; either alone is not. Computed SERVER-side from the same two columns
  the percentage comes from — never recomputed on the client, because two
  derivations of one number drift and a row whose € and % disagree is worse
  than a row with neither.
- **Let the member choose the axis.** `rank=pct|abs` on `/catalog/top-movers`.
  Ranking by euros returns a completely different and far more useful list:
  €569, €123, €58, €56 on €166–€1,990 items.
- **Floor the percentage list** at €5 (`PCT_MIN_PRICE_EUR`, shared by the widget
  and the screen so they cannot answer the same question differently). Not
  applied to the euro ranking, where trivial moves sort themselves to the
  bottom and a floor would hide data for nothing.

**Say what you hid.** The caption reads "Ranked by percentage change · items
under €5 hidden". A filter nobody can see reads as "this is everything" — the
same silent-cap failure as a screen that renders a failed fetch as an empty
state.

## Back buttons: every pushed screen already has one — and now a gate says so (2026-08-14)

Asked to "add back buttons on all screens, or logically where they belong". The
audit says they are already there:

```
[back-affordance] PASS — 61 pushed screen(s): 59 inherit the native header,
                         2 suppress it and provide their own back control.
```

`app/_layout.tsx` sets `headerShown: true` globally, so a pushed route gets the
native chevron for free. The only two that turn it off — `category-browse.tsx`
and `categories/[categoryId].tsx` — replace it with `<ScreenHeader />`, whose
`showBack` defaults to true. They do that on purpose: the flat header keeps the
back/chat/settings icons out of the iOS 26 glass capsules.

**Tab roots have none, and should not.** There is nothing to pop from a tab, and
a chevron there would be the only one of its kind —
`app/(tabs)/marketplace.tsx` passes `asTab` to `/listings` specifically to
suppress it, while the same screen reached as a pushed route *does* show back.
So "the Marketplace screen is missing a back button" is the tab root, and it is
consistent with Items, Events and Search rather than out of step with them.

`npm run check:back-affordance` encodes exactly that distinction: a screen fails
only if it hides the header AND provides no `ScreenHeader`, `safeGoBack`,
`headerLeft` or back icon. Tab roots, auth screens and layouts are exempt.

**Proving it fails.** The first attempt removed `<ScreenHeader>` from
`category-browse.tsx` and the gate still passed — which looked like a false
negative and was not: that file has a second `arrow-back` control at line 401,
so it genuinely was not a dead end. A synthetic screen with `headerShown: false`
and nothing else does fail it. Pick a proof subject with NO other affordance, or
you learn nothing about the gate.

Two gates, different questions: `check:back` asks whether a back handler is
SAFE (`safeGoBack`, never a bare `router.back()`); this one asks whether one
EXISTS.

## Prose pages: hierarchy comes from the sections, not from icons (2026-08-15)

`app/guide/[categoryId].tsx` and `app/help/*` are the app's two long-prose
screens, and they were built the same way twice, so the lessons are shared.

**Six identical boxes read as six equally important things.** The collecting
guide rendered every section in the same card, distinguished only by the icon
colour — including the one section whose entire job is to stop a beginner
losing money. That is the "three equal controls read as three equal decisions"
problem in prose form. Three levels, not one:

| level | treatment | what belongs there |
|---|---|---|
| reference | `colors.card` + hairline border | glossary, care, value drivers |
| pick | tone tint + 3pt left rule | the grail, the entry point |
| alert | tone tint + tone border | the one warning |

The tint is always `tone + '12'` and the border `tone + '40'` — **an alpha of
the tone, never the tone itself**, so every glyph and letter stays on a theme
colour and nothing can go invisible when the palette swaps.

**No decorative icon beside every heading.** The first pass put each section
glyph in a tinted disc. Reported as *"remove the very Claude design like icons
next to the section titles"* — and the objection is structural, not a matter of
taste: an icon on all six headings decorates them identically and so
distinguishes none of them, while the tint and the left rule already do that
job properly. The heading is the heading.

**Sentence case, not tracked-out caps.** `BACKGROUND` / `WORDS YOU WILL SEE` at
`sm` with `letterSpacing: 0.5` read as system labels. These pages exist to sound
like a person explaining something, so headings are `lg`, `bold`, sentence case,
`letterSpacing: 0.1`. Wide tracking exists to make caps legible; in sentence
case it just looks stretched.

**A hero, not a bare `<Text>` heading.** Both pages open with a tinted panel
carrying an eyebrow (*"Need a helping hand?"*), the title and the intro. The
guide's tint is the CATEGORY's own `CATEGORY_VISUAL.accentColor` at 14%, so a
Pokémon guide and a Warhammer guide do not look like the same page.

**Validate icon names against the glyph map, don't just cast.**
`CATEGORY_VISUAL` contained `'vinyl'` and `'logo-nintendo'`, neither of which is
an Ionicons glyph. A bad name renders an **empty box** rather than throwing, so
it stays invisible until somebody looks at that one category. Both are fixed
(`disc`, `game-controller`), and all 112 names are now verified:

```bash
node -e "const g=require('@expo/vector-icons/build/vendor/react-native-vector-icons/glyphmaps/Ionicons.json');
const s=require('fs').readFileSync('src/data/categories.ts','utf8');
const bad=[...s.matchAll(/iconName:\s*'([^']+)'/g)].map(m=>m[1]).filter(n=>!(n in g));
console.log(bad.length?bad:'all valid')"
```

## `flexWrap: 'wrap'` on an action row strands the third button (2026-08-15)

`app/offers.tsx` gained a third action on countered bids (Accept bid / Turn it
down / Delete) and the row wrapped, dropping Delete onto its own line,
right-aligned under the others. A button on its own line reads as a separate
decision rather than the third option in a set.

**Let the buttons shrink instead of letting the row wrap:** `flexWrap: 'nowrap'`
on the row, `flexShrink: 1` and tighter horizontal padding on the button,
`textAlign: 'center'` on the label. **Leave `minHeight` alone** — the row is
what shrinks, never the touch target.

## The screen title had no spec, so it drifted eight ways (2026-08-15)

Reported as *"all screens have different size title and alignment"*, and a sweep
of every route confirmed it: **8 sizes (14–28), 4 weights, 5 different top
paddings** across 41 screens with an in-body heading.

**The spec, taken from the help/guide pages:**

| property | value |
|---|---|
| fontSize | `text['2xl']` (24) |
| fontWeight | `fontWeight.extrabold` (`'800'`) |
| lineHeight | 30 |
| textAlign | left |
| gutter / top padding | 16 (the screen gutter, unchanged) |

Applied to the six screens whose heading is genuinely a page title:
`(tabs)/add`, `catalog-item/[key]`, `purchase/create-mandate`,
`sell/ebay-defaults`, `sets-to-complete`, `listing/[id]`.

**Three categories are deliberately NOT normalised, and the first sweep tried to
change all three — check before touching a style called `title`:**

1. **Card / list-row titles.** `archived.tsx` and `favorites.tsx` use
   `styles.title` at 14pt for a row title, and `offers.tsx` at `lg` with
   `flex: 1`. Bumping those to 24 wrecks the cell. Tells: `flex: 1` in the
   style, a `fontSize` under 18, or the `<Text>` sitting inside a `render*`
   function.
2. **Section headings inside a document.** `legal/*.tsx` use `styles.heading`
   **10–29 times** per file — it is an `<h2>`, not the page title.
3. **Deliberate heroes.** `(auth)/*`, `subscription.tsx` and `mfa-setup.tsx` sit
   at 28 on purpose; `chat/[threadId]` centres its title because it acts as a
   nav bar.

**Do not "fix" this with prettier.** There is no `.prettierrc` in this repo, so
`npx prettier --write` reformats whole files to ITS defaults (double quotes) —
one run produced **3,000 lines of churn across 7 files** for 11 lines of real
change. To separate a real edit from formatting noise afterwards: format the
`HEAD` copy with the same prettier and diff that against the working file.

## A bottom sheet must take only the BOTTOM safe-area inset (2026-08-15)

`SafeAreaView` with no `edges` prop applies **all four** insets. On a sheet
pinned to the bottom (`justifyContent: 'flex-end'`) that adds the 47–59pt
status-bar inset to the TOP of the sheet, pushing the body down inside a
`maxHeight: '90%'` box with `overflow: 'hidden'` — so the bottom of the content,
usually the primary button, is silently clipped. Reported as *"the listing change
price screen is half cut off"*.

```tsx
<SafeAreaView edges={['bottom']} style={[styles.container, { maxHeight }]}>
```

**Scrolling is opt-IN (`scrollable`), not the default.** The sheet clips, so tall
content needs a scroller — but most sheets already bring their own
(`SettleUpSheet`, `ShareToChatSheet`) or their own `FlatList`
(`app/create-event.tsx`), and nesting two vertical scrollers breaks the inner
one. Defaulting it to true fixes one sheet and regresses several; only
`listing/[id]`'s "Change price" opts in.

## A paywall CTA that routes to Settings sells nothing (2026-08-15)

`UpgradePrompt.tsx` — the banner on every Pro gate (set completion, analytics,
market movers, item detail) — called `router.push('/settings' as Href)`, as did
the "Upgrade to see" button in `MarketMoversSection.tsx`. **Hitting a gate could
not reach the paywall from anywhere.**

The `as Href` cast is what hid it: `/settings` is a real route, so TypeScript had
no complaint. Any cast to `Href` turns a routing question into a typing
formality — when you write one, the destination is unverified by definition.

Sweep for it by pairing intent with destination: every `router.push` in a file
mentioning upgrade/paywall/locked/requiredPlan should land on `/subscription`.

## Four stacked header blocks is what "messy" means (2026-08-15)

`app/(tabs)/wishlist.tsx` opened with **four full-width blocks before a single
watched item**: a title row, a full-width action row (Inbox pill + Add pill), a
bordered stats card with four icons and three dividers, and the Deal Agent
banner. Each was individually reasonable; stacked they spent the first screen on
chrome. Reported simply as *"visually very messy"*.

**Collapsed to one header block plus the banner:**

- Title, Inbox and Add share ONE row — `flex: 1` on the title pins the controls
  to the right edge.
- Inbox lost its text label and became an icon button. It was the only pill
  labelling an action its icon already states, and it competed visually with
  Add, which is the primary action.
- The stats card became a caption line — `4 items · 3 categories · €454 target`
  — at `sm`, directly under the title. These are reference numbers, not
  controls; a border and four icons asserted otherwise.
- The header row sat at `paddingHorizontal: 12` while `listContent` used 16, so
  the title hung 4pt left of every card beneath it. Both are 16 now.

**The general rule: count the full-width blocks above the fold.** More than two
before real content and the screen reads as chrome, however clean each block is
on its own.

## Never ship "coming soon" on a screen that can reach the App Store (2026-08-15)

`app/subscription.tsx` rendered *"Coming soon — we're finishing the Pro tier
setup"* whenever RevenueCat returned no offering. That is a pre-launch message
on a shipping screen: an Apple reviewer opening the paywall reads the product as
unfinished, and a real customer whose plans failed to load once is told the
feature does not exist rather than to retry.

Both underlying failures — no offering from StoreKit, or a thrown fetch — are
retryable, so they now share one honest state ("Plans couldn't load" + a **Try
again** button), with the specific cause going to `logger.error` instead of into
the copy. Restore Purchases renders outside that branch, so someone who has
already paid is never stranded.

**Plan feature lists are a spec, not marketing.** The Pro card omitted two real
entitlements (unlimited watchlist, unlimited deal alerts) and claimed "Priority
support", which nothing implements. Keep the lists in step with `FORCED_LIMITS`
/ `DEFAULT_LIMITS` in `src/hooks/useBillingLimits.ts` — this is the screen that
takes money, and a written promise to a paying user is a requirement.

### The title sweep missed two whole classes (2026-08-16)

The 2026-08-15 pass only found screens rendering their own `styles.title` text,
so it declared the job done while two obvious offenders were untouched — caught
immediately in use: *"marketplace is still aligned center as a title, search
page still doesnt have a title"*.

1. **`ScreenHeader.tsx` centred its title at 18pt**, and that ONE component is
   the header for **13 screens** (Market/`listings`, `offers`, `favorites`,
   `catalog-item`, `categories/[categoryId]`, `tax-reporting`, `sell/pick`,
   `category-browse`, `listing/[id]`, …). Now left, 24, extrabold — the same
   spec as an in-body title. The equal-width side boxes existed only to keep a
   CENTRED title centred, so `sideLeft` lost its `minWidth` (the title now sits
   beside the chevron rather than 76pt away) while `sideRight` kept it, which is
   what pins the gear to the screen edge when `InboxHeaderButton` renders null.
2. **`app/search.tsx` had no title at all** — the tab opened straight onto a
   search field. Title and back control now share a row, with the field
   full-width beneath at the 16 gutter.

**The lesson for the next sweep: a screen's title is not always a `Text` in that
screen's file.** Grep for the shared header components too, and check a tab
root's rendered output, not just its source.

## Two label languages in one form (2026-08-16)

`app/purchase/create-mandate.tsx` rendered its own labels for NAME, VALUE
AGAINST and MAX PRICE (11pt, uppercase, `letterSpacing: 0.5`, `colors.muted`)
while CATEGORY and MIN TRUST came from `SelectField` (12pt, semibold,
`colors.text`). Reading down the form the label style alternated on every other
field, which is what "the alignment is off" meant.

Worse: **`SelectField` carries `marginBottom` but no `marginTop`**, so its label
sat flush against the input above it while every hand-written label had
`marginTop: 16`. A select placed after a text input therefore collided with it.

Fix: one label spec for the screen (12 / semibold / `colors.text`), and each
`SelectField` wrapped in a 16pt top-margin view. **When a screen mixes a shared
field component with hand-rolled fields, the hand-rolled ones must copy the
component's label spec — not the other way round.**

## A list card is a reference row, not a call to action (2026-08-16)

The watchlist card carried a priority dot, title, a filled-circle remove X, a
category pill, target + edit, notes, an "Added <date>" line, and **two
half-width buttons**. Five rows of that is a wall of teal, and only two and a
half cards fit on screen.

- **Dropped "Added <date>."** Nobody acts on it; it cost a full line per card.
  (Its `formatDate` helper went with it — an unused helper left behind is how a
  dead path survives a cleanup.)
- **Actions became compact pills on one right-aligned row.** Same two actions,
  same touch targets, a third of the height.
- **The edit pencil went 12pt muted → 16pt accent.** At 12pt grey beside the
  target it read as decoration, not a control, which is why it got reported as
  "the edit button doesn't work".
- **The summary line was removed entirely** on request, and
  `WishlistStatsBar.tsx` deleted with it — it had exactly one caller.

Four cards now fit where two and a half did.

## `headerTitleAlign: 'left'` does NOTHING on iOS (2026-08-16)

Reported as "marketplace is still aligned center as a title". The fix for
`ScreenHeader` was real, but a second class of screen sets a **native** header
title via `<Stack.Screen options={{ headerTitle: … }} />`, and
`@react-navigation/native-stack` **ignores `headerTitleAlign` on iOS** — the
native bar always centres. Setting it is harmless and helps Android; it is not
the iOS fix.

**And it produced a false verification.** I screenshotted `/guide/comic_books`,
saw "Comic Books & Graphic Novels" starting hard against the chevron, and called
it fixed. It was still centred — the title was simply long enough to fill the
bar. The short one (`Help`) made that obvious immediately. **Verify alignment
with a SHORT string; a long one looks left-aligned no matter what.**

The real fix on iOS is to not set a native title at all where the screen already
renders its own heading. `guide/[categoryId]` and `help/*` open with a hero
carrying the page title, so the bar title was a duplicate as well as a
misalignment. Both now pass `headerTitle: ''` and keep the chevron and gear.

## The newest screens keep shipping without the nav bar (2026-08-16)

`QuickNavBar` is the bottom bar for screens OUTSIDE the `(tabs)` group. The
three most recently built screens — `help/index`, `help/[topicId]` and
`guide/[categoryId]` — all shipped without it, so a reader who arrived from
search had only a back chevron.

An enumeration of all 78 route files found 41 with it and 37 without. Most of
those 37 are correct: `(auth)/*` (no navigation before login), `(tabs)/*` (they
have the real tab bar), the camera screens, chat compose, `+not-found` and
`index`. The genuine omissions were the three new ones.

Two details worth keeping:

- **It reserves its own space.** `QuickNavBar` is a normal flex row with a top
  border, NOT `position: absolute` like `ExternalTabBar` — so adding it needs no
  inset and no `useTabBarInset()`. Render it as the sibling after the scroller
  inside a `flex: 1` container.
- **Cover every return branch.** The first pass added it to each screen's main
  render but not to its `if (!guide)` / not-found branch, so a bad deep link
  still stranded you. A screen with early returns needs the bar in all of them.

## An always-rendered card is an empty grey box when its field is null (2026-08-17)

`EventHeroSection` rendered the description card unconditionally. Most scraped
events have no description — Ticketmaster feeds give a title, a date and a venue
and nothing else — so the event screen showed a bordered card with nothing in
it, directly under the location. Reported by pointing at it in a screenshot.

A bordered card with no content does not read as "this field is empty". It reads
as **a component that failed to load**, which is worse than the information
being absent. Guard on the content, and guard with `.trim()` — a whitespace-only
string is the same nothing, and `{event.description && ...}` would still render
the card for `" "`.

Sweep-worthy: any `<View style={styles.someCard}>` whose only child is a single
`{optionalField}` has this bug waiting.

## Two stacked rows of pill buttons are one row (2026-08-17)

The event screen rendered `EventActionBar` (Open link / Share) and then
`EventRsvpSection` (Going / Interested) as siblings, each with its own row. Two
rows of identical pills, stacked — reported as wanting them "all aligned".

They were built weeks apart, and each was reasonable alone. The fix is
structural rather than cosmetic: **one component owns the row**, and the other
returns a FRAGMENT of buttons passed in as `leadingActions`. Two components each
drawing their own row can never align, because neither knows about the other's
padding.

Three things this turned up that are easy to get wrong:

1. **`flex: 1` on the primary button.** Fine on its own row, fatal in a shared
   one — it eats the whole line and pushes everything else onto a second row,
   which is the bug you were fixing. `flexShrink: 1` + `textAlign: 'center'`.
2. **The metrics have to be copied deliberately.** The share button was
   `paddingVertical: 12, borderRadius: 24`, the RSVP buttons `10` and `20`. In
   separate rows nobody noticed; side by side it reads as ragged.
3. **Render `leadingActions` in EVERY branch.** `EventRsvpSection` has a
   past-event branch that shows an "Attended" badge instead of the buttons.
   Putting the new prop only in the upcoming branch silently deletes Share from
   every past event — the "one branch got the fix" bug this repo keeps paying
   for.

Row is `flexWrap: 'nowrap'` per the rule above it: with four pills, wrapping
strands the last one on its own line.

## Two boards ranking the same idea should be the same object (2026-08-17)

`app/leaderboard.tsx` holds two boards — the XP board and the per-category one
added on 2026-08-16 — and they looked nothing alike. The category rows were bare
bordered strips: no card fill, no medal colours, no trophy on the top three, no
handle, no second stat, and **not tappable**, so the one board where you would
actually want to look someone up was the one you could not. The XP board had all
five. Reported as "match the analytics leaderboard UI".

Both now use `styles.card` / `rankCol` / `infoCol` / `valueCol`, the same medal
colours, the same stagger, and both push `/users/{id}`.

Two differences are deliberate and must survive:

- **The category board ranks by `r.rank` from the server, not by array index.**
  Ranks can TIE — two collectors with nine items are both #4 — and renumbering
  by position invents an ordering the data does not have. The XP board's
  `index + 1` is safe only because that endpoint returns a strict order.
- **`is_you` keeps its accent fill.** "Where am I" is the first question anyone
  asks of a board they might be on.

Also: `handle` is nullable on the category endpoint and derived on the XP one.
Rendering `@` with nothing after it looks like a truncation bug — branch on it.

## A profile that lists totals says nothing about the collector (2026-08-17)

The public profile showed stats and achievements, so two members with completely
different collections read almost identically — same badges, different numbers.
`UserCategoriesSection` now lists what they actually collect, most-held first,
with their rank in each category and a tap through to that board.

**The null rank is the whole design.** `rank === null` means not ranked, which
is NOT last place, and it is the COMMON case because discovery is off by
default. It renders as "Not ranked" — never as a number, never as the row
position, never as "#— of —". Falling back to any of those states a placement
the server deliberately refused to compute.

Same for money: a hidden value arrives as `0` with `value_visible: false`. "EUR
0.00" is a claim about a collection and "value hidden" is a statement about a
setting; they are different sentences and the component picks between them.

The "turn on Allow discovery to be ranked" hint renders **only on your own
profile**. On someone else's it would be reporting their privacy settings to a
stranger.

## Three rules I broke in one screen, all already written here (2026-08-19)

A pass over `app/offers.tsx` added five new text styles, and the
post-completion audit caught the same three rules this document already states.
Worth recording because none of them were subtle — they were skipped by writing
new styles instead of reading the neighbours:

1. **Five of five new styles were `xs`.** The type-scale section above bans 10pt
   for anything a user reads, and names THIS SCREEN as where it was reported
   ("that screen is very small letters"). The existing pills on the same row
   are `sm`. Copying the neighbouring style would have got it right for free.
2. **A sentence was dropped into a `flexWrap: 'nowrap'` action row.** That row
   is nowrap deliberately (2026-08-15, above) so a third button shrinks rather
   than wrapping onto its own line — which means a paragraph in it squeezes the
   touch targets instead of wrapping. Explanatory copy goes AFTER the row.
   I then wrote the comment saying so and left the code inside the row anyway;
   the fix is not done until the code moves.
3. **A count on a tab screen used `useEffect`, not `useFocusEffect`.**
   `app/listings.tsx` had already solved this for the same number, with the
   reason in a comment: a tab stays mounted, so a mount-only count keeps
   advertising work the user has already done.

**The pattern: a new component beside an old one should be written by reading
the old one, not by writing from scratch and checking afterwards.** All three
were caught by the audit — but the audit is a net, and the neighbouring file
was a spec.

## A tab's LABEL and its ROUTE are different things (2026-08-19)

The fifth tab is labelled **Explore** and its route is still `search`
(`app/(tabs)/search.tsx`, `/search`, every deep link). That split is
deliberate: the screen is a search box whose idle state is browse-by-category,
so "Explore" describes both halves, while renaming the route would break deep
links, `check:params` handoffs and the one-line re-export that keeps
`/search` and the tab rendering the SAME component.

The rule the P2P spec §11 states — *the word on the bar must describe the
screen it produces* — is about the LABEL. It is not a reason to rename files.

**One label, three components.** `ExternalTabBar`, `QuickNavBar` and
`app/(tabs)/_layout.tsx` all render this bar, and a screen shows whichever it
mounts. A rename that touches one of them leaves the app calling the same tab
two different names depending on where you are:

| component | where it renders | label source |
|---|---|---|
| `ExternalTabBar` | `(tabs)` screens, at RootStack level | `t("nav.explore")` |
| `app/(tabs)/_layout.tsx` | the navigator's own `Tabs.Screen` | `t("nav.explore")` |
| `QuickNavBar` | the 38 screens OUTSIDE `(tabs)` | **plain English literal** |

`QuickNavBar`'s `TABS` array is deliberately untranslated (the whole array is,
rather than half of it), so it needs the same edit by hand — it was the one
that still said "Search".

**And the label leaks into prose.** `src/data/appHelp.ts` told users to "Open
the Search tab". Copy naming a tab is a fourth place to change, and no gate
looks for it: `i18n:parity` compares keys across locale files and
`check:reachable` walks routes, so neither can see an English sentence naming a
control. Grep the label string, not just the components.
