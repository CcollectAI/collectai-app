# Sparrow Collect — Public App Store Launch Checklist

> Generated 2026-05-12 · Last refreshed 2026-05-20. Replaces the scattered guidance in `SPARROW_LAUNCH_TOMORROW.md` (sections 8/11 obsolete) and `SPARROW_LAUNCH_SOLO_GUIDE.md`. This is the single source of truth for getting from "TestFlight beta works" → "App Store live with paid IAP".

---

## Session log — what's shipped since this doc was generated

**2026-05-20 evening** (RevenueCat + TestFlight unblocked, no commits — all ASC/RC dashboard work):

| Step | Result |
|---|---|
| ASC API Key regenerated | Old `VT5SJZ3AUH` revoked. New key `AM32RK7DAY` (Admin role) generated + downloaded + registered via `eas credentials` (uses `gh auth switch -u CcollectAI` since `vascoapp` was the active gh account). |
| Build #13 → TestFlight | Resubmitted via `eas submit --profile store --platform ios --id 6609f91e-d09a-4d62-a1a6-90ca80de9688` → ✅ "Submitted your app to Apple App Store Connect!" — processing on ASC. |
| ASC subscription products | Created subscription group `Pro` with localization `Sparrow Pro`. Two products: `sparrow_pro_monthly` (€4.99/mo, 1 month) + `sparrow_pro_yearly` (€39.99/yr, 1 year). Both at `Ready to Submit` status. |
| ASC In-App Purchase Key | Confirmed existing key `RevenueCat` / `3LX4HL24FM` active. `SubscriptionKey_3LX4HL24FM.p8` found at `~/Documents/Sparrow/Keys/RevCat/` (had to rename — file had a literal `*` in the name that RC's regex rejected). |
| RevenueCat App Store app | Created under `Sparrow` project. Uploaded `.p8`, Key ID, Issuer ID, App ID `6767359453`, Bundle ID `io.sparrowcollect.app`. Validation green. |
| RC entitlement `pro` | Created (lowercase, matches `PRO_ENTITLEMENT_ID = 'pro'` in `src/lib/purchases.ts:5`). Attached both products. |
| RC offering `default` | Created with packages `$rc_monthly` and `$rc_annual`. **Initial setup had swapped mappings** (would have charged users wrong price); corrected to `$rc_monthly → sparrow_pro_monthly`, `$rc_annual → sparrow_pro_yearly`. |
| EAS env `EXPO_PUBLIC_REVENUECAT_IOS_KEY` | Updated to new RC public app-specific iOS key via `eas env:create --force --visibility sensitive`. |
| Build #14 kickoff | `eas build --profile store --platform ios --auto-submit` — picks up the new RC key. Build id `76b78c81-0273-4a95-a245-0d39f6704cca`. In Free-tier queue → building → auto-submit on success. |
| Sandbox tester | `sandbox-merle@sparrowcollect.com` created in ASC Sandbox. To use: iPhone Settings → App Store → Sandbox Account, sign in before testing IAP. |
| Apple reviewer demo account | `apple-review@sparrowcollect.com` created in Supabase project `ykqrruipzmrrvjcvwfgp` with Auto-Confirm + `raw_user_meta_data.full_name = "Apple Reviewer"`. To be pasted into ASC App Review Information before submit. |

**Phases now complete (from sections below):**
- ✅ Phase 1 — ASC IAP products
- ✅ Phase 2 — RevenueCat wiring
- ⏳ Phase 3 — In flight: store-profile binary build (#14, rebuild required for new RC key to land)
- ⏳ Phase 4 — Demo account ready, just needs ASC App Review Info paste
- ☐ Phase 5 — ASC metadata (paste from `docs/app-store-aso.md`)
- ☐ Phase 6 — App Privacy nutrition labels
- ☐ Phase 7 — App Review Information
- ☐ Phase 7.5 — Run `node scripts/check-asc-listing.mjs` + `node scripts/analyze-bundle.mjs --cached`
- ☐ Phase 8 — Submit for review

**2026-05-20 morning** (3 commits, all bake-side perf + CI hygiene):

| Commit | What |
|---|---|
| `9350dae` | `nightly-sanity`: `count=exact` → `count=planned` (fixes false-FAIL on market_hits count timeout); switched healthz to `https://api.sparrowcollect.com/healthz`; events checks gated behind `PRE_LAUNCH_MODE=true` (default on) |
| `091c377` | `aggregate_catalog_attributes`: added `seen_at > now() - 90 days` partition filter — mtg went from hanging to 8.4s; full live run 15.3s for 14K groups |
| `c6e83fc` | `calibration_worker`: added `LIMIT 10000` to bound per-category work — was hitting 2min `statement_timeout` under bake IO load (mtg query was 8.6s at idle, blew up under load); now caps at ~85ms per category |

Both EC2 fixes deployed via `scripts/deploy_to_ec2.sh --restart --dirty`. Bake restarted twice, both clean. Zero worker errors in the 22h since the second restart. Verified live: full calibration cycle 156s, aggregate cycle 15.3s.

**Git auth note**: `gh` was authenticated as `vascoapp` (active account). Fixed via `gh auth switch -u CcollectAI` (the org account was already in the keyring). Also reverted the remote URL from SSH back to HTTPS (was changed mid-session; no SSH key registered on GitHub). All 15+ commits pushed to `origin/feature/all-enhancements`.

**2026-05-12 → 2026-05-19** (8 days, ~12 commits on `feature/all-enhancements`):

| Date | Commit | What |
|---|---|---|
| 2026-05-12 | `20ac609` | Beta-unlock flag wired; ASO metadata gaps closed |
| 2026-05-12 | `1f430e1` | Production-ready submission infra + `store` EAS build profile |
| 2026-05-12 | `aac8e53` | Dev/share-preview gated behind `__DEV__` |
| 2026-05-12 | `69c4224` | ShareCard ripped out entirely |
| 2026-05-12 | `9db6065` | Closed 4 post-launch follow-up gaps |
| 2026-05-12 | `8c9a170` | Brand sweep (13 files) + permission cleanup + dep prune |
| 2026-05-12 | `9f536ec` | RUNBOOK + deprecation banners on superseded launch guides |
| 2026-05-12 | `dadbe0d` | Privacy scrubbing + dev sentry tooling + listing/bundle checkers + auth tests |
| 2026-05-12 | `8d7a24d` | Wired pre-submission checkers into RUNBOOK + this checklist |
| 2026-05-12 | `d327294` | Sentry EAS build hook + GitHub Actions release workflow |
| 2026-05-18 | `d0c4713` | Onboarding rework: age→seller-gate (412 + auto-modal in httpClient + retry); followed-categories drive add-flow sort / scan classifier prior / catalog-match tiebreaker / home empty state / Deal Hub filter; auth bug fixes (OfflineBanner status-bar bleed, AuthTextInput tap-eating label, onboarding completion loop, Skip-button bypass) |
| 2026-05-19 | uncommitted | `eas.json` gained a `store` submit profile mirroring `production` (the `--profile store --auto-submit` flag from Phase 3 needed it) |

**Build history (`appVersionSource: remote`, auto-incremented):**
- Build #3 (buildNumber 9, ID `6ea51914`) — uploaded to ASC 2026-05-12
- Builds #10–12 — local iterations
- **Build #13 — building right now (2026-05-19)** on EAS via `eas build --profile store --platform ios --auto-submit`. Track at https://expo.dev/accounts/collectai/projects/collectai/builds/

**What's NOT changed since 2026-05-12:** Phases 1-9 below. The path is identical; the user-action checklist is unchanged.

---

**Prerequisites assumed done** (already checked off this session):
- ✅ Apple Developer enrolment paid + approved (Team `3DX8FBF7S6`)
- ✅ App Store Connect record created (App ID `6767359453`, bundle `io.sparrowcollect.app`)
- ✅ EAS auth + cert provisioning (cached in EAS keychain)
- ✅ EAS env vars (Supabase, API URL on HTTPS, Sentry source-map upload off)
- ✅ Web legal pages live: `/privacy.html`, `/terms.html`, `/user-policy.html`, `/support.html` (cleanUrls applied 2026-05-12, needs `cd web && vercel --prod` to deploy the rewrite)
- ✅ All metadata copy ready in `docs/app-store-aso.md`
- ✅ 6 App Store screenshots ready in `collectai-admin/video/out/screenshots/`
- ✅ Paywall screenshot ready: `~/Desktop/sparrow_paywall_1290x2796.png`
- ✅ Beta TestFlight build pipeline working (`eas build -p ios --profile production`)
- ✅ Store-launch build profile ready (`eas build -p ios --profile store` flips beta-unlock off)

---

## Track A — TestFlight beta (NOW)

The current build is on the `production` EAS profile. Beta-unlock flag is ON. Once it lands in TestFlight:

1. **Internal testing** — ASC → TestFlight → Internal Testing → add your Apple ID → install on your phone.
2. **Validate the beta** — sign-up → first scan → portfolio view → all paywalled tabs unlocked. If anything's broken, fix and rebuild before moving to Track B.
3. **External testing (optional)** — invite 10-100 beta testers via ASC → TestFlight → External Testing → paste the TestFlight beta description + "What to Test" copy from this session's chat → submit for Apple's lightweight beta review (~24 h).

**Do not move to Track B until you've eaten your own dog food in TestFlight for at least 24-48 h.**

---

## Track B — Public App Store launch (when you're ready)

### Phase 1 — Configure In-App Purchases in App Store Connect

ASC → My Apps → Sparrow Collect → **Monetization → Subscriptions**.

#### 1.1 Create Subscription Group

- Click **"+"** next to "Subscription Groups" → name it `Pro`.
- Add a localization (English) → display name `Pro`.

#### 1.2 Create `sparrow_pro_monthly` (€4.99/mo)

Inside the `Pro` group:

| Field | Value |
|---|---|
| Reference Name | `Pro Monthly` |
| Product ID | `sparrow_pro_monthly` |
| Subscription Duration | 1 Month |
| Price | €4.99 (EUR base — ASC auto-fills 175 storefronts) |
| Free Trial | (optional) 7 days |

**Localization (English):**
- Display Name: `Pro Monthly`
- Description: `Unlimited items, AI scans, market alerts, and advanced valuations.`

**Review screenshot:** upload `~/Desktop/sparrow_paywall_1290x2796.png` (the mock we generated this session).

#### 1.3 Create `sparrow_pro_yearly` (€39.99/yr)

Same group, same screenshot. Only differences:

| Field | Value |
|---|---|
| Reference Name | `Pro Yearly` |
| Product ID | `sparrow_pro_yearly` |
| Subscription Duration | 1 Year |
| Price | €39.99 |
| Display Name | `Pro Yearly` |
| Description | `Save 33% vs monthly. Unlimited items, AI scans, market alerts, and advanced valuations.` |

Both will sit at status **"Ready to Submit"** — that's correct; they ship live with the first reviewed build.

#### 1.4 In-App Purchase API Key for RevenueCat

ASC → Users and Access → Integrations → **In-App Purchase** keys → **Generate In-App Purchase Key**.

- Name: `RevenueCat`
- Click Generate → **Download the .p8 file immediately** (one-time download; can't be re-downloaded)
- Note the **Key ID** (10 chars) and **Issuer ID** (UUID at the top of the Integrations page)

Save the `.p8`, Key ID, and Issuer ID — you'll paste them into RevenueCat next.

---

### Phase 2 — Configure RevenueCat dashboard

Go to [app.revenuecat.com](https://app.revenuecat.com) → your `Sparrow` project (already created this session).

#### 2.1 Add iOS app configuration

If not already done:
- **Project settings → Apps and providers → Add app → App Store**
- Bundle ID: `io.sparrowcollect.app`
- Upload the `.p8` file from step 1.4
- Paste the Key ID and Issuer ID
- Save

The page now shows a **Public app-specific API key** (starts with `appl_…`). Copy it.

#### 2.2 Push the iOS SDK key to EAS

In your local terminal:

```bash
cd /Users/merle/GitHub/CcollectAI
eas env:create --environment production --name EXPO_PUBLIC_REVENUECAT_IOS_KEY \
  --value 'appl_PASTE_HERE' --visibility sensitive --non-interactive
```

This is the key the iOS app uses at runtime to talk to RevenueCat. Without it, `src/lib/purchases.ts:isPurchasesAvailable()` returns `false` and the subscription screen falls back to "Coming soon".

#### 2.3 Import products

RevenueCat dashboard → **Product catalog → Products** → **Import from App Store** → select both `sparrow_pro_monthly` and `sparrow_pro_yearly`.

If they don't appear, ASC needs a few minutes after creation to propagate. Refresh and retry.

#### 2.4 Create the `pro` entitlement

**Product catalog → Entitlements → New entitlement**

- Identifier: `pro` (**lowercase** — must match `PRO_ENTITLEMENT_ID = 'pro'` in `src/lib/purchases.ts:5`)
- Attach both products from step 2.3

#### 2.5 Wire the offering

**Product catalog → Offerings → "default" offering** (RC creates one automatically).

Add two packages:
- Package identifier: `$rc_monthly` → linked to `sparrow_pro_monthly`
- Package identifier: `$rc_annual` → linked to `sparrow_pro_yearly`

These identifiers match what `app/subscription.tsx:151` reads (`offerings?.current?.monthly` and `offerings?.current?.annual`). Other names will silently produce a "Coming soon" UI.

#### 2.6 Sandbox tester (for your testing before submission)

ASC → Users and Access → **Sandbox → Testers** → "+" → create a tester with a fake email like `sandbox-merle@sparrowcollect.com`. You'll use this Apple ID on your iPhone (Settings → App Store → Sandbox Account) to test purchase flow without real charges.

---

### Phase 3 — Build the store-submission binary

```bash
cd /Users/merle/GitHub/CcollectAI
eas build -p ios --profile store --auto-submit
```

The `store` profile (added 2026-05-12 in `eas.json`) sets `EXPO_PUBLIC_BETA_UNLOCK_ALL=false`, so:
- Subscription screen renders the real plan cards (not the beta panel)
- `useBillingLimits()` actually queries RevenueCat for entitlements
- Paywalled features lock until purchase

Build runs ~20 min. Auto-submits to App Store Connect when done.

**Before submitting for review, install the build on your phone via TestFlight** and run through:
1. Sign in as a fresh user → confirm Free tier limits apply (3 mandates, locked Analytics, locked Deal Discovery)
2. Open Subscription tab → tap "Pro Monthly" → sandbox tester completes purchase → confirm Pro unlocks
3. Tap "Restore Purchases" on a fresh install with the same sandbox tester → entitlement restores
4. Try the "Subscription" deep link from inside a locked feature → opens subscription screen, not crash

If anything fails, do NOT submit for review. Fix in code, rebuild, retest.

---

### Phase 4 — Demo account for Apple's reviewer

ASC's reviewer needs to log in to test your app. **Create this Supabase account before submission**:

[supabase.com/dashboard](https://supabase.com/dashboard) → project `ykqrruipzmrrvjcvwfgp` → **Authentication → Users → "Add user" → "Create new user"**

- Email: `apple-review@sparrowcollect.com`
- Password: `SparrowReview2026!` (or your choice — match what you paste into ASC)
- **✅ Auto Confirm User** — must be checked
- Click **Create user**

(Optional) Click the new user row → edit `raw_user_meta_data`:
```json
{ "full_name": "Apple Reviewer" }
```

Verify by signing in as this user on your TestFlight build. If any flow fails for the demo user but works for your real account, Apple will reject the submission.

---

### Phase 5 — Fill App Store Connect metadata

All copy lives in **`docs/app-store-aso.md`**. Open it and paste each section into the corresponding ASC field:

| ASC field | Source line in `app-store-aso.md` |
|---|---|
| App Name | line 13: `Sparrow Collect` |
| Subtitle | line 18: `Scan, Value & Track` |
| Keywords | line 23 |
| Promotional Text | line 28 |
| Description | lines 33-79 |
| What's New (for updates) | lines 83-89 |
| Primary Category | Lifestyle |
| Secondary Category | Shopping |
| Support URL | `https://sparrowcollect.com/support` (works after `vercel --prod` from `web/`) |
| Marketing URL | `https://sparrowcollect.com` |
| Privacy Policy URL | `https://sparrowcollect.com/privacy` |
| Copyright | `© 2026 Merle Slendebroek` |

Upload all 6 screenshots from `collectai-admin/video/out/screenshots/`.

---

### Phase 6 — App Privacy nutrition labels

ASC → App Information → **App Privacy** → "Get Started" → questionnaire.

Use the answers in **`docs/app-store-aso.md` lines 620-672** ("App Privacy Nutrition Label" section). Key answers:

- **Do you collect data?** Yes
- Collected types: Email, Name, User ID, Photos, Camera, Coarse Location, Purchase History, Product Interaction, Crash Data, Performance Data, Diagnostics
- **Is data linked to user identity?** Mostly yes (except Device ID — anonymous PostHog distinct_id)
- **Used to track across apps/websites?** **No.** (App has no IDFA / ad SDK / cross-app tracking.)

The full mapping is in the doc — just transcribe row-by-row.

---

### Phase 7 — App Review Information

ASC → App Information → **App Review Information**.

| Field | Value |
|---|---|
| Sign-in required | Yes |
| Demo Account: Username | `apple-review@sparrowcollect.com` |
| Demo Account: Password | `SparrowReview2026!` (whatever you set in Phase 4) |
| Contact First Name | Merle |
| Contact Last Name | Slendebroek |
| Contact Email | `apple@sparrowcollect.com` (or `slendebroekmerle@gmail.com`) |
| Contact Phone | (your phone number from Apple Developer account) |
| Notes (free text) | Paste from `docs/app-store-aso.md` lines 707-727 (the reviewer-notes paragraph) |

---

### Phase 7.5 — Pre-flight validation (~30s, run before submit)

Catch length-limit violations + bundle-size issues BEFORE Apple does:

```bash
cd /Users/merle/GitHub/CcollectAI
node scripts/check-asc-listing.mjs   # validates app-store-aso.md fields
node scripts/analyze-bundle.mjs --cached  # bundle weight check
```

The listing checker caught a real bug (Play Short Description 83/80 chars) when first run on 2026-05-12. If either script exits non-zero, fix before Phase 8.

---

### Phase 8 — Submit for review

ASC → **App Store** tab → Prepare for Submission → at the bottom click **"Add for Review"** → confirm.

Apple's review typically takes **1-3 days for first-time submissions**. They may ask questions about:
- IAP not working in their test (most common — they don't have a sandbox account; the reviewer notes explain this)
- The RevenueCat SDK reference in your code (just confirm: handled via Apple-approved StoreKit)
- The 37 marketplace sources claim (confirm: data only, no scraping from the app itself)

Respond to all reviewer questions within 24 h or the queue resets.

---

### Phase 9 — After approval

1. Use the **"Manual release"** option in ASC, not "Automatic release after approval", so YOU pick the launch moment.
2. Pick a Tuesday or Wednesday at 10 AM ET (peak App Store traffic, lower review-queue risk).
3. Coordinate with marketing pushes (TikTok / Twitter launch thread → see `docs/app-store-aso.md` for templated copy).
4. Monitor:
   - ASC → Analytics → impressions, page views, conversions
   - RevenueCat → Charts → trials, MRR
   - Sentry → crash rate (target <0.5%)
   - PostHog → user funnels (`subscription_screen_viewed`, `subscription_upgrade_completed`)

---

## Things explicitly NOT needed for v1

These appear in older launch docs but you can ignore them for the first App Store submission:

- ❌ `/webhook/revenuecat` server endpoint — v1.1 work; FE-only gating via RevenueCat `customerInfo` is sufficient. (Memory: `project_iap_blocker.md`)
- ❌ Stripe live mode — RevenueCat replaced it 2026-05-09 (commit `652230a`). Don't waste time creating Stripe products.
- ❌ Google OAuth client IDs — beta uses email/password auth. Add Google Sign-In post-launch.
- ❌ Google Play Console submission — iOS first. Android can ship 1-2 weeks later from the same codebase.
- ❌ Apple Sign-In service ID / Key — only needed when you wire Apple Sign-In through Supabase. Not required for App Store approval.

## File-level checklist

Re-run before every `eas build -p ios --profile store`:

- [ ] `eas env:list --environment production` shows `EXPO_PUBLIC_REVENUECAT_IOS_KEY` (sensitive)
- [ ] `git status` is clean (no uncommitted changes)
- [ ] `npx tsc --noEmit` reports zero errors on changed files
- [ ] `ios/SparrowCollect/Info.plist` has `NSAllowsArbitraryLoads = false` (already correct)
- [ ] `app.json:CFBundleVersion` will auto-increment because `autoIncrement: true` in `eas.json` store profile
- [ ] Web legal pages reachable: `curl -sIL https://sparrowcollect.com/privacy https://sparrowcollect.com/support` returns 200
- [ ] `apple-review@sparrowcollect.com` Supabase user exists and can log in via TestFlight build
