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

## ▶ RESUME HERE — Android QA pass, 2026-08-01 (unfinished)

Driven from `docs/TESTFLIGHT_QA_CHECKLIST.md`, on an Android 16 x86_64 emulator
with a real logged-in session. **Sections 3, 4b, 5, 6, 9, 10 are NOT run.**

### Setup to get back to where this stopped

```bash
# 1. Emulator (it hosts a SECOND project's app — see gotchas)
$ANDROID_HOME/emulator/emulator -avd SammySamPixel -no-snapshot-load -no-boot-anim &
adb wait-for-device
adb shell am force-stop com.sammysam.app     # ALWAYS do this first, see gotchas

# 2. Latest APK with every fix in this doc (rebuild if the tree moved on)
npm run build:android:apk                    # -> builds/sparrow-android-apk<N>.apk
adb install -r builds/sparrow-android-apk5.apk
adb shell am force-stop io.sparrowcollect.app   # install -r does NOT swap running code
adb shell monkey -p io.sparrowcollect.app -c android.intent.category.LAUNCHER 1

# 3. Permissions without fighting dialogs
adb shell pm grant io.sparrowcollect.app android.permission.CAMERA
adb shell pm grant io.sparrowcollect.app android.permission.READ_MEDIA_IMAGES
```

**QA account** (created via anon signup, confirmed with SQL over `DB_DSN_DIRECT`
— there is no service-role key anywhere): `android-qa-20260801@sparrowcollect.com`
/ `AndroidQA!20260801x`. It has 3 test items. Delete it when done.

### Coverage so far

| Section | State |
|---------|-------|
| 1 Auth | **Partial** — login verified. Signup + email-confirm NOT run |
| 2 QuickScan | **PASS** — camera → capture → vision sets category → Add Manually → Save |
| 3 Photo-library scan | **client PASS / server bug found + FIXED** — see below |
| 4 Collection view | **PASS** — items list, item detail opens, photo, no fatals |
| 4b Spreadsheet import | **NOT RUN** |
| 5 Paywall | **PASS (degraded, as expected)** — see below |
| 6 Settings / sign-out | **PASS** — sections load; sign out shows a confirm dialog, signs out and redirects to login, no crash. Account block also has Change Password / Export Insurance Report / Download inventory CSV / Delete Account |
| 7 Deep links | **PASS** — both hosts `verified`, link opens the app |
| 8 Permissions | **Partial** — camera + notifications granted. Calendar NOT run |
| 9 Network / offline | **FAILED → FIXED** — see below (`e8c73d6`) |
| 10 Crash audit | **PASS** — 30 routes 0 crashes; background→foreground keeps pid; rotation clean |

**Section 5 detail.** `/subscription` renders **"Subscriptions Coming Soon"** —
the `iapUnavailable` branch, because `EXPO_PUBLIC_REVENUECAT_ANDROID_KEY` is
unset. So **Android cannot take money**, now observed rather than inferred. The
checklist's *serious* case (no paywall anywhere ⇒ beta flag leaked into a
shippable profile) is NOT happening: Home shows the free-tier "Upgrade" CTA, so
`EXPO_PUBLIC_BETA_UNLOCK_ALL=false` really is in effect. Legal copy correctly
says "Google Play subscriptions", not Apple. Purchase itself is untestable
until the RevenueCat key exists.

**Section 9 detail — real bug, fixed.** Airplane-mode ON→OFF left Items showing
"Start your collection" while the server had 4 items (verified directly against
the REST API). Only a manual pull-to-refresh recovered it. An empty list reads
as "you own nothing", not "the fetch failed", so a brief signal drop looks like
data loss. `onReconnect` existed but its only consumer replayed queued WRITES;
nothing re-fetched READS. Fixed in `usePaginatedList` so every list screen gets
it — `e8c73d6`, mutation-proven.

### Section 3 detail — a NOT-Android-only bug, found by driving Android

The client flow is fine: picker → Front/Back label → Android photo picker →
crop. Then the upload 500'd:

```
POST /items/{id}/images  ->  500 {"code":"DB_ERROR","detail":"Failed to add item image"}
```

**`20260226_item_images.sql` had silently no-opped.** It used
`CREATE TABLE IF NOT EXISTS` and a DIFFERENT `public.item_images` already
existed — `(id, user_id, item_id, url, created_at)` — so the migration reported
success and did nothing. The API has always written `(item_id, image_url,
label, position)`, none of which existed, and never supplied the required
`user_id`. Adding a photo to an item has therefore **never worked, on either
platform**.

Worse, the **read** path had already been patched around it — aliasing
`url AS image_url` and hard-coding `NULL::text AS label`. That stopped GET
500ing but guaranteed label and position were always null, so front/back and
ordering could never work even in principle. The write path was never patched.

Fixed 2026-08-01 (table was empty in prod, so rebuilt rather than patched):
- `20260801_fix_item_images_schema.sql` — correct columns, label CHECK, index, 4 RLS policies
- `20260801_restore_images_needing_embeddings.sql` — the CASCADE dropped
  `v_images_needing_embeddings` (consumed by `ops/embed_images.py`); rebuilt
  against `image_url`
- `item_images_router.py` — read the real columns, order by position
- `marketplace_listing_router.py` — also read `item_images.url`; the router-drift
  gate caught it before restart
- `schema.lock.json` regenerated; all 9 preflight gates pass; API restarted, healthz 200

**Two lessons worth keeping.** `CREATE TABLE IF NOT EXISTS` is not idempotent
when a *different* table already owns the name — it is a silent no-op, and the
migration will report success forever. And a DDL fix must be swept across every
router: `preflight_router_drift` is what stopped this from hard-downing the API
on restart.

### Driving the Settings screen

Sign-out is near the **BOTTOM** of Settings — order is Privacy → Notifications →
Appearance → Accessibility → Alerts → **Account** (`ProfileEditSection`). An
earlier note in this doc said "near the TOP"; that was wrong.

Two things make it hard to reach with adb:
- The Account block is inside `{user && (…)}`, so a wedged session hides it
  entirely and it looks like the control is missing.
- Swiping down the CENTRE of the screen drags across switch rows and opens
  sub-modals (Region picker, etc). **Swipe in the left margin (x≈60)** instead.

### ⚠️ Do not repeat: minting tokens while the app holds a session

Late in the run every on-device Supabase query began timing out at 15s
(`items`, `profiles`, `v_chat_inbox_v1`, `chat_dm_requests_v1`) while the SAME
queries returned in **~0.1s** server-side and the device pinged Supabase at
44ms/0% loss. So it was not the network and not the server.

The likely cause is self-inflicted: this session repeatedly minted tokens via
`grant_type=password` for the QA account **while the app held a live session**.
That is the rotating-refresh-token reuse that Supabase treats as theft — see
`project_2026_07_11_auth_401_root_cause_lock`. Queries then stall behind the
auth lock exactly as CLAUDE.md § "Loading states" describes.

**When you need a token for server-side checks, use a DIFFERENT account than
the one signed in on the device.** If the device wedges, sign out and back in.

Also swept: 21 screens for **error states** (not just crashes) — 0 found.

### Emulator gotchas that cost hours — read before driving the UI

1. **A second app (`com.sammysam.app`) steals foreground.** `am start` returns
   success while SammySam is actually in front, so taps and typed text land in
   the wrong app. It happened twice, including typing the QA credentials into
   it. **Force-stop it first, and screenshot to confirm which app you are in —
   text-only `uiautomator` dumps cannot tell you.** `monkey -c LAUNCHER`
   foregrounds reliably where `am start` silently fails.
2. **`adb install -r` does NOT swap a running process.** Old code keeps
   executing until `am force-stop`. An install mid-test silently keeps testing
   the previous APK.
3. **`pm get-app-links` state `1024` = "approved WITHOUT verification"**, not
   verified. Only the literal string `verified` counts.
4. **`adb shell input text` truncates** against a controlled RN `TextInput` —
   type in ~4-char chunks with sleeps. The device shell also mangles `-`
   unless the whole string is single-quoted.
5. **Tap coordinates shift between screens.** Read the target's position from a
   `uiautomator` dump each time; a hardcoded y-value silently misses and you
   will think a field is empty when your tap simply landed elsewhere.
6. **The emulator died twice and lost network once** (ANR storms). If
   `TypeError: Network request failed` appears, reset the radios:
   `adb shell svc wifi disable && adb shell svc data disable` then re-enable.
   Do not file those as app bugs.
7. **`uiautomator` itself crashes** (`FATAL EXCEPTION ... UiAutomation`). Those
   fatals are the tooling, not the app — check for `Process: io.sparrowcollect.app`
   before counting a fatal.

### A false trail, recorded so it is not re-walked

Several cycles went into a "Save to Collection is permanently disabled" bug
that **does not exist**. The saves were succeeding and the form was resetting,
so `canSubmit` correctly went false on an empty name. The Items tab would have
shown 3 saved items in one tap. **Check the destination before theorising about
the mechanism.**

That hunt did surface a real latent issue by code inspection — the unbounded S3
PUT in `usePhotoUpload` — fixed in `057038c`, but never reproduced on device.

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
- **Android App Links work** (fixed + deployed 2026-08-01). `assetlinks.json`
  had a wrong package and a placeholder fingerprint, so every
  `https://sparrowcollect.com/*` link opened the browser. Now `verified` on
  device for both hosts, accepted by Google's Digital Asset Links API, and a
  fired link resolves to `.MainActivity`. Details + the Play App Signing caveat:
  `docs/AUTH_AND_WEB_DEPLOY.md`.
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
