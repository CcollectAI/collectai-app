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

### The wordmark went on the native splash (2026-08-22)

Asked for "Sparrow Collect written out on the splash screen in the same font as
the rest of the app". `src/components/SplashScreen.tsx` — the ANIMATED overlay —
already did that, in `fonts.black`. The native splash did not, and it is the
first frame anyone sees.

expo-splash-screen can only show an IMAGE; there is no text option. So the
wordmark is baked into `assets/splash.png`, generated by
`scripts/make_splash.py` from three measured inputs: the real `icon.png`, its
sampled background, and `node_modules/@expo-google-fonts/roboto/900Black` — the
exact file `fonts.black` resolves to, so the splash and in-app wordmarks are the
same typeface rather than merely similar. It is a SCRIPT because an asset nobody
can regenerate is one nobody can adjust.

Two numbers worth carrying:

- `assets/splash.png` was previously **byte-identical to `icon.png`** and
  referenced by nothing — the config pointed at `icon.png` directly.
- The bird art is now **55% of the canvas** rather than 59%, because the
  wordmark sits below it. At `imageWidth: 300` that renders the art at ~164pt
  instead of ~180pt. `imageWidth` was left at 300 rather than raised to keep the
  old size: 330 would exceed a 320pt-wide iPhone SE, and this section already
  records 300 as what fits.

⚠️ **The size jump this section warns about already existed and is not fixed
here.** The native splash renders the art at ~164pt; the animated overlay then
renders `icon.png` in a 124pt box, so its art is ~73pt. They have never matched.
Worth closing, but it is a separate change from adding the wordmark.


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

## What actually catches a UI defect you just wrote (2026-08-22)

Recorded after ~15 self-introduced defects over two days. None of them were
found by re-reading the new JSX; they were found in the SEAM:

- **the base style** — an outline button whose `borderWidth` was never set,
  because as a filled block it never needed one; a "3pt stripe" that inherited
  `borderWidth: 1` and rendered as a tint
- **the neighbouring row** — a gap figure in the row's own currency beside a
  target formatted in the VIEWER's, because `formatPrice` formats and never
  converts
- **the enclosing block** — a row wrapped in `isDraft || isEditing` that was
  already branching on `isDraft || isEditing`, killing twenty lines
- **the gate above it** — a card opened by a condition its own children then
  declined to satisfy, rendering bordered and empty

Practical checks, cheap enough to run every time:

```bash
# styles defined but never used (line comments are LINE-scoped — `//.*` with
# re.S eats the rest of the file and reports everything as dead)
# icon names, which render an EMPTY BOX rather than throwing when wrong
node -e "const g=require('@expo/vector-icons/build/vendor/react-native-vector-icons/glyphmaps/Ionicons.json');
  ['trending-up','flash'].forEach(n=>!(n in g)&&console.log('INVALID',n))"
# banned type sizes
grep -rnE "fontSize: text(Token)?\.xs|fontSize: (9|10|11)\b" app src
# roles that are FATAL on Android, and SafeAreaView imports
node scripts/preflight_android.mjs
```

⚠️ **A grep written for an audit is itself unaudited.** A search for
`accessibilityRole="tabbar"` returned two hits that were both comments warning
against it — the same false positive `check:unrendered` had to be fixed for. A
comment is neither a reference nor a declaration, including in your own checks.

## A native header title is invisible to both i18n gates (2026-08-22)

The font sweep found that 26 native `headerTitle` strings were hardcoded
English. What matters is WHY no gate saw it:

- `check-i18n-parity` compares KEYS across locale files, so it can only report a
  string that already HAS a key. These have none.
- `check-i18n-strings` finds user-visible strings in JSX never wrapped in `t()`.
  A value inside `<Stack.Screen options={{ … }}` is not JSX text.

So a Dutch device showed an English bar title over a fully translated screen and
every gate stayed green. **The failure is a missing KEY, not a missing
translation** — the blind spot beside
`learning_i18n_missing_key_renders_english`.

`npm run check:native-header-titles` covers `headerTitle` AND `headerBackTitle`
(an English "Items" under a translated title is the same bug). Proven red first:
**26 across 20 screens**, two more than a hand grep found. `''` still passes —
it is the documented iOS fix for a screen that renders its own in-body heading.

**The keys are their own, not reuses.** Ten of these strings already existed —
`settings.condition_guide`, `settings.my_suggestions`, `home.analytics` — but
those are SETTINGS ROW labels and a nav item. "A tab's label and its title are a
third thing"; reusing them couples two questions that can diverge. Each
`screen_titles.*` key was instead SEEDED with the existing key's value per
locale, so the wording cannot drift while the identities stay separate — the
resolution `search.title` got when it took `nav.explore`'s value verbatim.

⚠️ **Not yet wired into `verify:prebuild`, because it is still red.** The 26
call sites need `useTranslation()` in 17 files whose component shapes differ
(arrow components, function declarations, nested components), and hook placement
is what produced a `useCallback` spliced into a `useEffect` body the same day. A
red gate that is not wired documents the debt honestly; wiring it before the
debt is paid would just break the build.

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

### …and shrinking is the right rule for THREE buttons, not four (2026-08-19)

The rule above (`nowrap` + `flexShrink: 1`) held for three. `app/offers.tsx`
grew a fourth on a live trade — Mark sent · Add tracking · Book shipping ·
Delete — and the last button squeezed until the WORD broke, rendering as
**"Del ete"**. Not the row wrapping: the LABEL wrapping inside a button that had
run out of width.

**The fix is fewer buttons, not a wrapping row.** Two of the four were steps of
a flow that now has its own screen, so they moved there. A row of four actions
on a list card is a sign the card is doing a screen's job.

Seen on the simulator against seeded data — invisible to tsc, to every gate,
and to reading the code, because the width only runs out at a real font on a
real device.

**Removing a button can strand its sheet.** The same edit left `SettleUpSheet`
mounted on the list with nothing able to open it: `setSettleFor` survived only
inside its own `onClose`. When you delete the last opener of a modal, grep the
setter — if its only remaining call is the close handler, the whole thing is
dead.

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

### …and the title sweep never checked the FONT (2026-08-21)

Both earlier passes normalised **size, weight and alignment** and neither looked
at `fontFamily`. Asked "is the title in the same font on every page?", the
answer was **no**, and the split is invisible on the platform most of the work
happens on.

There are two title-rendering paths:

| path | screens | iOS | Android |
|---|---|---|---|
| RN `<Text>` — in-body titles + `ScreenHeader` | ~15 | **Roboto** | Roboto |
| native-stack `headerTitle` string | **26** | **SF Pro** | Roboto |

`app/_layout.tsx` monkey-patches `Text.render` to inject
`fontFamily: "Roboto_400Regular"` into every RN `<Text>`. A native-stack
`headerTitle` is drawn by **UIKit, not by an RN `<Text>`**, so the patch cannot
reach it — the same fact the `headerTitleAlign` comment in that file already
records. And there was **no `headerTitleStyle` anywhere in the repo**: zero hits
across `app/` and `src/`.

So 26 screens showed a San Francisco title above a Roboto body on iOS. On
Android the system font *is* Roboto, so it matched by accident — which is why a
sweep that fixed everything else about the title never saw it.

Fixed globally in one place rather than 26:

```tsx
// app/_layout.tsx, Stack screenOptions
headerTitleStyle: { fontFamily: fonts.bold },
```

⚠️ **Check it on a device.** Setting `fontFamily` on iOS changes how
`fontWeight` resolves — the family carries the weight, so a numeric
`fontWeight` alongside it can be ignored or double-applied.

**The related gap, NOT fixed here:** of those 26 native titles, **25 are
hardcoded English** — `"Archived"`, `"Scan Barcode"`, `"Analytics"` — never
passed through `t()`. `check:i18n-parity` cannot see them, because the failure
is not a missing translation but a missing KEY. That is the blind spot beside
`learning_i18n_missing_key_renders_english`, and it needs a gate of its own
before it is worth translating 25 strings into 7 locales.

## A "find people" button that opens the marketplace (2026-08-21)

Reported as *"find collectors links to the marketplace, which is not correct —
it should link to a search bar"*, and it was right twice:

- `app/inbox.tsx` — the "No messages yet" empty state, **"Find collectors"** →
  `router.push('/marketplace')`
- `src/components/category/FriendsFollowSection.tsx` — **"Find friends"** →
  `router.push('/(tabs)/marketplace' as Href)`, under a comment asserting *"the
  collector search lives on the marketplace tab"*

That comment was false. The marketplace tab is `<MemberMarketplace asTab />` —
`app/listings.tsx`, a **listings feed**. It has no person search of any kind, so
neither button could do what its label said. Both now push `/search`
(`app/search.tsx`), the unified search over items, catalogue, **collectors**,
events and categories.

**This is the 2026-08-10 bug in a second place.** That one was the Search TAB
redirecting to the marketplace; it was fixed on 08-11 by making the tab real.
These two survived because the fix looked at the tab and never asked *who else
pushes to the marketplace expecting a search*. The sweep that finds it is the
one this playbook already prescribes for the paywall CTA: **pair intent with
destination** — every push in a file whose copy says find/collector/friend
should land on a search, not a feed.

Two details worth keeping:

- Push **`/search`, never `/(tabs)/search`**. `check:params` resolves a push
  target to its route FILE, and the tab wrapper has no `useLocalSearchParams`,
  so pushing there reports "that route reads: (none)" and the `?q=` contract
  stops being checkable.
- **No `type=users` param was added.** `app/search.tsx` reads only `q`, and a
  param the destination never reads is silently dropped
  (`learning_route_params_are_an_unchecked_contract`). "Find collectors"
  therefore lands on a general search rather than a filtered one — the correct
  destination, not yet the ideal one.

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

### …and the card still could not answer its own question (2026-08-21)

The 08-16 pass made the watchlist card SHORTER. It did not make it say more,
and a visual sweep a week later found the gap: **a watchlist card showed your
target and never the current price**, so the one question the screen exists to
answer — *how close am I?* — had no answer on it.

The data was half-built across three layers, which is why nobody saw it:

| layer | state |
|---|---|
| `watchlist_items` | `last_market_price`, `price_trend`, `market_hit_count`, `image_url`, `predicted_value` all exist |
| provider `.select()` | **omitted every one of them** |
| `WatchlistItem` type | `lastMarketPrice` / `priceTrend` declared, referenced NOWHERE |

Three changes:

- **The gap line.** `Now €62 · €12 over target`, with a trend arrow. Measured
  on prod first: 5 of 20 rows carry a price, so the ABSENT case is the common
  one and gets a sentence, never a `0` — an unpriced item is not a worthless
  one, and this list feeds the paid alert. That sentence renders only when a
  target is set: otherwise it would be a line on 15 of 20 cards saying nothing
  actionable, and the card already prompts "Set target price".
- **The priority dot became a left edge STRIPE.** An 8pt colour-only dot
  encoded the field at a size you had to look for. A 3pt rule reads scrolling,
  and it is what `app/offers.tsx` already does for the buying/selling role.
  `paddingLeft` drops 14 → 12 so the text gutter is unchanged.
- **"I Got It!" stopped being a filled accent block.** Four cards on screen
  meant four teal buttons down the right edge, and that PERMANENT button was
  louder than the conditional "Target met" row above it — the only urgent thing
  on the card. Accent is now reserved for that row.

**Four defects the post-completion audit caught in this very change**, all of
them mine:

1. **An outline button with no `borderWidth`.** `gotItBtn` had none — it never
   needed one as a filled block — so passing `borderColor` alone would have
   shipped a button with no visible edge.
2. **A 1pt "stripe" is a tint.** `itemCard` has `borderWidth: 1`, so
   `borderLeftColor` alone gave a 1pt edge nobody would notice — the dot's
   problem in a new shape. It needs an explicit `borderLeftWidth: 3`.
3. **`borderColor` is a four-edge shorthand** and the `highlighted` style set
   it, erasing the stripe on exactly the card an alert had just pointed at.
   Re-asserted in the same object — the trap this playbook already records for
   the offers role stripe.
4. **Two prices on one card in two currencies.** `formatPrice` FORMATS and
   never converts, so the existing `Target:` line rendered a stored EUR value
   labelled with the VIEWER's currency. Pre-existing, and invisible until a
   market price and a gap were rendered beside it in the row's real currency.
   Both now use `item.currency`, matching the member-listing row, which had the
   comment explaining this all along.

**The generalisable bit: "improve the UI" is not always a styling job.** Every
style on this card already followed the playbook. What was wrong is that the
screen had three columns of relevant data in the database and selected none of
them — so the sweep worth doing was a `.select()`, not a `StyleSheet`.

**Still open:** `image_url` is on the table, mapped by the provider on create,
and **0 of 20 rows are populated**, so a thumbnail would give every card a
placeholder — "a bordered card with no content reads as a component that failed
to load". It needs a writer before it needs a renderer.

### Decluttering means making the loud things RARE (2026-08-21)

Asked "does it need decluttering?" straight after the sweep above, and the
strongest case was against something that sweep had just added. Counted against
the 20 live rows rather than argued:

| element | on how many cards | verdict |
|---|---|---|
| priority stripe | 20/20 — **13 of them the untouched default** | decoration |
| category badge | 20/20, tinted accent chip | competing with the one urgent accent |
| notes | **2/20** | not clutter; left alone |
| touch targets | **5 per card**, body opens nothing | real, but each does something distinct |

**A signal identical on two thirds of the list is not a signal.** `medium` is
the default priority and 13 of 20 rows still carry it, so striping every card
marked "this is a card", not "you flagged this". The stripe is now applied only
to a priority the member actually chose; an unflagged card keeps the uniform
1pt border and 14pt padding, so only a decision costs ink. That is the DOT's
problem one layer up — the fix for a weak signal is not to make it bigger.

**The category badge came off the CARD and stayed in the SHEETS.** It was
reference information wearing the app's most emphatic colour on every row,
beside a "Target met" row that is supposed to be the only accent thing there.
As plain muted text it says the same and stops competing.

⚠️ **And the deletion of its style was caught by `tsc`, not by review.**
`categoryBadge` had two more callers — the acquire sheet and the edit-target
sheet — where a chip is correct: one item in focus, not repeated, nothing to
compete with. The argument for removing it ("on 20 of 20 cards") was
LIST-specific and did not transfer. When a shared style is dropped because of
how it reads in one context, check the other contexts before deleting it; the
type error was the only thing standing between that and a broken modal.

**What was NOT decluttered, and why the measurement decided it:**

- **Notes** render on 2 of 20 rows. Removing it saves nothing and deletes the
  member's own words.
- **A tappable card body** was rejected: only **7 of 20** rows carry an
  `item_id`, so it would be a dead tap on 65% of the list — the
  `as Href`-hides-a-wrong-destination shape, arrived at from the data instead.

## The item screen: the money had the least emphasis on it (2026-08-22)

Reported as cluttered, too much grey space, colours pulling attention, and a
hierarchy that does not follow monetary value. All four were right, and none of
them was fixed by spacing.

**The €6 was row 4 of a spec table** — the only MONETARY fact on the screen,
at the same weight as "Condition" — while the card asking *"Price seems off?"*
rendered no number at all. `ItemPriceSection` draws its price card only when
`priceEstimate` is truthy, and for a catalogue-sourced value it is null, so
that card collapsed to a bare data-collection prompt about a figure four rows
above it in a DIFFERENT card.

The value and its provenance chip now lead the valuation card. One card answers
both halves of *"what is it worth, and is that right?"*. The chip moved rather
than being copied — its own docstring is the reason: *"one component, so the
item card and the detail screen cannot end up describing the same number two
ways."* In EDIT mode the value stays in the details card, because there it is a
form field among form fields.

⚠️ Moving it meant widening the card's gate with `!isUnpriced(editableValue)`.
A card that leads with a figure must render whenever there IS one, and the old
gate only fired on an ML band — which this item does not have.

**Sell was buried and Share had the slot.** The action row is Edit / Share /
List for Sale, and the third is gated by `SELLING_ENABLED = false` — it lists to
EXTERNAL marketplaces. The LIVE P2P sell sat near the bottom, below the price
feedback: a data-collection ask outranking the thing that makes money. Now
**Edit · Sell**, and Share is a 30×30 icon overlaid top-right on the gallery
with the marketplace tile's exact metrics.

**Share could not go in the nav header**, which is the obvious place: that
cluster is bell/bubble/gear, and a fourth icon stops reading as a cluster and
starts reading as a toolbar — the reason the avatar was removed from it.

### 48 accent usages is why nothing read as primary

Counted across the screen and its components. Teal had become the default
decoration rather than a signal, which is "three equal controls read as three
equal decisions" in colour form. One tier per job:

| tier | treatment | what gets it |
|---|---|---|
| primary | filled accent | **Sell** — one per screen |
| secondary | outline / accent text | Edit, "I sold it for…", catalogue fill |
| tertiary | muted | Share, Refresh, the feedback heading |

**The feedback heading was a `text`-coloured 14/600 header** — the title of the
card — which is how a request for help ended up outranking the figure it is
about. Muted, and it now follows the number instead of introducing it.

### Two bugs found while doing it

**A destructuring default cannot express "or blank".** `condition = "Not set"`
fires only on `undefined`, so a route param arriving as `""` kept the empty
string and rendered a label with NOTHING beside it — while Collection one row
above looked fine, because its picker writes the literal "Not set". The backfill
compared against `"Not set"` too, so `""` never recovered. Normalised once, for
all four params.

**`feedbackBtnTextWhite` was still `#FFFFFF`, with the comment "Button text on
brand background"** — verbatim the defect this playbook records as FIXED in
this exact file on 2026-08-19. One instance in the file was fixed (the
sale-price submit, now `accentText`); this second one was missed.
`check:brand-colors` passes on it because the fill and the colour live in
different objects, outside its ±window — the same false negative that section
already describes the gate having, in the same file. **When a gate is widened
after a miss, re-run it against every instance in the file it missed, not just
the one you fixed.**

### A gate must admit exactly what the body will draw (2026-08-22)

The audit pass after the sweep above found the sweep's own worst bug.

Widening the valuation card's gate with `!isUnpriced(editableValue)` looked
right — the card leads with the figure, so it must open whenever there is one.
But the LEAD renders on `!isDraft && !isEditing`, and the feedback below it on
`!isDraft && id`. So a **draft with a value and no ML band** satisfied the gate,
drew no lead, no feedback, and nothing from `ItemPriceSection` — **a bordered
card, completely empty**. That is the 2026-08-17 "always-rendered card is an
empty grey box" bug, arrived at from the opposite direction: not a card that
forgot to guard its content, but a guard that admitted content the body then
declined to draw.

The gate term now matches the lead's own condition exactly —
`(!isDraft && !isEditing && !isUnpriced(editableValue))`. **When you widen a
gate for a new child, copy that child's condition rather than paraphrasing it.**

### An unreachable branch hides inside a nested identical ternary

Making the value row edit-only was done by wrapping it in
`{isDraft || isEditing ? … : null}` — but the row ALREADY branched on
`isDraft || isEditing` internally. The inner `else`, twenty lines of read-mode
display, became unreachable and `tsc` said nothing: both branches type-check,
and dead JSX is legal. It surfaced only by counting the guards in the block.

Removing it orphaned `valueHighlight`, which the corrected dead-style pass then
found. **After wrapping an existing block in a condition, grep that block for
the same condition** — if it is already there, one of the branches just died.

### And two in my own diff

1. **A `useCallback` spliced into the body of a `useEffect`.** The insertion
   anchor matched inside an effect, so a hook ended up inside a callback — a
   rules-of-hooks violation `tsc` cannot see. It surfaced only as "cannot find
   name" at the JSX, several steps later.
2. **A dead-style detector that reported everything as dead.** `//.*` compiled
   with `re.S` makes `.` match newlines, so stripping line comments ate the rest
   of each file. It "found" 13 dead styles in a file with one. A checker written
   in a hurry is a checker that lies — the same lesson as the `check:unrendered`
   gate being wrong in both directions.

## Two containers, one `gap` — the rows drift apart (2026-08-23)

Reported from a screenshot: *"the collection category condition has different
spacing than the list rarity brand set code"*. Both groups are label/value rows
in the SAME card, and they were 16pt and 6pt apart respectively.

Neither style was wrong. The rows have different PARENTS:

| rows | parent | spacing |
|---|---|---|
| Category / Collection / Condition | the card in `ItemDetailsCard` — `gap: 10` | + `row`'s `marginTop: 6` = **16** |
| Rarity / Brand / Set Code | `ItemAttributesSection`'s own `<View>` — no gap | `attributeRow`'s `marginTop: 6` = **6** |

`ItemAttributesSection`'s styles carry a comment saying they *deliberately COPY*
`ItemDetailsCard`'s `row`/`label`/`value` — and they do, exactly. Copying the
CHILD metrics is not enough when the spacing lives on the PARENT. A `gap` is
invisible from inside the child, so a component extracted out of a card inherits
its type scale and silently loses its rhythm.

The section now restates `gap: 10` so both groups land on 16, and the hairline
that separated them is gone: they are one continuous list of label/value rows,
and a rule between them asserted a distinction the data does not have.

**Generalisable: when you extract rows into a child component, check the
parent's `gap`/`rowGap`, not just the row styles.** The tell is a group that
looks tighter than its neighbour while every declared metric matches.

### A brand that only restates the category is not a fact

Same screenshot: *"is brand not the same as category?"* — Category read
**Disney Lorcana** and, two rows below, Brand read **Disney Lorcana**.
`formatCategoryName('lorcana')` IS the literal string `'Disney Lorcana'`.

That is the "a grouped list should not repeat its group key in every member"
rule from the collection row, one card down: the row restated a fact the screen
had already stated, in the same words.

**Measured on prod before writing the rule**, per
`learning_keyword_filters_need_per_category_false_positive_audit`:

| category | brand | verdict |
|---|---|---|
| lorcana | Disney Lorcana | restates |
| yugioh | Yu-Gi-Oh | restates |
| mtg | Magic: The Gathering | restates |
| whiskey | **Bunnahabhain** | a real brand — kept |

4 of 5 suppressed, 1 kept, and the suppression is **read-mode only**: hiding a
field in edit mode is how a wrong value becomes impossible to correct, the same
reason `editableEntries` adds the category's empty fields back.

### The value leads in accent now

The 2026-08-22 pass moved the figure to the top of the valuation card and left
it in `colors.text`. It is the one monetary fact on the screen, and the accent
BUDGET to spend on it exists precisely because that same pass cut 48 teal usages
down to one tier per job. Accent as TEXT on a card is the "secondary" tier that
table already sanctions — this is not an accent FILL, so `accentText` does not
enter into it.

### Three defects the audit caught in this very change

All three are entries this playbook already contains, re-earned:

1. **Stripping diacritics is not folding them.** `norm()` was
   `.toLowerCase().replace(/[^a-z0-9]/g, '')`, which turns `'Pokémon'` into
   `pokmon` while a stored brand of `'Pokemon'` becomes `pokemon` — so the app's
   LARGEST category could never match and would have kept the duplicate row the
   change exists to remove. Now folds NFD first, and the guard around
   `normalize` keeps the failure pointing the safe way: a redundant row is
   SHOWN rather than a real brand hidden. Found by asking which category name
   would break the comparison, not by re-reading it.
2. **The retry button borrowed a list-row style.** `buyRow` carries only
   `borderBottomWidth: hairline` — reusing it for a button would have rendered a
   control with no visible edge. Verbatim the `gotItBtn` trap from the watchlist
   card ("What actually catches a UI defect you just wrote"), which is filed
   under *the base style* for exactly this reason.
3. **A comment still promised the hairline it had just removed.** The style
   block opened *"a hairline above them and nothing else"* over a style with no
   border. Comments EXPIRE — and a stale one is worse here than none, because
   the next reader treats it as the spec.

## The money was in the middle (2026-08-23)

Asked for as *"assess the full card rather than in isolation for a hierarchy of
user needs"* — after three separate rounds of fixing individual rows had left
the ORDER untouched. That is the lesson before any of the specifics: **a
hierarchy complaint cannot be answered one block at a time.** Each fix was
locally right and the screen still said the wrong thing first.

The item screen used to read: gallery → actions → **the whole spec table**
(category, collection, grade, rarity, brand, set code, set) → the comp prompt →
**the value** → notes → build/progress → where-to-buy → Pro.

So between the item's name and what it is worth sat reference data **the owner
already knows, because they own it** — and the one monetary fact on the screen
arrived after a scroll.

### The order now, and the need each block serves

| need | blocks |
|---|---|
| identify | gallery, **name** |
| act | Edit · List · **Sell** |
| **value** | the figure + provenance chip, comps/confidence, **"Price seems off?"** |
| reference | the spec table |
| my own record | notes, build, reading progress |
| — | where to buy |
| upsell | Pro / upgrade card |
| the ask | "Help improve our estimates" + "I sold it for…" |

**"Where to buy" deliberately did NOT move up**, though it is an action and the
first instinct was to promote it: *"these are items the user has in their
portfolio, so where to buy doesn't make sense that high."* An action is only
high-value if it is an action the member actually wants HERE — they already own
this one.

**The ask goes last.** Every other tenant of the valuation card answers "what is
it worth". "Help improve our estimates" asks — a favour, on behalf of the model,
and it was sitting directly under the figure.

**But the CORRECTION goes back up.** *"Shouldn't it be close to the price?"* —
yes. "Price seems off?" acts ON the number, so it belongs against the number;
what did not belong there was the heading and the "I sold it for…" button around
it. The block was split (`PriceCorrectionRow`), and because both halves still
write through one `feedbackMessage`, the hook now records a `feedbackSource` so
"Thanks for the feedback!" cannot appear under the control that did not cause
it.

### Two structural constraints that a reorder makes visible

1. **The name was the spec card's HEADER.** Moving the card below the money
   would have put the item's title under its price. The name had to be hoisted
   to the screen — read mode only, since in edit mode it is a form field among
   form fields, which is the exception the value row already makes.
2. **A gate must still admit exactly what its body draws.** Lifting the feedback
   block out of the valuation card removed one of the tenants its gate was
   widened for. Re-checked rather than assumed: the `(!isDraft && id)` term now
   corresponds to `ItemRefreshBar`, which has no early return, so the card
   cannot open on a term whose content declines to draw — the 2026-08-22 bug in
   reverse.

### Highlighting a card without re-inflating the accent count

Asked for as *"highlight and differentiate the card with the tiffany blue/teal
colour text, highlighted areas"*. The literal reading — teal on the label, the
chip, the comps — is precisely what "48 accent usages is why nothing read as
primary" records undoing, and the accent table reserves the FILLED tier for
Sell, one per screen.

**A tinted SURFACE is a different axis from accent text.** The value block gets
`accent + '14'` with an `accent + '33'` bottom edge, bleeding to the card's
inner edges (`marginHorizontal: -16` against the card's `padding: 16`) — the
same treatment `thinCatPrompt` already uses in this file. The figure keeps its
accent text, **nothing else gains any**, and the card is differentiated by the
region rather than by more teal. Alpha suffixes on `theme.accent` rather than a
new palette entry, so high-contrast dark still matches.

### Six defects the audit found in this very change

The post-completion pass over my own new code, and the count is the point — a
re-read of the diff found the stale comments; the rest needed the NEIGHBOURING
file or a question the code could not answer about itself.

1. **A comment that lied about the metrics beside it.** The hoisted title said
   *"same metrics ItemDetailsCard.name carried"* over `text.xl`/`bold`. The real
   style was `text['2xl']`/`extrabold`/`-0.3`. Every item title in the app would
   have shrunk while the comment asserted nothing had changed. Found by opening
   the style it claimed to copy instead of trusting the sentence.
2. **`styles.name` left behind, dead.** Worse than unused: it still reads as the
   definition of the item title.
3. and 4. **`marginBottom: 12`, then `marginTop: 10`, on direct children of a
   container with `gap: 10`.** Verbatim "Two containers, one `gap`" — written
   into this playbook that morning and re-earned twice the same afternoon.
5. **A failure state that consumed its own affordance.** The correction row
   swapped the button OUT for the message. Fine on success; on failure
   `onPriceDisagree` writes "Failed to submit feedback" through the same state,
   so the one path that needs a retry was the one path with no button. **A
   message renders beside a control, never instead of it.**
6. **Three comments that expired the moment the blocks moved** — an "END OF THE
   VALUATION CARD" marker now closing the spec table, an ask-block comment still
   describing "four lines below" and a "refresh bar above" it no longer sits
   near, and a "two places need this answer" note over a predicate down to one
   reader. Moving code invalidates the prose attached to it, and a stale comment
   is worse than none because the next reader treats it as the spec.

Also deleted: the `compChoicePending` gate on the ask, and the
`showSalePriceInput` escape hatch that existed only to soften it. Both were
correct when the two blocks were four rows apart; from opposite ends of the
screen there is no contradiction left to resolve. **Carrying a guard past the
reason for it is how a condition becomes folklore.**

## The same row, rendered by two different components (2026-08-23)

Reported from a screenshot of the item card in edit mode: *"the red issues in
brand/product name writing"*. Three separate defects, and each is a rule this
playbook already contains, broken one level out from where it was enforced.

### "Grade" twice, four rows apart

`ItemDetailsCard` renders a Condition/Grade row. `ItemAttributesSection`,
mounted inside that same card, rendered a second one. The list already enforced
*one label, one row* — but only against ITSELF, so a label the PARENT owned was
invisible to it. That is "One fact, three renderers" and
`learning_parent_gap_is_invisible_from_the_child` meeting: **a `gap` is
invisible from inside a child, and so is a LABEL.**

Measured before fixing: `attrs.grade` is present on **zero of 148 prod rows**.
The real grade lives in `items.condition` (`PSA 9`, `BGS 10`). The duplicate came
entirely from `editableEntries` synthesising the yugioh field list in edit mode
— so the row that looked like data was a placeholder for a key nothing writes.

The parent now passes `reservedLabels`, derived from the same
`isGradingEligible` expression that labels its own row rather than restated as a
literal. The semantics deliberately match the in-list rule: an **empty**
duplicate is dropped, a **filled** one survives as "Grade (captured)". Zero rows
hit the second branch today, and that is exactly why it needs to exist — the day
a captured grade appears, hiding it behind the card's "Not set" would be the
data-destroying half of the label dedupe all over again.

### One instance of a fix landed; the second was never looked at

Category read **`yugioh`**. `docs/TAXONOMY.md` says the promise is *"never shows
a raw slug"*, and the 2026-08-19 sweep resolved it on the detail screen — but
only in the READ branch. The EDIT branch printed `editableCategory` verbatim, so
the one moment a member is actively looking at that field was the one moment it
showed the database's word for it.

**And the obvious fix was wrong.** `editableCategory` holds a slug when seeded
from the row and a display NAME straight after a pick, because the picker is
built from `ALL_CATS.map(c => c.name)`. `formatCategoryName` is **not
idempotent** — it title-cases on separators, so wrapping it eagerly turns
`'Yu-Gi-Oh!'` into `'Yu Gi Oh!'`. `categoryDisplayName` discriminates on
`CATEGORY_NAME_TO_SLUG` membership, the same map `updateItem` normalises
through, so the read and the write agree by construction.
`__tests__/lib/categoryVocabulary.test.ts` pins the mangling too — if
`formatCategoryName` ever stops corrupting that input the wrapper is redundant
and should go.

### Bookkeeping keys are not facts about the collectible

`attrs` carries plumbing beside the real attributes, and the list rendered all
of it: *"Value Choice: mine"*, *"Intake Timestamp: 2026-07-26T21:32:30.736662+00:00"*,
*"Source: open_library"*.

`value_choice` is the one that would have grown: the market-comp prompt writes
it on **every** answer, so shipping that prompt without a blocklist means a
member's answer becomes a visible row on the item they answered it about.

All 22 keys present in prod were read before the line was drawn, per
`learning_keyword_filters_need_per_category_false_positive_audit` — **and two
that look like plumbing are not**: `item_type` (= "Merch") and `sealed` are real
facts and stay. Reading the total, or the key names, would have hidden both.

### What the audit of this change caught

The row-building was extracted to a pure `buildAttributeRows` for
`__tests__/components/attributeRows.test.ts`, because every rule above — plus
the brand suppression and label dedupe shipped the day before — lived inside a
component that could only be exercised by rendering it. **A rule with no way to
fail is a rule nobody can check.** The extraction immediately surfaced one:

- **The a11y label was recomputed from the key**, not taken from the row's
  resolved label. A row displaying "Grade (captured)" or "Set Name" announced
  plain "Grade" / "Set" — so the two rows the dedupe exists to tell apart were
  identical to the one user who cannot see them side by side.
- **The first version of the test passed immediately, which proves nothing.**
  It now carries the counter-case: with `reservedLabels` omitted, the duplicate
  "Grade" must come BACK. Without that, a `grade` row that was never synthesised
  in the first place would make the rule a no-op wearing a green tick.

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

## A component can be imported, wired, and never in the tree (2026-08-20)

`app/listings.tsx` imported `ShareToChatSheet`, held a `shareFor` state, drew a
paper-plane on every tile and computed a `sharePayload` memo — and the element
was **never rendered**. Tapping share set state that nothing read. Reported as
*"the send button on marketplace does not work"*.

`tsc` is happy (an unused binding is legal), `check:reachable` asks about ROUTE
edges and a component has none, and `check-dead-nav` asks whether a route file
exists. eslint *did* say `'ShareToChatSheet' is defined but never used` — as a
**warning**, in a repo with dozens, and `verify:prebuild` does not run lint.

**`npm run check:unrendered`** (`scripts/check-unrendered-components.mjs`) now
fails the build for a PascalCase import from a `components/` path that appears
nowhere else in the file. It found 7 more on its first run.

**The gate was wrong in BOTH directions before it was right**, and both are
worth remembering when writing any grep-shaped checker:

- a component named only in a `//` comment ("moved to CategorySpecificSection")
  counted as a USE, hiding a stale import;
- a deliberately commented-out `// import { SellTimingBadge } …`, kept beside
  the note explaining how to restore it, counted as an IMPORT and was reported
  as unrendered.

Strip comments first. A comment is neither a reference nor a declaration.

## One fact, three renderers (2026-08-20)

The item card showed **"Item Details" twice**, then the same attribute keys a
third time as **"Card Details"**. Reported as *"the item card is messy"*.

- `ItemAttributesSection` was mounted inside `ItemDetailsCard` **and** again
  standalone from the screen, each with its own fetch of the same row. The
  inner copy got `editableCategory` — a display NAME — where
  `getCategoryFields` expects a SLUG, so it silently lost the category's field
  order and labels.
- `CategorySpecificSection` re-rendered the same `attrs` as 71 hand-rolled rows
  across 25 blocks. Every one duplicated the list BY CONSTRUCTION: the list
  renders every key present; the blocks re-render a hand-picked subset.

**The rule: a kind of row has ONE renderer.** The attribute list owns key/value
rows; the category blocks keep only what the list cannot say — badges (Foil,
1st Edition, Vaulted) and controls (size, build progress, auth links).

**And the defect that cleanup introduced:** 19 blocks were left holding nothing
but *conditional* badges while the wrapper still carried `marginTop`,
`paddingTop` and `borderTopWidth`, so an item that was neither foil nor 1st
edition drew a **stray divider above 12pt of nothing**. Spacing that belongs to
a conditional child has to live ON that child, not on a wrapper that always
renders.

## Six full-width rows is a wall; two columns is a list (2026-08-20)

The profile's "Collects" block was reported as stacking three times, and each
fix made it less bad without making it right: six framed boxes → one framed
list → six unframed full-width rows. The last version was still ~90pt per
category, so a collector in six categories spent a screen on them and the CTA
row fell off the bottom.

**A category is a small fact** — a name, a count, a rank. Giving it the full
width of the phone is what forced the stack. Two columns halve the height with
nothing hidden and no horizontal scroll (which hides half the content behind a
gesture nobody is told about).

Three things that went with it:

1. **`flexGrow: 1` stretches the last tile across the full row on an ODD
   count.** The profile under test had six — the data that cannot show the bug.
   `flexGrow: 0` with `flexBasis: '48%'`.
2. **The chevron per tile went.** The whole tile is the target; twelve chevrons
   are decoration.
3. **A bordered container inside a bordered card is a box in a box.** The card
   already says where the group ends.

## A count in a section header describes TRADES, not rows (2026-08-20)

When `app/offers.tsx` started collapsing competing bids into one row, the
header `{section.title} · {section.data.length}` began counting **rendered
rows**: "Waiting on them · 2" over five bids, two of which had collapsed. The
display list now carries `total` from before the collapse. Any time you filter
what a list renders, check every number computed from that list —
`[[learning_aggregate_over_the_wrong_population]]` is one `.length` away.

## Your own empty state is a different sentence (2026-08-20)

Opening your own profile rendered **"Collector not found — this profile doesn't
exist or couldn't be loaded"**, because `user_public_profile_v1` ends in
`WHERE COALESCE(NULLIF(display_name,''), NULLIF(username,'')) IS NOT NULL` and
a member who never set a name has no row. Telling that member their profile
does not exist is telling them THEY do not exist — and the Settings row added
the same day walked them into it.

**Any screen reachable for both "you" and "someone else" needs the self branch
checked separately.** Here it says what is true and what fixes it: *"Your
public profile isn't set up yet — add a display name so other collectors can
find you"*, with a route to Settings.

## The top-right cluster is ONE component, on every screen (2026-08-20)

Reported as *"top right on portfolio there's a settings icon, notification icon
and profile icon — this should be the same for every screen across the nav bar,
this is not the case currently."* An audit of the five tabs found four
different clusters and two tabs with none at all:

| tab | bell | bubble | avatar | gear |
|---|---|---|---|---|
| Portfolio | ✓ | ✓ | ✓ | ✓ |
| Items / Add / Events | — | ✓ | ✓ | ✓ |
| Market / Explore | — | — | — | — |

Six files hand-rolled the same row. That is the same shape as the tab LABEL
problem (three components each rendering their own copy of the bar): **when N
files draw one thing, they drift, and no gate can see it.** There is now one
`HeaderActions` — bell · bubble · gear — rendered by all five tabs, by
`ScreenHeader` (15 screens) and by the root stack.

**Three icons, and identity is not one of them.** The bell, the bubble and the
gear are things you DO; a profile is something you ARE. Four icons stop reading
as a cluster and start reading as a toolbar. The avatar came off the header and
identity moved to the FIRST ROW of Settings — avatar, name, chevron — which is
the Apple-ID-row pattern, and is what Vinted does.

That is deliberately not the Uber-rider burial: Uber hides the rider rating
under Settings → Privacy → Privacy Center, and it needed CNBC and Washington
Post how-to articles to be findable. Row one of the first settings screen,
behind a gear that is now on every screen, is the opposite of a fourth-level
menu.

**Two defects this fixed that were not the reported one:**

1. **The notification bell existed on Portfolio ONLY.** Its unread count was
   fetched by `app/(tabs)/index.tsx`, so notifications were reachable from one
   screen out of five. A control whose state lives in a screen ends up living
   only on that screen.
2. **The cluster changed SHAPE with your inbox.** `InboxHeaderButton` hid
   itself under `COMMUNITY_GATED` unless you had unread mail — a DISCOVERY flag
   ("flip when ~50 public profiles exist") reused for a messaging control, the
   exact reuse `featureFlags.ts` already warns against for
   `GAMIFICATION_UI_ENABLED`. It now has its own `MESSAGING_ENABLED`. The old
   reuse is also what left the gear floating ~46pt from the screen edge (see
   the iOS 26 capsule section).

**Two defects the post-completion audit caught in this very change** — both
the same shape, a rewrite that deleted a fact while adding a label:

- **The account email vanished from Settings.** The identity row used to read
  *username / email*; the rewrite put "View public profile" on the second line.
  But the chevron already says the row goes somewhere — so the label restated
  the affordance and deleted the only place in the app that tells you WHICH
  account you are signed in as. The email is back and the label key is gone.
- **The badge cache outlived the session.** Module scope survives a sign-out,
  so the next account would have worn the previous one's unread count for up to
  a minute. The cache is now keyed by user id and cleared when it changes.

**And the cost this change ADDED, measured rather than assumed:** moving the
badge fetch into the cluster multiplied it by every screen that renders a
header — five tabs plus 15 `ScreenHeader` users. The count is now cached at
module scope with a 60s TTL, so it is one request a minute at worst instead of
one per screen opened. Any time you move a fetch from a screen into a shared
component, ask how many mounts you just created.

## A tab's label and its TITLE are a third thing (2026-08-20)

The 2026-08-19 entry above records that the fifth tab's LABEL ("Explore") and
its ROUTE (`search`) are deliberately different. What nobody checked was the
in-body **title**, which still read "Search" — so you tapped Explore and landed
on a page called Search, in all seven locales.

`search.title` now carries each locale's own `nav.explore` value verbatim
(Explore / Ontdek / Entdecken / Explorer / Explorar / さがす / 둘러보기) rather
than a fresh translation, so the bar and the page cannot drift apart by
wording. The KEY keeps its name — the route really is `search` — and it was
edited in place rather than duplicated, because it had exactly one consumer and
a second key would have left an orphan in seven files.

**The rule: a rename has three surfaces — label, route, title — and they answer
different questions.** Changing one and checking the other is how this survived
a documented pass about the very same tab.

## Two toggles that claim the same trigger (2026-08-26)

Renaming the Settings notification row *Deal alerts* → **Target Hit**, the new
hint read *"When a watched item drops to your target price"*. The row directly
above it already said *"When an item hits your target price or moves sharply"*.

Both true, both about "your target price", and between them a member cannot
tell which switch turns off which push. A settings list is a set of promises
about when the phone buzzes; two rows describing one trigger is the same defect
as two components rendering one fact, moved into copy.

**The discriminator is never in the label — it is in what the sender actually
sends.** The worker's own message settled it:

```
{title} — €{price} on {provider} ({n}% below your target of €{target})
```

Target Hit fires on a **marketplace listing appearing** below the target;
price alerts fire on a **valuation moving**. So the hint became *"When a
watched item is listed for sale below your target price"*.

Two rules worth keeping:

- **When you rewrite one row of a list, read the whole list.** The collision
  did not exist in either row alone; it existed between them, and re-reading
  the diff could not show it.
- **A label may be load-bearing.** `item.label` is also the row's
  `accessibilityLabel`, so a label written only to look right in the visual
  list is what a screen-reader user hears as the entire control.

Related: "One fact, three renderers" and "A tab's label and its TITLE are a
third thing" — the same rule at three scales.

## An analytics card that re-renders another screen (2026-08-26)

Reported as *"on the professional plan analytics we have to remove the holdings
because that is literally the same as the items overview screen"*, plus *"move
the cost basis summary into the performance card because this is the full
investment related analytics overview so it should be grouped together"*.

Both were right, and measuring them first changed what "move" meant.

### Holdings was the Items tab, minus the parts that make it useful

It drew name / category / current value per row — exactly what `ItemsListItem`
draws, without the thumbnail or the value-source chip, capped at 8 with no way
to reach the rest. Its one differentiator was a 24h percentage behind
`item.change1dPct !== undefined`, and **`/portfolio/items` has never returned
`change_1d_pct`** — the same fact that deleted the "Movers" card on 2026-08-14.

**The trap: it only looked distinct in development.** The six rows of the
dev-forced mock snapshot DO set `change1dPct`, so on a dev build the card
showed a column that production could never draw. Reading the code on a laptop
made it look like it answered a question the Items tab does not.

The screens answer different questions and the duplicate was on the wrong one:
*what do I own and what is each worth* is the Items tab; *how is the collection
doing* is Performance → Allocations → Category Performance.

### "Move it into Performance" required moving nothing

All three figures on the Cost Basis Summary card read the same three fields of
the same `pl` object the Performance card above already renders:

| Cost Basis Summary | = | already on Performance |
|---|---|---|
| Total Invested | `pl.startValue` | "from EUR X" on the delta line |
| Current Value | `pl.currentValue` | the hero figure |
| Unrealized P/L | `pl.deltaAbs` | the hero delta |

So the merge was a deletion. **When a "move this into that" turns out to be a
duplicate, say so rather than performing the move** — copying the tiles across
would have produced the same numbers twice inside one card.

Two of its behaviours were not carried over, because both were wrong rather
than merely duplicated:

1. **"Total Invested" was a mislabel.** `pl.startValue` is the portfolio's
   value at the start of the window, not what the member spent — the server
   falls back to the earliest prediction as cost basis when an item has no
   purchase price. `portfolioAnalytics.ts` states the rule this broke in so
   many words: summing that fallback into "what you paid" *"reports money the
   member never spent"*. The honest figure was already on the same screen as
   **"You paid"** (`valueSplit.purchaseTotal`, real purchase prices only). The
   screen was showing two different numbers that both claimed to be the cost of
   the collection.
2. **Its P/L was ungated.** Performance shows the delta only when
   `pl.hasBaseline`; this card printed `deltaAbs` unconditionally, so on an
   account with no earlier value to measure against it stated a gain the card
   directly above it deliberately refuses to state — the same contradiction
   that removed the percentage badge on 2026-08-20, one card down.

The progress bar went too. `width: min(100, (current/start) * 100)` pins at
100% for **any** gain, so it carried no information in exactly the case a
member wants to read it, and moved only while the collection was losing value.

### The housekeeping the deletion forced

- **14 style keys went dead** (`itemRow`…`itemPct`, `dcaRow`…`dcaBarFill`) and
  were removed with the JSX. A style left behind is worse than unused: it still
  reads as the definition of a row somebody might re-add.
- **Two comments expired the moment the cards did** — the screen's file header
  still advertised "Winners & losers section" and "Full items breakdown", and
  the `getCollectionTrends` note still pointed at "the Cost Basis Summary card
  below". Third session running that moving code invalidated the prose attached
  to it.
- `src/components/analytics/WinnersLosersSection.tsx` is now an **orphan file**,
  imported by nothing. `check:unrendered` passes because it only catches a
  component that is imported and not rendered; a file nobody imports at all is
  invisible to it. Left in place and recorded here rather than deleted blind.

Verified: `tsc --noEmit` exit 0, and `eslint app/analytics.tsx` reports the
**same 5 warnings as HEAD** — compared against a `git worktree` baseline, not a
stash. check:unrendered, check:item-values and check:brand-colors all PASS.

## The item card: a request that was already shipped, and a floor that was not (2026-08-26)

Three things asked for on the item card. Checking them first changed two of the
three answers.

### "Bring 'Price seems off?' to the top and integrate it into the price section"

First answer: **already done, 2026-08-23 16:28** (`af16271`) — it moved into the
valuation card then, and a device on build 152/153 predates that commit. That
part still holds, and it is worth keeping as a habit: **check the commit date
against the build before re-doing a layout change**, because the second
implementation is the one that rots.

**But "already in the card" was not the request.** Re-read as *"make this more
integrated"* it is a different and correct complaint: `PriceCorrectionRow`
rendered *after* `ItemPriceSection`, so on a priced item carrying bands, an
explanation, scarcity and comps, the control sat a screen below the figure it
corrects. Same card, nowhere near the number.

It now renders inside `styles.valuationHighlight` — the tinted block around the
figure — directly under the amount and its provenance chip. **"Against the
number" has to mean the number, not the section**, and the distance between
those two readings is however long `ItemPriceSection` happens to be for that
item.

Two gates travelled with it, and only one is cosmetic:

- **`id`** — the enclosing block is `!isDraft && !isEditing`; this control has
  always been `!isDraft && id && !isEditing`. Nesting it without re-stating
  `id` would have silently widened it. Effective condition unchanged.
- **`!isUnpriced`** — new, and it is what the move *exposed*. The block renders
  "Not priced yet" for an unpriced item, and "Price seems off?" directly
  beneath that asks a member to dispute a number the screen has just said does
  not exist. `onPriceDisagree` submits a disagreement about a valuation, so
  with no valuation there is nothing to disagree with. It was survivable while
  the control sat far below; adjacent, the two lines contradict each other.
  **Moving a control next to its subject makes it inherit that subject's
  states** — that is the general form.

And the parent changed, so both of the row's metrics had to. It was a direct
child of the card (`gap: 10`), which is why it carried an explicit "NO
`marginTop`" note; the tinted block has **no** gap, so the spacing it used to
inherit now has to be stated (`marginTop: 2`, against `valuationLead`'s
`marginBottom: 4`). `alignItems` went `flex-end` → `flex-start`: right-aligning
read fine across the full card width and reads as a detached control in the
corner once it sits under a left-aligned figure. **"Two containers, one gap"
from the other side — the rule is not "never set a margin", it is "know which
container owns the spacing", and the answer changes when a component moves.**

⚠️ `correctionText` was `fontSize: 12`, a raw literal — `textToken.sm` *is* 12.
The import it then needed did not exist, which would have thrown at runtime;
`tsc` caught it, a re-read of the diff had not.

### "Make the notes section smaller" — the box, not the label

`notesInput` opened at `minHeight: 100` and grew to `maxHeight: 220`: the
largest single element on a screen whose subject is the item's value, for a
field most items never fill. Now **64** (three lines at `lineHeight: 18` plus
padding) to **132** (six). `multiline` still grows and then scrolls internally,
so nothing is truncated.

**The label deliberately did not move.** `ItemNotesEditor.label` is `text.md`
and so is `ItemDetailsCard.label` — every other label on the screen. Shrinking
this one alone would have broken the row rhythm it currently matches, which is
"the parent gap is invisible from the child" applied to type instead of
spacing. *Smaller* meant the box.

⚠️ **And shrinking a section is not a licence to shrink its control.** The first
pass took the save button's `paddingVertical` from 10 to 8, which puts a
full-width primary action at ~30pt — under the 44pt minimum, and it was already
under at ~34. The padding went back to 10 *and* the button now states
`minHeight: 44` rather than letting its height fall out of the padding.

### The alignment sweep found a banned type size, not a misalignment

Run as the playbook's own checks rather than by eye, because "none of them were
found by re-reading the new JSX":

| check | result |
|---|---|
| invalid Ionicons names (they render an empty box, never throw) | clean |
| `accessibilityRole` values fatal on Android, `SafeAreaView` imports | clean on this screen |
| **banned type sizes** | **9 hits** |

Nine styles across `SellOnSparrowSection` (8) and `ItemPriceSection` (1) were
still on `textToken.xs` — 10pt, which rule 1 of the type scale bans outright for
anything a user reads. None qualified for the single exemption (a glyph-sized
label beside an icon): they are a consent sentence, a demand readout, a warning,
a link, two hints and a comp's SOURCE — the last being what tells a member
whether a number came from a sale or an asking price.

All moved to `sm` (12), **the floor, and not one step further**. The 2026-08-11
follow-up is the reason: bumping everything one step put 12 of 17 styles on
`md` and flattened the hierarchy. Raise the floor, leave the lead alone.
`hint` also went `lineHeight` 16 → 17, because 16 on 12pt is 1.33× and the rule
is ≥ 1.35×.

### One "violation" that was left alone

A line-height ratio check over the whole item card returned exactly one more
hit: `valuationAmount` at `fontSize: text['2xl']` (24) with `lineHeight: 30` =
**1.25×**. It stays. The ≥1.35× rule was written about a two-line string whose
lines collided; this is a single-line display figure where a tight leading is
the point. **A checker written during a sweep is itself unaudited** — the
playbook says so about greps, and it is just as true of a ratio test. Fixing
this one would have been a false positive with a commit message.

## A screenshot is a test case, and five of them were (2026-08-27)

Five TestFlight screenshots of build 154 produced eleven defects. Every one is
a rule this playbook already holds; what is worth recording is the *shape* of
each miss, because none of them was found by reading the JSX.

| reported as | what it actually was |
|---|---|
| "the LEGO details line seems odd and misplaced" | a bordered heading with an empty body — a gate admitting content its children declined to draw. Five categories, not one |
| "the market prices are way off" | `EUR 1,620,277,371` — a scraped page counter filed as a comp. The display path had **no bound of any kind** |
| "price seems off is duplicated" | not duplicated; the *ask* sat a screen below the *correction*, and from a member's seat that is one question asked twice |
| "the export report doesn't work" | an authenticated URL handed to `Linking.openURL`. The browser has no session, so a **paying** member got raw JSON |
| "profile additions don't persist" | they persisted. Nothing could ask the context to re-read them |

### The one that generalises: a paid surface has to justify itself

*"Why would a paid user want to see these? … all choices need to be
intentional."* The Market Prices section listed five suruga_ya products under a
Japanese vinyl record, three of them different records, beneath an EUR 8,015
estimate every visible row contradicted.

The estimate was **right** — Summer Magic Bayou is a real four-figure card. The
comps under it were wrong. Both halves of that sentence matter: the first
instinct was that a EUR 8,015 valuation on a vinyl screen must be the broken
part, and chasing that would have "fixed" the one number that was correct.

The fix was not a filter bolted on. It was to make the section answer its own
question — relevance-gated comps, ported from the server's
`_is_plausible_tcg_listing`, and an honest empty state when nothing survives.
**An unsupported estimate should look unsupported**, which is what "no listings
matching this item" achieves and what five wrong rows actively concealed.

### Deleting a reader twice is a sign the number is missing

"Movers" was deleted 2026-08-14 and "Holdings" lost its percentage 2026-08-26,
both for rendering `change_1d_pct`, which `/portfolio/items` has never returned.
Both times the fix was to delete the reader. **Nobody asked why the number did
not exist.** It was computable the whole time: `price_predictions` keeps
history, and 66,172 of 71,858 item_refs span >= 7 days.

When a feature is deleted twice for reading an empty column, the third response
should be to look at the writer.

### NULL is a claim, and `or 0` erases it

Three separate places this week turned "unknown" into a number:

- `((totals or {}).get("api_5xx") or 0) >= 10` — the 5xx alert vanished for two
  days while the window really held 16
- `float(r["change_7d_pct"] or 0)` would have made "no week-old prediction"
  read as "moved 0.0%"
- `h["source"] or "unknown"` labelled **100%** of comps "Unknown" while
  `provider` sat populated in the next column

The 2026-08-12 `[]`-vs-`None` work fixed the collector and not the consumers.
**Fixing the number is not fixing the alert built on the number.**

### What a "UI sweep" actually means here

Asked for an "alignment and professional UI sweep", the useful pass was
mechanical, not visual: invalid icon names (render an empty box, never throw),
Android-fatal `accessibilityRole`s, banned type sizes, line-height ratios. That
found **9 styles still on 10pt** across the item card. Reading the JSX found
nothing.

⚠️ And the sweep's own checker lied twice in one day: a ratio test flagged a
deliberate 1.25x display line-height, and a grep for leftover `openURL` matched
the phrase inside an explanatory comment. **A comment is not a reference,
including in your own checks** — and a checker written during an audit is
itself unaudited.

### Render the component, or the build finds it for you

The export bug was type-correct and shipped. `tsc` cannot prove a component
mounts. `@testing-library/react-native` was already a dependency; three suites
now mount the changed components in CI — asserting the `=== 1` boundary at 0/1/
2/5/undefined, that an empty-attribute LEGO item draws **no** heading while one
with `set_number` does, and that pressing Export never calls `Linking.openURL`.

## The populated card says what the empty one cannot (2026-08-28)

Every defect below was found by opening **one item that had real data in it** on
the simulator. The same screen with an empty item had been read several times
and looked fine. An empty state exercises the absence branch of every rule on
the screen; it cannot show you a row that renders the wrong fact, a number
missing beside a number that is present, or a filter that rejects everything it
is given.

### The number the screen exists for was the one number absent

The card led with **€95** and never mentioned the **€58** paid for it. Not a
styling problem — `cost_basis` and `unrealized_pl` are returned by the server
and already mapped by the client store, and the item screen simply never
rendered them. `learning_complete_feature_reachable_from_nowhere`: the code was
correct and ran nowhere.

Placed directly under the figure and **above** "Based on N recorded sales",
because that line qualifies how much to trust the number while this one says
what the number *means for the holder* — the stronger claim goes first.

⚠️ **EUR against EUR.** `items` carries the cost basis twice —
`purchase_price` in `purchase_currency`, and `purchase_price_eur`. The screen's
valuation is EUR. `computeItemDelta` therefore takes **explicitly named** EUR
arguments, so a caller passing the raw half has to ignore the parameter name to
do it (`learning_a_currency_column_needs_the_currency_applied`, ~170x wrong for
a JPY purchase). Both halves are now carried on the screen on purpose: the raw
one still feeds the edit field, in the member's own currency.

No cost basis renders **nothing**, never `+€0 (0.0%)`. A member who never told
us what they paid has no P/L, and a zero states a measured break-even.

### An empty row is noise — and the rule already existed one component down

"Collection: Not set" took a full line to say nothing.
`ItemAttributesSection` had stated the rule for the rows immediately below it —
*"Read mode lists only what exists — an empty row is noise. But edit mode
listing only what exists means a missing rarity can never be added"* — and the
card above it was never covered by it. The card was internally inconsistent:
the attribute list hid its blanks while the card printed its own.

**Measured before fixing: 73 of 112 items have no collection, 76 of 112 no
condition.** Two-thirds of members, not an edge case.

⚠️ **`reservedLabels` has to move with the row.** The card tells the attribute
list which labels it draws so the same fact is not rendered twice. A label
reserved by a parent that has *stopped* drawing it deletes the child's copy and
shows neither — `learning_removing_the_opener_strands_the_sheet`, one component
up. The reservation is now derived from the same booleans that gate the rows.

### A `false` on an undeclared field is bookkeeping, not a fact

A PSA 9 single rendered **"Sealed: No"** — the absence of a property a slabbed
card cannot have.

Enumerated rather than judged, per
`learning_keyword_filters_need_per_category_false_positive_audit`. Across all
112 prod items there is exactly **one** boolean attribute in existence:

| key | val | category | n |
|---|---|---|---|
| sealed | false | pokemon | 3 |

Not one `true`. And `POKEMON_FIELDS` never declares `sealed` — the key arrives
from an importer, not from anything a Pokémon member was asked.

**The discriminator is the category's own declared field list, not the word
"sealed".** That list is already the app's statement of which attributes mean
something where, so using it is not a keyword rule. LEGO and whiskey *do*
declare it and keep "Sealed / New in Box: No", because loose-vs-MISB is a real
price driver there. `true` survives everywhere. With no category the row is
**shown** — the same direction the diacritic-fold guard beside it fails in: a
redundant row beats a hidden fact.

The test asserting the LEGO case failed first, and the code was right — LEGO
labels the field "Sealed / New in Box". **A test written from memory of a label
is a test of the memory.**

### A row can render and still be invisible

The Items list showed a `LEGO` heading and a `Collection total €900` footer with
a row-shaped **blank** between them. The row was not missing; it was mounted at
opacity 0.

Relaunching the app made it appear, and that is what identified the cause rather
than the symptom: those items had been added while the app was open. Three lines
in `useStaggerReveal` combine into it — new values are created at `0`,
`reveal()` early-returns once it has latched, and the auto-start effect keys on
`count > 0`, which **does not change when a list grows from 8 items to 9**.
Anything appended after the first reveal was created invisible with nothing left
that would ever animate it up. Pull-to-refresh, pagination and an optimistic add
all reach it.

**Fixed by creating late arrivals visible, not by re-running the reveal.**
Re-revealing the tail is prettier and its failure mode is a row that stays
invisible — the bug being fixed. This version's failure mode is a row that
appears without an animation. On a list of things a member owns those are not
symmetric: *unanimated* is a cosmetic loss, *invisible* reads as sold, lost or
deleted. When a fix has two directions, pick the one whose failure is the
smaller lie.

### Four suites were passing and gating nothing

`verify:prebuild` names its jest files explicitly. Four were never in the list —
including one added the previous day, which I had assumed was gated because the
suite count went up (it had; a *different* file's tests accounted for the rise).
**A test file is not a gate until the gate names it.** Now 37 suites / 314
tests.

## A chip grid and a menu are not interchangeable (2026-08-29)

Requested as *"the marketplace filters section has category as a list of chips
rather than a drop down bubble menu ... i dont want chips menus but rather
bubble ios menus"*. `FilterSheet`'s Category section now renders a pill trigger
over an anchored checklist instead of a wrapped chip grid.

**The trap, and why the obvious implementation is wrong.** `CompactSelect`
already exists and is exactly the requested look — a pill with a chevron
opening an anchored popover. It is also **single-select**
(`value: string | null`, `onChange: (v: string) => void`), while
`config.categories` is an **array** and the marketplace genuinely filters on
several categories at once. Dropping it in would have looked right, satisfied
the request as literally worded, and silently removed multi-category filtering
that nobody asked to lose. The change here is a trigger + checklist, keeping
`handleToggleCategory` untouched.

Three details that are behaviour, not styling, and are pinned by tests:

- **The trigger states the selection** — "All categories" / the single label /
  "N selected". A trigger that only names the control makes you open it to
  learn what you already picked.
- **"All categories" CLEARS the array**, it does not select a sentinel. An
  empty array already means unfiltered to every downstream reader; a value like
  `'all'` would be a category nothing ever equals.
- **The menu is separate state from `expandedSection`.** Folding them together
  made the whole section disappear while the menu was open.

`FilterSheet` is shared by `app/listings.tsx` (Member Marketplace) and
`app/(tabs)/items.tsx`, so both surfaces changed together — deliberately, per
this doc's own rule that when N files draw one thing they drift.

⚠️ The `colors` prop here is a **narrow six-token subset**
(`background, card, text, muted, accent, border`) — no `overlay`, no
`accentText`. `tsc` caught both on the first attempt. The backdrop uses the
literal this file already uses twice; the Done label uses `colors.background`.

## The comment said one thing and the dependency array said another (2026-08-29)

`ItemNotesEditor` tracked a `lastSaved` baseline so Save could disable when
there was nothing to save:

```tsx
useEffect(() => {
  setLastSaved(notes);
  // ... We intentionally depend on `notes` only ...
}, []);            // <- empty
```

The notes value arrives from the server AFTER mount, so the component is almost
always constructed with `''`. With empty deps the baseline never resynced,
`hasChanges` was permanently true, and opening an item with existing notes
showed an enabled Save button with nothing to save — inviting a write-back of
the value already stored.

**A comment describing a dependency the array does not contain is not
documentation, it is a second opinion that lost.** Pinned by
`__tests__/components/itemNotesEditor.test.tsx`, which rerenders with the
server value and asserts Save is disabled; restoring the empty deps turns it
red.
