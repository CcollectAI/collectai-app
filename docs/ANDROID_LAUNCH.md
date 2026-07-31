# Android / Google Play Readiness

> Assessed 2026-07-31. The app **builds and runs on Android** — the codebase is
> cross-platform and the signing keystore already exists on EAS. What is missing
> is entirely account-and-console setup, none of which fails the build, and all
> of which silently degrades the app.

Run the gate rather than reading this list:

```bash
npm run preflight:android      # exit 0 = ready to build and submit
```

## The shape of the problem

Every Android gap found on 2026-07-31 was **silent**. No crash, no failed build,
no red test — Android just quietly did less than iOS:

| Gap | Symptom on Android | Why nothing caught it |
|-----|--------------------|-----------------------|
| `EXPO_PUBLIC_REVENUECAT_ANDROID_KEY` unset | Paywall shows "unavailable"; app cannot take money | `initPurchases()` returns early and logged at `warn`, which is stripped in release builds |
| No FCM config | Push never works | `getExpoPushTokenAsync()` throws into a `catch` in `usePushNotifications.ts:129` |
| `sparrow-play-service-account.json` absent | `eas submit` / `fastlane supply` fail | Only surfaces at upload time |
| Listing screenshots 1320×2868 RGBA | Play rejects the upload | Valid for the App Store, invalid for Play |
| `<Modal>` without `onRequestClose` | Back button cannot dismiss the sheet | No-op on iOS, so it only manifests on Android |

That is one pattern, not five bugs: **a platform-specific path that degrades to
a no-op instead of an error.** `scripts/preflight_android.mjs` exists so the
next one is found by a checker rather than by a store rejection.

## ⛔ The crash that "it launches fine" hid (2026-08-01)

Two logged-out device runs said the app was healthy. It was not. The moment a
**logged-in** session navigated off the root tabs, the app died:

```
FATAL EXCEPTION: main
com.facebook.react.bridge.JSApplicationIllegalArgumentException:
  Error while updating property 'accessibilityRole' of a view managed by: RCTView
Caused by: java.lang.IllegalArgumentException: Invalid accessibility role value: tabbar
  at ReactAccessibilityDelegate$AccessibilityRole.fromValue
```

`accessibilityRole="tabbar"` is **iOS-only**. On Android react-native throws
while creating the view — an uncatchable fatal on the main thread. One line,
`src/components/QuickNavBar.tsx:51`, and **38 screens mount `<QuickNavBar />`**:
settings, item detail, search, subscription/paywall, add-manual, analytics,
alerts, notifications, categories, the whole sell and purchase flow. Everything
past the five root tabs. Fixed to `"tablist"`, which is valid on both platforms.

**The lesson is about the verification, not the bug.** Launch-only testing gave
a clean bill of health twice. Nothing short of a real authenticated session
walking real screens would have found it — exactly what
`feedback_never_call_app_ready_without_e2e_verify` says. `preflight_android.mjs`
now validates every `accessibilityRole` against the Android-supported set
(mutation-proven: reverting the one character makes the gate fail).

### Proven by walking 30 routes, before and after

Same harness both times (deep links over `sparrow://`, scoring each route
`CRASH` / `NO-NAV` / `ok`, where `ok` requires the process alive, no new fatal,
**and** the view-hierarchy fingerprint actually changing — so a deep link that
silently fails to resolve cannot score as a pass):

```
buggy build:  13 CRASH        fixed build:  rendered=27  no-nav=3  CRASHED=0
```

Flipped `CRASH → ok`: `/settings` `/notifications` `/subscription` `/add-manual`
`/category-browse` `/condition-guide` `/sets-to-complete` `/leaderboard`
`/sell/dashboard` `/sell/offers` `/my-suggestions` `/mfa-setup` `/create-event`.

All 13 fatals in the before-run carried the **same** root cause — verified by
diffing the signatures, not assumed. The 3 `NO-NAV` rows are the `(tabs)` routes
the walk starts on (fingerprint cannot change); those were confirmed visually.

Two traps worth remembering when re-running this:
- **`adb install -r` does not swap a running process.** The old code keeps
  executing until a `force-stop`, so an install mid-test silently keeps testing
  the old build. Always `am force-stop` before scoring a new APK.
- A harness that only asks "did a new FATAL appear?" scores an unresolved deep
  link as a pass. The first version of this walk did exactly that and reported
  `/settings` and `/subscription` as `ok` while they were crashing.

## Verified on device (2026-07-31 → 2026-08-01)

Built `--profile android-apk --local` and run on an Android 16 x86_64 emulator.
Cold start is clean — login screen, branding, theme and fonts all correct, no
crash on launch. Logged in with a throwaway account and walked the app; see the
crash above for what that surfaced.

Also confirmed with a real session: the **paywall is intact** on this profile —
Home shows the "Upgrade" CTA for a free user, so `EXPO_PUBLIC_BETA_UNLOCK_ALL=false`
is genuinely in effect in `android-apk` (the reason that profile exists).
Insets are correct on the screens reached: the onboarding carousel, Home, and
the tab bar all clear the status bar and the gesture nav.

Two runs, before and after the fixes:

| Log line | Before | After |
|----------|--------|-------|
| `[silent-catch] useStoreReview.ts:26: Cannot find module` | 2 | **0** |
| `SafeAreaView has been deprecated` | 1 | **0** |
| `[purchases] ..._KEY not set` | generic, `warn` (stripped in release) | names `EXPO_PUBLIC_REVENUECAT_ANDROID_KEY`, at `error` |

Log lines that remain and are **correct**, not defects:

- `[silent-catch] _layout.tsx:92: Cannot find module` — `expo-updates`. OTA is
  deliberately not wired; the `require` is guarded for exactly this.
- `[AuthProvider] getSession error: TimeoutError after 8000ms`,
  `[supabase] request timed out after 15000ms`, `listItems timed out after
  8000ms`, `listWatchlist timed out — returning empty list`. These are the
  **designed** cold-start bounds from CLAUDE.md § "Loading states"
  (`AUTH_INIT_TIMEOUT_MS`, `installRequestTimeouts()`), firing because the
  emulator had just booted. They log at `error` on purpose. **Do not "fix"
  these by loosening or removing the bounds** — `AuthProvider`'s comment and
  `docs/AUTH_AND_WEB_DEPLOY.md` explain why `getSession` is safe to bound and
  why a second concurrent auth op revokes the session.
- `ANR in com.google.android.as` / `com.android.phone`, and a "System UI isn't
  responding" dialog — emulator processes under load right after boot. No ANR
  was ever raised against `io.sparrowcollect.app`.

Known and **not** Android-specific: on a logged-out cold start ~12 authenticated
endpoints fire and 401 before the redirect to login (`/portfolio/overview`,
`/billing/status`, `/alerts/trigger-history`, …), preceded by
`[DIAG auth] getAuthHeaders: NO TOKEN after refresh window`. Caught and
non-fatal, present on both platforms.

### Signing

Upload-key fingerprints of the local build, needed when registering the Android
app in Firebase and (later) Google Sign-In:

```
SHA-1:   4d7a2753f0903537290c94a5829e1fa6859c62b8
SHA-256: bfc37f04992e4168f39f159be2f62ea4d1339ba0021d89175c57a6efc28d5ef3
```

Once Play App Signing is enabled, Play re-signs with its own key — take the
*app signing* fingerprint from Play Console for anything user-facing.

## Status

### Done (in-repo)

- Package `io.sparrowcollect.app`, adaptive icon, `blockedPermissions`, and
  deep-link `intentFilters` with `autoVerify` — all in `app.json`.
- Upload keystore exists on EAS (the local build injects a signing config).
- Expo SDK 54 → `targetSdk` 36, above Play's current floor.
- Every `<Modal>` handles the Android back button (`onRequestClose`).
- `SafeAreaView` always comes from `react-native-safe-area-context` — the
  react-native one is iOS-only and renders as a plain `View` on Android.
- `expo-store-review` installed, so the review prompt can actually fire. It was
  `require`d by `useStoreReview.ts` and wired at `_layout.tsx:430` and
  `(tabs)/index.tsx:234`, but the package was never a dependency — the whole
  feature was dead on both platforms.
- Play listing images render natively at 1440×2560 with Android device chrome
  (`Play-*` compositions in `collectai-admin/video/src/Root.tsx`).
- `android-apk` build profile — an installable twin of `store` that still pins
  `EXPO_PUBLIC_BETA_UNLOCK_ALL=false`. (`store` emits an `.aab` that adb cannot
  install; `preview` emits an `.apk` but does not pin the flag, so it inherits
  `true` from the EAS `production` environment and the paywall disappears.)
- `.gitignore` now actually covers the Play publishing credential. It listed
  `google-play-service-account.json`, but every config uses
  `sparrow-play-service-account.json` — the credential would have been
  committed on creation. (`google-services.json` is deliberately left tracked:
  it holds public client identifiers, not secrets, and `app.json` will
  reference it, so a clean checkout must still build.)

### Blocked on console work (cannot be done from the repo)

Run `bash scripts/setup_play_store.sh` — it automates the GCP half and walks the
browser-only half in dependency order.

1. **Play Developer enrolment** ($25, identity must match the Apple enrolment).
2. **Play service account** → writes `sparrow-play-service-account.json`, which
   `eas.json` and `android/fastlane/Appfile` both already expect at the repo root.
3. **RevenueCat Android app** → `EXPO_PUBLIC_REVENUECAT_ANDROID_KEY`. See
   `docs/MONETIZATION.md` § "To Activate on Android".
4. **Firebase / FCM** → `google-services.json` + `expo.android.googleServicesFile`,
   then `eas credentials -p android` to upload the FCM V1 key.

### By design, not a gap

- **No Google Sign-In on Android.** `SOCIAL_LOGIN_ENABLED = false`
  (`src/config/featureFlags.ts:39`) hides the whole social block, and Apple
  Sign-In is iOS-only — so Android launches with email/password, matching the
  documented iOS launch decision in `docs/PUBLIC_LAUNCH_CHECKLIST.md`.

## Store listing images

Play enforces two rules the App Store does not, and both are invisible locally:

- the longest side may not exceed **2×** the shortest (the iOS 1320×2868
  masters are 2.173 → rejected);
- screenshots must be **24-bit PNG with no alpha** (the masters are RGBA).

Plus a policy point: a Play listing should not show iPhone hardware. So the Play
screenshots are rendered separately rather than reused:

```bash
cd collectai-admin/video && bash scripts/render-screenshots.sh --play
cd ../.. && python3 scripts/prepare_play_assets.py     # copies in + verifies
```

`prepare_play_assets.py` regenerates from the masters every run, so it is
idempotent. It falls back to padding the iOS masters if the Android renders are
missing, and says so — that is a stopgap for a build, not for a listing.

## Build and submit

```bash
npm run preflight:android                     # must exit 0

npm run build:android:local                   # signed .aab for Play
npm run build:android:apk                     # installable apk, same config

eas submit -p android --profile store --path ./builds/sparrow-android-local.aab
```

Both submit profiles default to track `internal`, `releaseStatus: draft` —
nothing reaches the public store without promoting it in Play Console.

> Do not run `eas build` without `--local`; cloud builds are billable and the
> project is on the free plan. Both npm scripts above already pass `--local`.
