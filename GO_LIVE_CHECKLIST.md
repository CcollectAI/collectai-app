================================================================================
  SPARROW COLLECT — GO-LIVE CHECKLIST
  Generated: 2026-02-18 · Last refreshed: 2026-05-20
================================================================================

> **For the current launch path, use [`docs/PUBLIC_LAUNCH_CHECKLIST.md`](docs/PUBLIC_LAUNCH_CHECKLIST.md)** — it's the single source of truth from "TestFlight beta" → "App Store live with paid IAP".
>
> This file is the historical infra/setup checklist (DNS, EC2, .env, Supabase migrations, EAS secrets). Most of it is now done — see status below. Kept for reference if you need to rebuild any layer from scratch.

  Brand: Sparrow Collect (formal) / Sparrow (colloquial)
  Domain: sparrowcollect.com (Cloudflare, purchased 2026-05-04, SSL fixed 2026-05-08)
  Bundle ID: io.sparrowcollect.app (com.sparrowcollect.* was rejected by Apple)
  Deep-link scheme: sparrow://
  Brand color: #81D8D0 (Tiffany Blue)
  App Store Connect App ID: 6767359453
  Apple Team ID: 3DX8FBF7S6 (Individual enrolment, NL eenmanszaak, KvK 99596326)

--------------------------------------------------------------------------------
 EXECUTIVE STATUS — 2026-05-20
--------------------------------------------------------------------------------

CODE: SHIPPING. TestFlight build #13 (id 6609f91e) submitted successfully
via new ASC API Key AM32RK7DAY. Build #14 (id 76b78c81) building with new
RevenueCat key + auto-submit. RevenueCat fully wired end-to-end this
evening: ASC products created (sparrow_pro_monthly €4.99/mo + sparrow_pro_yearly
€39.99/yr), In-App Purchase Key 3LX4HL24FM uploaded, entitlement `pro`
attached, offering `default` with $rc_monthly + $rc_annual packages.
Sandbox tester + Apple reviewer demo account both created.

Three bake/CI hardening commits landed 2026-05-19/20 (c6e83fc, 091c377,
9350dae) — calibration_worker no longer times out, aggregate_catalog_attributes
no longer hangs, nightly sanity no longer false-FAILs on count timeouts.
  * Preflight chain (6 gates): ALL PASS (deps, env, worker imports, schema drift,
    RLS check, models). systemd ExecStartPre refuses to start if any fails.
  * Bake monitors: 3 in-process monitors live (sustained-error paging, circuit
    breaker stuck-OPEN page, instance health — disk/RSS/ingest stall/matview stall).
  * Tests: 3,325 BE + 516 FE pass, 0 TS errors in shipped code, 58 snapshots.
    (Pre-existing TS errors in `app/item/[id].tsx` not blocking EAS build.)
  * Security advisor: 7 remaining WARN-level (4 extension_in_public, 3 dashboard-only).
  * Data scaling: market_hits + price_predictions + price_history partitioned monthly.
    pg_cron job id=32 auto-creates next-month partition on the 25th @ 02:00 UTC.
  * Infrastructure: 44 marketplace adapters, 54 categories, ~140K catalog items,
    528K market_hits, 99K+ price_predictions, 36 Ridge models, data lake on S3.

USER ACTIONS DONE (since launch push started 2026-05-04):
  [x] Apple Developer enrolment — Individual, paid + approved 2026-05-07
  [x] App name decision — Sparrow Collect (formal) / Sparrow (colloquial)
  [x] Brand rename sweep — app.json, src/, web/, locales (7), legal copy
  [x] eas.json submit creds — ASC App ID 6767359453, Team ID 3DX8FBF7S6
  [x] Domain purchase + DNS — sparrowcollect.com live via Cloudflare + Vercel (SSL OK)
  [x] EC2 SSL — Let's Encrypt on api.sparrowcollect.com
  [x] App Store Connect record created — bundle `io.sparrowcollect.app`
  [x] EAS store profile (BETA_UNLOCK_ALL=false) — eas.json:32
  [x] RevenueCat IAP — Free + Pro shipped 2026-05-09 (commit `652230a`)
  [x] Onboarding rework — age→seller-gate + followed-cat surfaces (commit `d0c4713`, 2026-05-18)

USER ACTIONS REMAINING (before App Store submission):
  [ ] RevenueCat dashboard configuration — see PUBLIC_LAUNCH_CHECKLIST.md Phase 2
        (revenuecat.com account, iOS app + .p8 + Key ID/Issuer ID, products,
         `pro` entitlement, default offering with `$rc_monthly` + `$rc_annual`)
  [ ] App Store Connect IAP products — sparrow_pro_monthly (€4.99/mo),
        sparrow_pro_yearly (€39.99/yr) — Phase 1 of PUBLIC_LAUNCH_CHECKLIST.md
  [ ] Sandbox tester for purchase QA — ASC → Users → Sandbox → Testers
  [ ] Demo user for Apple reviewer — apple-review@sparrowcollect.com in Supabase
  [ ] App privacy nutrition labels — ASC questionnaire (answers in
        docs/app-store-aso.md lines 620-672)
  [ ] App Review Information — demo creds + contact + reviewer notes
  [ ] Submit for review — Phase 8 of PUBLIC_LAUNCH_CHECKLIST.md
  [ ] Supabase dashboard toggles — HIBP, OTP expiry, Postgres upgrade (post-launch)

DEFERRED (NOT required for v1):
  - Stripe Live keys — replaced by RevenueCat for iOS IAP (Stripe code path
    remains in `server/app/billing_router.py` for future web/Android billing).
  - Google OAuth (web/iOS/Android client IDs) — beta uses email/password.
  - Google Play submission — iOS first; Android ships 1-2 weeks later.
  - Apple Sign-In service ID / .p8 key — not required for App Store approval.

ESTIMATED TIME TO SUBMIT: ~3-4 hours of dashboard clicks once TestFlight
build #13 lands (RevenueCat dashboard config + IAP setup + ASC metadata +
nutrition labels + reviewer info). Apple review: 1-3 days.

--------------------------------------------------------------------------------

================================================================================
 1. DOMAIN & DNS  ✅ DONE
================================================================================

[x] Buy sparrowcollect.com (purchased 2026-05-04)
[x] Cloudflare DNS configured:
    - api.sparrowcollect.com -> 51.21.210.195 (DNS-only, grey cloud)
    - sparrowcollect.com -> Vercel (proxied)
    - www.sparrowcollect.com -> CNAME sparrowcollect.com (proxied)
[x] DNS propagation verified (`dig api.sparrowcollect.com +short`)
[x] Vercel project linked: collectais-projects/sparrowcollect

================================================================================
 2. SUPABASE PROJECT SETUP  ✅ DONE
================================================================================

[x] Project: ykqrruipzmrrvjcvwfgp (eu-central-1 Frankfurt)
[x] All env values in .env (SUPABASE_URL, KEY, SERVICE_KEY, JWT_SECRET, JWT_ISSUER, DB_DSN)
[x] All migrations applied through 2026-05-19 (~70 migrations, see supabase/migrations/)
[x] RLS enforced on all user-data tables
[x] Auth: email/password + email confirmation REQUIRED
[x] Auth redirect URLs: sparrow://reset-password, sparrow://subscription
[ ] Apple OAuth provider — DEFERRED (email/password is sufficient for v1)
[ ] Google OAuth provider — DEFERRED (post-launch)

================================================================================
 3. EC2 / SERVER SETUP  ✅ DONE
================================================================================

[x] EC2: 51.21.210.195, t3.medium, eu-north-1, Elastic IP
[x] SSH: `ssh collectai` (key at ~/.ssh/collectai-ec2)
[x] systemd service: `collectai-bake.service` runs `bake_orchestrator.py`
    from `/opt/collectors/server/` (NOT `/opt/collectors/`)
[x] Bake preflight gates (6) wired into ExecStartPre
[x] nginx + Certbot for SSL on api.sparrowcollect.com (renewal verified)
[x] CORS_ORIGINS + TRUSTED_HOSTS updated for sparrowcollect.com
[x] Deploy: `scripts/deploy_to_ec2.sh` (rsyncs to `/opt/collectors/server/`)

================================================================================
 4. PRODUCTION .ENV FILE  ✅ DONE
================================================================================

[x] All required vars set in /opt/collectors/.env on EC2
[x] CORS_ORIGINS=https://sparrowcollect.com,https://www.sparrowcollect.com
[x] TRUSTED_HOSTS=api.sparrowcollect.com,sparrowcollect.com,www.sparrowcollect.com
[x] RATE_LIMIT_ENABLED=true, DEBUG=false, DB_SSL_ALLOW_SELF_SIGNED=0
[x] Sentry: backend + mobile DSNs in .env
[x] AWS S3: collectai-warehouse-prod-eu-north-1 (data lake, lifecycle rules)
[x] Marketplace API creds: eBay, TCGPlayer (closed), Cardmarket (restricted),
    PriceCharting (paid only). 9 unrestricted sources active.
[x] Paid-scraper kill switches: FIRECRAWL_ENABLED=false, SCRAPEDO_ENABLED=false
    (both quota-exhausted 2026-04-21; not blocking)

================================================================================
 5. PAYMENTS — RevenueCat (PRIMARY)  ⏳ DASHBOARD PENDING
================================================================================

> Stripe was the original plan but RevenueCat replaced it for iOS IAP on
> 2026-05-09 (commit `652230a`). Stripe code stays in `server/app/billing_router.py`
> for future web/Android billing; do NOT activate Stripe Live Mode for v1.

Code side ✅ DONE:
[x] `react-native-purchases` SDK installed + initialised in `src/lib/purchases.ts`
[x] PRO_ENTITLEMENT_ID = 'pro' (lowercase, must match RC dashboard)
[x] Subscription screen reads `offerings?.current?.monthly` and `.annual` (app/subscription.tsx:151)
[x] FE source of truth: RevenueCat customerInfo (BE billing endpoints vestigial)
[x] EXPO_PUBLIC_REVENUECAT_IOS_KEY plumbing via EAS env

Dashboard side ⏳ PENDING (user action — see PUBLIC_LAUNCH_CHECKLIST.md Phases 1-2):
[ ] revenuecat.com account + Sparrow project
[ ] ASC: create `sparrow_pro_monthly` (€4.99/mo) + `sparrow_pro_yearly` (€39.99/yr)
[ ] ASC: generate In-App Purchase Key (.p8) — Key ID + Issuer ID
[ ] RC: paste .p8 + Key ID + Issuer ID, copy public app-specific API key
[ ] `eas env:create` to push `EXPO_PUBLIC_REVENUECAT_IOS_KEY` to production env
[ ] RC: import products from App Store
[ ] RC: create `pro` entitlement, attach both products
[ ] RC: configure `default` offering with `$rc_monthly` + `$rc_annual` packages
[ ] ASC: create sandbox tester for purchase QA

================================================================================
 6. AWS SETUP  ✅ DONE
================================================================================

[x] IAM user `collectai-access` with S3 + EC2 access
[x] S3 buckets: collectai-artifacts (images), collectai-warehouse-prod-eu-north-1 (data lake)
[x] Data lake lifecycle: 180d → Glacier IR → 730d → Deep Archive (versioned, AES-256)
[x] DuckDB readback verified

================================================================================
 7. APPLE DEVELOPER + APP STORE CONNECT  ✅ DONE
================================================================================

[x] Apple Developer enrolment — Individual (NL eenmanszaak, KvK 99596326)
    paid + approved 2026-05-07
[x] App ID: io.sparrowcollect.app (com.sparrowcollect.* was rejected)
[x] App Store Connect record: App ID 6767359453, name "Sparrow Collect"
[x] eas.json submit creds: appleId, ascAppId, appleTeamId all filled
[x] Distribution cert + provisioning profile auto-managed by EAS (valid → 2027-05-12)
[ ] Sign In with Apple service ID + .p8 key — DEFERRED (v1 uses email/password)

================================================================================
 8. GOOGLE CLOUD / PLAY  ⏭️ DEFERRED
================================================================================

iOS-first launch. Play Console scaffolded in `android/fastlane/` for phase 2
(1-2 weeks post-iOS). Google OAuth client IDs not wired — email/password for v1.

Android readiness was assessed 2026-07-31: the app builds and runs, and what
remains is console setup (Play enrolment, RevenueCat Android key, FCM). Run
`npm run preflight:android` for live status — see `docs/ANDROID_LAUNCH.md`.

================================================================================
 9. SENTRY  ✅ DONE
================================================================================

[x] Sentry EU region account
[x] Two projects: collectai-backend (Python/FastAPI) + collectai-mobile (RN)
[x] DSNs in backend .env + EAS env vars
[x] EAS build hook for release tracking (commit `d327294`)
[x] GitHub Actions release workflow

================================================================================
 10. DEPLOY BACKEND  ✅ DONE
================================================================================

[x] systemd service running, ExecStartPre preflight gates enforced
[x] Health check: https://api.sparrowcollect.com/healthz returns {ok:true, db:up}
[x] Bake orchestrator supervises 17 in-process workers + 3 monitor loops
[x] CRAWL4AI_MAX_CONCURRENT=1, circuit breakers on all 44 adapters

================================================================================
 11. MOBILE APP — EAS ENV VARS  ✅ DONE
================================================================================

[x] EXPO_PUBLIC_API_BASE_URL=https://api.sparrowcollect.com (in EAS production)
[x] EXPO_PUBLIC_SUPABASE_URL + ANON_KEY (in EAS production)
[x] EXPO_PUBLIC_SUPABASE_MODE=strict (set per-profile in eas.json)
[x] EXPO_PUBLIC_BETA_UNLOCK_ALL — true on `production` profile, false on `store`
[x] EXPO_PUBLIC_REVENUECAT_IOS_KEY (sensitive, pending RC dashboard setup)
[x] SENTRY_DISABLE_AUTO_UPLOAD plumbed

================================================================================
 12. APP ASSETS  ✅ DONE
================================================================================

[x] App icon: assets/icon.png (1024x1024, Tiffany Blue gradient, no transparency)
[x] Splash + adaptive icon refreshed for Sparrow brand
[x] App Store screenshots: 6 compositions rendered via Remotion 5
    (collectai-admin/video/out/screenshots/, iPhone 16 Pro Max 1290x2796)
[x] Paywall screenshot: ~/Desktop/sparrow_paywall_1290x2796.png

================================================================================
 13. APP STORE METADATA  ✅ READY TO PASTE
================================================================================

All copy lives in **`docs/app-store-aso.md`**. Paste each section into the
matching ASC field per **`docs/PUBLIC_LAUNCH_CHECKLIST.md` Phase 5**.

================================================================================
 14. BUILD & SUBMIT  ⏳ IN-FLIGHT
================================================================================

[x] EAS CLI installed, logged in as collectai (slendebroekmerle@gmail.com)
[x] Build #3 (buildNumber 9, ID 6ea51914) uploaded to ASC 2026-05-12
[~] Build #13 (auto-incremented from #12) — BUILDING on EAS 2026-05-19,
    track at https://expo.dev/accounts/collectai/projects/collectai/builds/
[x] Submit profile `store` added to eas.json 2026-05-19 (mirrors `production`)
[ ] App Store submission — pending RevenueCat dashboard + ASC metadata

================================================================================
 15. POST-LAUNCH
================================================================================

[x] Sentry monitoring live (backend + mobile)
[x] PostHog analytics (31+ events) wired
[x] CI workflows: ci-min, Sanity, Sanity E2E, Nightly Training, Nightly Eval
    (Nightly Sanity fixed 2026-05-09 after 16-day silent fail, commit `cfd32c1`)
[ ] Pre-launch bake manifest cut to 10 workers (2026-05-04). Re-enable disabled
    workers in 5 waves post-launch — see Pre-Launch Bake Posture above.
[x] Spend Monitor: €150/mo budget cap, Telegram alerts at 75/90/100%
[ ] Apply for eBay Marketplace Insights API (sold-comps data; Finding API
    revoked 2026-04-26)

================================================================================
 END OF CHECKLIST — see docs/PUBLIC_LAUNCH_CHECKLIST.md for active launch path
================================================================================
