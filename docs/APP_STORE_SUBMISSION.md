# App Store Submission Guide

Step-by-step guide for submitting Sparrow Collect to the iOS App Store and Google Play Store.

## Prerequisites

- Apple Developer Program ($99/year) enrolled
- Google Play Console ($25 one-time) enrolled
- EAS CLI installed: `npm install -g eas-cli`
- `eas login` completed
- Backend deployed and healthy (`/healthz` returning OK)
- All database migrations applied

## 1. EAS Build

### Initialize EAS project

```bash
eas init
```

This populates `expo.owner` and `expo.extra.eas.projectId` in `app.json`.

### Set EAS Secrets (env vars for production builds)

```bash
eas secret:create --name EXPO_PUBLIC_API_BASE_URL --value https://api.sparrowcollect.com
eas secret:create --name EXPO_PUBLIC_SUPABASE_URL --value https://<project>.supabase.co
eas secret:create --name EXPO_PUBLIC_SUPABASE_ANON_KEY --value <anon-key>
eas secret:create --name EXPO_PUBLIC_SUPABASE_MODE --value strict
eas secret:create --name EXPO_PUBLIC_SENTRY_DSN --value <sentry-mobile-dsn>
eas secret:create --name EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID --value <google-web-client-id>
eas secret:create --name EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID --value <google-ios-client-id>
eas secret:create --name EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID --value <google-android-client-id>
```

### Build for production — LOCAL ONLY

> ⛔ **Never run `eas build` without `--local`.** The Expo account is on the
> **Free** plan; a cloud build is a paid service and there is no budget line for
> it. This section used to read `eas build --platform ios --profile production`
> — following it verbatim queues a cloud build. Corrected 2026-08-20.
>
> The profile is **`store`**, not `production`. `production` exists in
> `eas.json` but the shipping scripts use `store`, and the two are different
> entries.

Use the npm scripts — they carry the profile, `--local`, `--non-interactive`
and the output path, and the Android one carries the whole JDK/SDK environment:

```bash
npm run build:ios:local        # -> ./builds/sparrow-ios-local.ipa
npm run build:android:local    # -> ./builds/sparrow-android-local.aab
npm run build:android:apk      # -> ./builds/sparrow-android-apk.apk (sideload/testing)
```

A local iOS build takes **25–45 minutes**, most of it compiling pods.

**Before building, run the gates:** `npm run verify:prebuild` (20 checks, tsc,
and the pinned jest suites). A build is the wrong place to discover a red gate.

**The build number is EAS-REMOTE.** `ios.buildNumber` in `app.json` is ignored
(`appVersionSource: remote`) and EAS prints exactly that warning on every run.
To see what the next build will be:

```bash
eas build:version:get --platform ios     # e.g. "iOS buildNumber - 146" -> next is 147
```

Do not "fix" the number in `app.json`; read the real one out of the IPA
(`CFBundleVersion`) if you need to prove what shipped.

Certificates are already provisioned (Apple Team `3DX8FBF7S6`, individual
account). EAS reports "All credentials are ready to build" at the start of a
local build — if it starts asking questions, something changed upstream.

## 2. Screenshot Requirements

### iOS (App Store Connect)

| Device | Resolution | Required? |
|--------|-----------|-----------|
| iPhone 6.9" (16 Pro Max) | 1320 x 2868 | Yes |
| iPhone 6.7" (15 Plus / 14 Pro Max) | 1290 x 2796 | Yes |
| iPad Pro 13" | 2064 x 2752 | Yes (supportsTablet: true) |

Minimum 3 screenshots per device size, recommended 6-10.

### Google Play

| Type | Resolution | Required? |
|------|-----------|-----------|
| Phone | 1080 x 1920 (min) | Yes (2-8 screenshots) |
| Feature graphic | 1024 x 500 | Yes |

### Recommended screenshot scenes

1. Collection overview — portfolio grid with values
2. Item detail — single item with valuation and price evidence
3. QuickScan — camera scanning a barcode
4. Price intelligence — valuation breakdown with chart
5. Deal discovery — purchase mandates with matched deals
6. Events — collector events with countdown timers
7. Categories — browsing the 36 category taxonomy
8. Analytics — portfolio value trends
9. Chat — messaging between collectors
10. Build & Paint — project tracking for Warhammer/Gunpla

**Capture with:** Xcode Simulator (Cmd+S), Android Studio emulator, or Fastlane snapshot.

## 3. Content Rating Questionnaire

Both Apple and Google require content rating information.

### Apple App Store

- **Age Rating**: 12+ (marketplace features, user-generated content)
- Unrestricted Web Access: No
- Gambling/Contests: No
- Simulated Gambling: No (marketplace is price tracking, not gambling)
- Frequent/Intense Horror: No
- Frequent/Intense Medical/Treatment Info: No
- Infrequent/Mild Profanity: No
- Infrequent/Mild Sexual Content: No
- Frequent/Intense Mature/Suggestive Themes: No

### Google Play

- Violence: No
- Sexuality: No
- Language: No
- Controlled Substance: No
- User Interaction: Yes (chat, connection requests)
- Shares Location: Yes (approximate, for events)
- Contains Ads: No
- Digital Purchases: Yes (subscriptions)
- **Target Age**: 13+ (COPPA-compliant age gate on registration)

## 4. App Review Notes

See `docs/APP_REVIEW_NOTES.md` for the full demo account walkthrough.

Key points for reviewers:
- Demo account pre-loaded with collection items across multiple categories
- Marketplace links are affiliate links (eBay EPN, TCGPlayer, etc.) — this is standard and disclosed
- Subscriptions use Apple/Google in-app purchase — Free / Pro (€4.99/mo or €39.99/yr)
- Age verification checkbox on registration (COPPA/GDPR compliance)
- Chat requires mutual connection (not open messaging)

## 5. Apple Privacy Nutrition Labels

Declare in App Store Connect under App Privacy:

| Data Type | Collected | Linked to Identity | Tracking |
|-----------|-----------|-------------------|----------|
| Email Address | Yes | Yes | No |
| Name (display name) | Yes | Yes | No |
| User ID | Yes | Yes | No |
| Photos or Videos | Yes | Yes | No |
| Coarse Location | Yes | No | No |
| Purchases | Yes | Yes | No |
| Product Interaction | Yes | Yes | No |
| Crash Data | Yes | No | No |
| Performance Data | Yes | No | No |

**Purpose**: App Functionality, Analytics

## 5a. Inventory Export

Two CSV exports for users:

**`/items-export/overview` (round-trip CSV — 12 columns)** — symmetrical with
`/api/imports/template`. Lets users export → edit in Excel/Numbers → re-import
without column drift. Surfaced from the **Items tab → Export CSV** button.
Currency-aware: respects `user_settings.currency`, accepts `?currency=USD/GBP/...`
override, FX-converts `estimated_value` from EUR storage to display currency
via `app.lib.fx_service.get_rates_from_eur()` (Frankfurter ECB-backed). Round-trip
preserved because re-imported values are stored back in EUR by the import handler.

**`/items-export/full` (comprehensive snapshot — 30 columns)** — for insurance,
accountants, full collection records. NOT round-trip with import. Surfaced from
**Settings → Download full inventory (CSV)**. Adds beyond the 12-col schema:
- `item_id` (canonical_key for cross-reference)
- `brand`, `set_or_series`, `rarity`, `variant`, `serial_number` from `items.attrs`
- `edition`, `is_limited_edition` (collapsed `"23 / 1000"` format), `is_first_edition`
- `quantity`, `for_sale`, `asking_price`, `asking_currency`
- `estimated_value_low` (q10) and `estimated_value_high` (q90) from `price_predictions`
- `collection_name`, `created_at`, `updated_at`

Photo URLs deliberately excluded — CSV isn't the right delivery for images.

Both endpoints rate-limited (5/min per user via `per_user_rate_limit`). FE
wiring at `src/api/miscApi.ts:exportItemsOverview` / `exportItemsFull`,
`src/components/settings/ProfileEditSection.tsx` and
`app/(tabs)/items.tsx:handleExportCSV`.

## 5b. In-App Account Deletion

Apple App Store guideline **5.1.1(v)** and Google Play's User Data policy
both require that apps offering account creation also offer in-app account
deletion. Sparrow Collect satisfies this end-to-end:

**FE entry point** — Settings → "Delete Account" (`src/components/settings/ProfileEditSection.tsx`).
Tapping the row opens a typed-confirmation modal: the user must type the
literal string `DELETE` before the destructive button enables. The modal
also blocks dismissal while the deletion request is in flight.

**FE → BE call** — `deleteAccount()` in `src/api/miscApi.ts` issues
`DELETE /account?confirm=DELETE_MY_ACCOUNT`. The query-string token is the
second guard (the modal is the first); the BE refuses any DELETE call that
doesn't carry it.

**BE handler** — `server/app/routes/account_router.py`:
- Rejects with `400 / CONFIRMATION_REQUIRED` when `?confirm` is missing or wrong.
- Rate-limited to 3 attempts/hour per user (`per_user_rate_limit`).
- Wraps deletion in a transaction; sets `statement_timeout = 15s` per
  statement and bounds the whole transaction with `asyncio.wait_for(60s)`.
- Deletes from a frozen allowlist of per-user tables: `mandate_deals`,
  `purchase_mandates`, `alert_trigger_history`, `user_price_alerts`,
  `item_provenance_events`, `watchlist`, `user_settings`,
  `user_category_follows`, `event_attendees`, plus `profiles` and
  `user_public_profiles`. Tables that don't exist in a given env are
  silently skipped (`UndefinedTableError`).
- Deletes the Supabase Auth user via `supabase_admin.auth.admin.delete_user`
  as a best-effort step **after** DB rows are gone — if Supabase fails the
  request still returns 200 because the user's data is already gone; the
  orphaned auth row is cleaned up out-of-band.

**Tables explicitly NOT touched**:
- `category_items`, `price_predictions` — global catalog, no `user_id`
  column. Including them aborted the transaction with "column does not
  exist" prior to 2026-04 and is now blocked by the allowlist.
- `market_hits` — anonymous crawl data, partitioned by month, no index on
  `user_id`. A DELETE there would scan every partition and time out.

**Tests** — `server/tests/test_account_router.py` covers: success path,
offline-mode 503, Supabase-failure-doesn't-block, no-Supabase-admin,
undefined-table-skipped, DB error 500, V1 endpoint, **missing-confirm 400**,
**wrong-confirm 400**.

## 6. Common Rejection Reasons & Mitigations

| Rejection Reason | How We Address It |
|-----------------|-------------------|
| 1.3 Kids Category | We gate registration with age verification (13+/16 EU). Not in Kids category. |
| 2.1 App Completeness | Provide demo account with pre-loaded data for review |
| 3.1.1 In-App Purchase | All subscriptions use StoreKit/Play Billing (no external payment for digital goods) |
| 3.1.2 Subscriptions | Clearly display pricing, auto-renewal terms, and cancellation instructions |
| 5.1.1 Data Collection | Privacy policy linked, nutrition labels filled, data use is transparent |
| 5.1.1(v) Account Deletion | In-app deletion in Settings with typed-confirmation modal — see §5b |
| 5.1.2 Data Use and Sharing | No third-party data sharing. Sentry for crash reporting only. |
| 4.0 Design (web views) | All features are native — no wrapped web views for core functionality |
| **4.8 Sign in with Apple** | **N/A at launch.** Authentication is email/password only — no third-party social login is offered (`SOCIAL_LOGIN_ENABLED=false` in `src/config/featureFlags.ts`), so guideline 4.8 does not apply. When Apple/Google Sign In are enabled post-launch, Apple Sign In will be shown at-or-above Google per HIG. |
| Affiliate Links | Clearly labeled as marketplace links, standard affiliate programs |

## 7. Submit to Stores

The build is LOCAL, so `eas submit` has to be pointed at the artefact on disk —
there is no cloud build for it to fetch. The npm script carries the path:

```bash
npm run submit:ios
# = eas submit --platform ios --profile store --path ./builds/sparrow-ios-local.ipa
```

The `store` submit profile already holds the Apple id, `ascAppId` 6767359453 and
team `3DX8FBF7S6` (`eas.json`), so it does not prompt.

> ⚠️ **`FINISHED` is not "on TestFlight".** The submit profile sets
> `skip_waiting_for_build_processing`, so a FINISHED submission means only that
> **Apple accepted the bytes**. The build then goes through processing, and it is
> not installable until that completes and (for external testers) review passes.
> Confirm in App Store Connect — or by the TestFlight email — before telling
> anyone it is available. This has been reported as "the build never arrived"
> when it had simply not finished processing.

> ⚠️ **The output path already holds the PREVIOUS build's IPA.**
> `--output ./builds/sparrow-ios-local.ipa` is a fixed path that is only
> overwritten when the build *succeeds*. So before and during a build, a
> complete, valid, submittable IPA of the **last** release is sitting there.
>
> That breaks the obvious ways of waiting for a build: `[ -f
> builds/sparrow-ios-local.ipa ]` is true immediately, and `ls builds/` looks
> finished. Caught on 2026-08-28 — a "wait for the artefact" loop returned at
> once against build 154's file while 155 was still compiling. Submitting there
> would have re-uploaded 154 and reported it as 155, and the submission would
> have *succeeded*.
>
> **Wait on the build PROCESS, and compare the artefact's mtime to the one you
> recorded before starting:**
>
> ```bash
> stat -f "%m" builds/sparrow-ios-local.ipa > /tmp/stale_mtime.txt   # BEFORE
> # ... build ...
> while pgrep -f eas-cli-local-build-plugin >/dev/null; do sleep 60; done
> [ "$(stat -f "%m" builds/sparrow-ios-local.ipa)" -gt "$(cat /tmp/stale_mtime.txt)" ] \
>   || echo "STALE — the build produced no new artefact"
> ```
>
> Then still read `CFBundleVersion` below. Two independent checks, because a
> failed build leaves a *plausible* file rather than no file.

**Verify what you actually shipped.** `app.json`'s `buildNumber` is ignored, so
read the number out of the artefact rather than the config:

```bash
unzip -p ./builds/sparrow-ios-local.ipa 'Payload/*.app/Info.plist' \
  | plutil -extract CFBundleVersion raw -o - -
```

**Android:** the first AAB upload MUST be done manually in the Play Console —
`eas submit` cannot create the app entry. After that, `eas submit --platform
android --profile store` works, but note it expects
`./sparrow-play-service-account.json`, which is **not in the repo** (see
`docs/ANDROID_LAUNCH.md` for the blocker chain).

## 8. Post-Submission

- Monitor review status in App Store Connect / Play Console
- Respond promptly to reviewer questions
- Typical review times: iOS 1-3 days, Android 1-7 days
- OTA updates via expo-updates for non-native bug fixes after approval

## Android / Play Store — local build

```bash
npm run build:android:local     # ~25 min, outputs ./builds/sparrow-android-local.aab
```

Wraps `eas build --platform android --profile store --local`. **Always `--local`** —
cloud builds are billable. The script bakes in `JAVA_HOME` (openjdk@17) and
`ANDROID_HOME` (android-commandlinetools) because they are not on the default PATH.

Two machine-level prerequisites live in `~/.gradle` and are NOT in this repo:

- `init.gradle` — sets `crunchPngs = false`. **Required.** aapt2 8.11.0 segfaults
  (exit 139) crunching Expo's generated `assets_placeholder.png`, failing the build
  at `:app:mergeReleaseResources`. Kept in `~/.gradle` so it survives the CNG
  prebuild that regenerates `android/` on every build.
- `gradle.properties` — `org.gradle.jvmargs=-Xmx5120m -XX:MaxMetaspaceSize=1024m`.

### ⚠️ On build FAILURE the log contains the keystore

`eas-cli-local-build-plugin` prints the job payload — including the **keystore and
its passwords, base64-encoded** — into the log when a build fails. After any failed
run, scrub `/tmp/android_build*.log` and treat the log as a secret. The keystore is
Expo-managed and rotatable via `eas credentials`.

### `android/` is generated

Only `android/fastlane/` is tracked (Play metadata: descriptions, screenshots,
feature graphic). Everything else under `android/` is produced by prebuild at build
time. **`expo prebuild --clean` deletes the tracked fastlane directory** — restore
with `git checkout -- android/fastlane/` if you run it manually.

