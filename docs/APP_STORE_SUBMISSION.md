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

### Build for production

```bash
# iOS
eas build --platform ios --profile production

# Android
eas build --platform android --profile production

# Both at once
eas build --platform all --profile production
```

EAS will walk through certificate/provisioning setup on first build:
- **iOS**: Creates Distribution Certificate + Provisioning Profile (let EAS manage)
- **Android**: Generates upload keystore (EAS stores it securely)

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
- Subscriptions use Apple/Google in-app purchase — Free/Pro ($4.99)/Premium ($9.99)
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
| **4.8 Sign in with Apple** | **Required because we offer Google Sign In.** Service ID `com.sparrowcollect.app.auth` configured in Apple Developer; Supabase Auth → Providers → Apple wired with Team ID + Key ID + .p8. FE login screen shows the Apple Sign In button at-or-above the Google Sign In button per HIG. |
| Affiliate Links | Clearly labeled as marketplace links, standard affiliate programs |

## 7. Submit to Stores

```bash
# Submit iOS build to App Store Connect
eas submit --platform ios --profile production

# Submit Android build to Google Play
eas submit --platform android --profile production
```

**Important for Android:** The first AAB upload MUST be done manually via Play Console.
Download the AAB from EAS (`eas build:list`) and upload to the internal testing track.
Subsequent submissions can use `eas submit`.

## 8. Post-Submission

- Monitor review status in App Store Connect / Play Console
- Respond promptly to reviewer questions
- Typical review times: iOS 1-3 days, Android 1-7 days
- OTA updates via expo-updates for non-native bug fixes after approval
