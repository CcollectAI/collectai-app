# Sparrow Collect Monetization Strategy

> Last refreshed 2026-05-19. Renamed from CollectAI 2026-05-04. **iOS IAP via RevenueCat replaced Stripe on 2026-05-09** (commit `652230a`); Stripe code path is preserved for future web/Android billing.

## 1. Current System — RevenueCat IAP (PRIMARY, SHIPPED 2026-05-09)

Two-tier model (was three-tier on Stripe; Premium folded into Pro).

### Resolved 2026-07-31 — free gets 0 mandates, not 3

The table used to say Free = **3** purchase mandates while `deal_discovery` was
`No`, and the backend implemented exactly that. The result was 3 mandates a free
user could never reach: the Home entry point sends them to the paywall
(`limits.deal_discovery ? "/purchase" : "/subscription"`), the discovery worker
skips free users' mandates entirely, and `GET /purchase/deals/{id}` is
`require_plan("pro")`. A mandate without discovery cannot produce a deal, so
those 3 were inert even if reached by deep link — and `/purchase/*` **is** a
Universal Link path, so they were reachable.

Resolved by making the entitlement match the feature:
`PLAN_LIMITS["free"]["max_mandates"] = 0`. The existing limit check
(`purchase_router.py`, `count >= mandate_limit`) now rejects free users at the
API, which closes the deep-link bypass without needing the screens to self-gate.
A 0 limit returns **403 `PLAN_REQUIRED`** with "The Smart Deal Agent is a Pro
feature." rather than the nonsensical "Mandate limit reached (0)".

Verified against prod after deploy: a free user creating a mandate gets that 403.

If the intent were ever the opposite — free users setting up mandates that
activate on upgrade — the change is to set `max_mandates` back and open the
screen with discovery disabled, **not** to leave the two sides disagreeing.

**They disagreed anyway, for two and a half weeks (found 2026-08-16).** The
server went to 0 on 2026-07-31; `DEFAULT_LIMITS` in `useBillingLimits.ts` kept
saying **3**. Two things follow, and both are worth more than the fix:

1. **This table was correct the whole time. The code drifted, not the doc.**
   The paywall copy written on 2026-08-16 said "3 purchase mandates" because it
   was written from the client table instead of from here — so a screen that
   takes money advertised a feature the buyer gets none of.
2. **`check:billing-limits-parity` could not see it.** It compared FE/BE values
   for `pro` and `premium` only — free was deliberately out of scope — and only
   for keys the FE reads as `limits.X`. `max_mandates` is neither, so the gate
   passed every day of those weeks.

Both holes are closed: the gate now compares **free** as well and checks **every
numeric cap both tables declare**, and `__tests__/screens/subscriptionPlanCards.test.ts`
pins the plan-card copy to the limits, so a card can no longer name a number
that no plan grants.

**The server tests were the last thing still saying 3 (fixed 2026-08-19).**
`test_billing_router.py::TestPlanLimits::test_free_limits` and
`test_subscription.py::TestGetUserMandateLimit` both asserted `max_mandates == 3`
and had been red since the change — and `test_pro_limits` asserted
`advanced_analytics is False`, the pre-2026-07-28 three-tier value. A red test is
not automatically a bug in the code: making those three pass by editing
`PLAN_LIMITS` would have reopened the deep-link bypass this section exists to
describe, and re-broken analytics for paying users on the RevenueCat fallback
path. They now pin **0** and **True**, each with the reason inline, and each was
mutation-tested (put the old value back → red). The old name
`test_free_user_gets_3` encoded the number, which is exactly why it survived the
change looking plausible; it is `test_free_user_gets_0`.

### Plans

| | Free | Pro (€4.99/mo or €39.99/yr) |
|--|------|-----------------------------|
| **Watchlist items** | **25** | **Unlimited** |
| **Target Hit alerts** | **1 / day** | **Unlimited** |
| Purchase mandates | 0 | 10 |
| Deal discovery | No | Yes |
| Dossier PDF export | No | Yes |
| Condition Grading (item card) | No | Yes |
| Set Completion — **trading-card sets only**, see note | No | Yes |
| Advanced analytics (price trend, history, market prices) | No | Yes |
| Basic valuation | Yes | Yes |
| Community events | Yes | Yes |
| Ads | Yes | No |

> **Watchlist slots are the Target Hit lever (added 2026-08-06).** The alert
> can only fire on something you are watching, so slots ARE reach — that is why
> the paid tier gates them rather than gating the notification itself.
> `max_watchlist_items` (25 / None) and `max_daily_deal_alerts` (1 / None) live
> in `PLAN_LIMITS` (billing_router.py), are mirrored in `DEFAULT_LIMITS` +
> `FORCED_LIMITS` (useBillingLimits.ts) and in the `BillingStatus['limits']`
> type (src/api/types.ts). All three must agree — see
> `learning_billing_limits_fe_be_contract`. The watchlist cap is enforced
> server-side in `watchlist_router.add_to_watchlist` (403 `PLAN_LIMIT_WATCHLIST`),
> not only in the client; the alert cap is read from the same table by
> `deal_discovery_worker`, which no longer declares its own constants.
>
> **Two of these are easy to misread — verified 2026-07-29:**
>
> * **Purchase mandates** is **10**, not unlimited. Both
>   `PLAN_LIMITS["pro"]["max_mandates"]` (billing_router.py) and
>   `FORCED_LIMITS.pro` (useBillingLimits.ts) say 10; only this table said
>   "Unlimited". Corrected here rather than in code — raise both if you want it
>   to be truly unlimited.
> * **Set Completion is trading-card only, and there are TWO implementations
>   (measured 2026-08-19).** `category_items.set_name` coverage is 71-100%
>   across the six TCG categories and **0.0% — zero rows — in all 50 others**,
>   and every non-TCG catalogue row is `source='seed'` (no importer has ever
>   run for them). So completion is not computable outside trading cards, and
>   the paywall/store copy now says so.
>
>   The two implementations do not share a source, which is why this looked
>   fine for so long:
>
>   | surface | source | reality on prod |
>   |---|---|---|
>   | Home `AutoSetProgressList` | `GET /sets/auto-progress` — catalogue-derived, `attrs.set_name` vs `category_items` | works for TCG; needs 2+ owned from one set |
>   | **The PAID screen** `app/sets-to-complete.tsx` | `GET /portfolio/items` → `sets.total_items` joined on `collection_name` | `sets` holds **3 hand-seeded Pokemon rows**; `set_items` and `set_registry` are empty |
>
>   So the screen a user pays for is backed by three seeded sets, while the
>   free Home rail uses the catalogue. Repointing the paid screen at
>   `/sets/auto-progress` would collapse them to one implementation and is the
>   obvious next step — it changes what a paid screen shows, so it is a
>   deliberate decision, not a refactor.
>
> * The original note, kept because its mechanism is still correct:
>   **Set Completion works**, despite `sets`, `set_items` and `set_registry`
>   being effectively EMPTY. It is served by `GET /sets/auto-progress`, which computes
>   completion from `items.attrs->>'set_name'` against
>   `category_items.attributes_json->>'set_name'` (165,243 catalog rows carry
>   one) — it never reads those tables. Verified end to end: an account with 2
>   items tagged "Quarter Century Stampede" returns
>   `owned_count 2 / catalog_total 989`.
>
>   The empty tables belong to a separate legacy manual-registry path (`GET
>   /sets`, which does return empty). The only thing genuinely dead there is
>   the **Set Completion ALERT**, which `price_monitor_worker` drives off
>   `set_registry` — and that worker is disabled pre-launch anyway.

### RevenueCat ↔ FE contract

- Entitlement identifier: **`pro`** (lowercase) — must match `PRO_ENTITLEMENT_ID` in `src/lib/purchases.ts:5`.
- Offering: **`default`** with packages `$rc_monthly` (linked to `sparrow_pro_monthly`) and `$rc_annual` (linked to `sparrow_pro_yearly`). `app/subscription.tsx:151` reads these exact identifiers — other names produce a "Coming soon" UI.
- **FE source of truth: `Purchases.getCustomerInfo()`** from `react-native-purchases`. Backend `/billing/status` endpoint is vestigial for iOS — kept for future web/Android.
- Beta override: `EXPO_PUBLIC_BETA_UNLOCK_ALL=true` (set on `production` build profile) bypasses RC entirely for TestFlight testing. The `store` build profile sets it `false` for App Store submission.

### Verified live state (2026-08-15) — measured, not assumed

Probed with the real production RC key against the RevenueCat API, and by
unzipping the shipped `.ipa` and reading the Hermes bundle:

| Thing | How it was checked | Result |
|---|---|---|
| RC offering + packages | `GET /v1/subscribers/<probe>/offerings` with the live `appl_…` key | ✅ `current_offering_id: default`; `$rc_monthly` → `sparrow_pro_monthly`, `$rc_annual` → `sparrow_pro_yearly` |
| RC key reaches the binary | `grep appl_ main.jsbundle` in `builds/sparrow-ios-internal.ipa` and `build116.ipa` | ✅ inlined in both |
| EAS env plumbing | `eas env:list --environment production` | ✅ key lives in the `production` environment; profiles with no `environment` field still resolve it (EAS auto-assigns) |
| Beta unlock flag | same bundle grep | ❌ **was broken — see below** |
| ASC product state | **checkable — see `docs/ASC_API_KEY.md`** | ✅ 2026-08-23: both products `READY_TO_SUBMIT`, prices in every territory, `en-US` localization, review screenshot uploaded, 175 territories |
| Paid Apps agreement | **not exposed by any ASC endpoint** | ⬜ needs a human on `appstoreconnect.apple.com/business` — this half really is unqueryable |

**So the "IAP doesn't work" symptom is NOT a RevenueCat misconfiguration.** RC and
the app binary are both correct. What remains can only fail on Apple's side or on
the test setup — see "If the paywall shows no products" below.

#### The env-inlining trap (fixed 2026-08-15)

`useBillingLimits.ts` read the flag as
`(typeof process !== 'undefined' && (process as {...}).env?.EXPO_PUBLIC_BETA_UNLOCK_ALL)`.
Expo's babel plugin only replaces the **exact** `process.env.EXPO_PUBLIC_X`
member expression with a literal; a guarded/optional-chained read compiles to a
runtime lookup on `process.env`, which is empty in a release bundle. The flag
read `''` in every built app — **beta unlock never turned on, so paid features
stayed gated on TestFlight** while `eas.json` looked correct.

The tell is in the binary: an inlined var's *name* is absent from the bundle;
a runtime lookup leaves the name in the Hermes string table.

```bash
unzip -p builds/<app>.ipa 'Payload/*/main.jsbundle' | strings | grep EXPO_PUBLIC_
# anything printed here is read at runtime => undefined on device
```

Gated by `npm run check:env-inlining` (in `verify:prebuild`). Proven to fail on
the bad shape before being wired in.

#### "Coming soon" on the subscription screen — what it actually means

Reported on build 137 (TestFlight, 2026-08-15). That copy is the
`iapUnavailable` branch of `app/subscription.tsx`, and until 2026-08-15 **two
unrelated failures rendered it identically**, so it could not be triaged without
a rebuild. Both now log a distinguishing line via `logger.error` (info/warn are
stripped in release):

| log line | meaning | whose problem |
|---|---|---|
| `reason=no-key` | no RevenueCat key in this build at all | **the build**: normal on a dev-client, wrong on a store build |
| `reason=configure-failed` | a key IS present and `Purchases.configure()` threw | **ours** |
| `reason=no-offering` | RC configured, but `getOfferings()` returned no `current` | **Apple's**: StoreKit handed the SDK no products |

### The diagnostic itself was wrong until 2026-08-17 — read this before triaging

`isPurchasesAvailable()` is a BOOLEAN, and the screen turned every `false` into
the single line *"reason=no-key — EXPO_PUBLIC_REVENUECAT_IOS_KEY missing from
this build"*. That sentence is an assertion about the build, and it was emitted
in a case where it is simply untrue: when the key is present and
`Purchases.configure()` throws, `configured` stayed false and the screen blamed
a missing env var. **A wrong diagnostic is worse than none, because it is
believed.**

`src/lib/purchases.ts` now exports `purchasesStatus(): 'ready' | 'no-key' |
'configure-failed'` and the screen branches on it.
`__tests__/lib/purchasesStatus.test.ts` pins all three and also asserts the
screen does not go back to reading the boolean.

**And the answer to "plans couldn't load", asked across several sessions, was
none of the Apple items below.** The app under test was the **dev-client build
on the Simulator**. The `development` profile in `eas.json` sets only
`EXPO_PUBLIC_SUPABASE_MODE` — it carries **no RevenueCat key** — so
`initPurchases()` returns early and the paywall renders its unavailable state.
It cannot work on that build no matter what App Store Connect is configured to
do, and StoreKit serves no products on the Simulator either way. Two independent
reasons, neither fixable in code.

Verified for build 141 (2026-08-16), so these are NOT open questions:

| checked | how | result |
|---|---|---|
| key reaches the binary | `strings main.jsbundle \| grep appl_` on the shipped IPA | ✅ `appl_tfjQ…` inlined |
| RC serves the offering | `GET /v1/subscribers/<probe>/offerings` with that key | ✅ `default`, `$rc_monthly` → `sparrow_pro_monthly`, `$rc_annual` → `sparrow_pro_yearly` |
| the store profile locks the flag | build log | ✅ `EXPO_PUBLIC_BETA_UNLOCK_ALL=false` overrides the EAS production `true` |

**To actually test IAP: install build 141+ from TestFlight on a physical
device.** Anything observed on the Simulator or a dev build is not evidence.

For build 137 it can only be `no-offering`: the `appl_…` key is provably inlined
in that binary and the RC dashboard serves a `default` offering with both
packages. **The RevenueCat side is not the problem.** The SDK drops an offering
whose packages resolve to no StoreKit product, which happens when:

### The `reason=` line is now readable without a cable (2026-08-21)

The three-way diagnostic above was built to end this triage, and for six days
it could not be read on the device it describes. `logger.error` wrote to
`console.error` and **nowhere else**. Two independent gaps:

- **Sentry was initialised the whole time and never received a log line.**
  `app/_layout.tsx` has configured Sentry since 2026-05-12; nothing forwarded
  `logger.error` into it.
- **`getRecentLogs()` had no consumer.** `src/lib/logger.ts` retains every
  level in a 300-entry ring buffer and its own comment says the buffer is
  *"readable via getRecentLogs() from the diagnostics screen"*. Repo-wide,
  `getRecentLogs` appeared only in comments, tests and test mocks. There was no
  diagnostics screen. Captured, correct, reachable from nowhere — the same
  shape as the five features fixed on 2026-08-20.

So the answer to "which of the three reasons is it?" required plugging the
phone into a Mac and opening Console.app, which is why the question survived
several sessions.

Both closed:

| route | how | needs |
|---|---|---|
| **Settings → Diagnostics** (`app/diagnostics.tsx`) | reads `getRecentLogs()`, newest first, errors-only by default, with a Share action | nothing — works offline, which matters when the network is what is broken |
| **Sentry** | `setLogSink()` in `app/_layout.tsx` forwards `error` as an event and `warn` as a breadcrumb | a DSN and a network |

`setLogSink` is **injected, not imported**: `logger.ts` must not depend on
Sentry — it is the one module that has to keep working when everything else is
misbehaving.

⚠️ **The forwarder is re-entrant by construction and needs its latch.** Sentry's
`beforeSend` *and* `beforeBreadcrumb` hooks both call `logger.error(...)` from
their own catch blocks, so log → sink → Sentry → hook throws → `logger.error` →
sink → … recurses until the stack blows. `notifySink`'s `inSink` latch stops
it. `__tests__/lib/loggerSink.test.ts` pins that, and it was **proven by
removing the latch and watching the test fail** with a blown stack — without
which the diagnostic channel becomes the crash it was added to report, on
exactly the builds where something is already wrong.

Log text goes through `beforeSend` / `beforeBreadcrumb`, so the existing PII
scrub applies to it exactly as it does to exceptions — a new source of strings,
not a new way to leak them.

### Verified live for build 149 (2026-08-21) — do not re-litigate the RC side

| checked | how | result |
|---|---|---|
| key reaches the binary | `strings main.jsbundle \| grep appl_` on the shipped IPA | ✅ `appl_tfjQ…`, 32 chars |
| RC serves the offering | `GET /v1/subscribers/<probe>/offerings` with that key | ✅ `current_offering_id: default` |
| package → product | same response | ✅ `$rc_monthly → sparrow_pro_monthly`, `$rc_annual → sparrow_pro_yearly` |
| paywall actually live | build job env | ✅ `store` profile pinned `EXPO_PUBLIC_BETA_UNLOCK_ALL=false` |

Reported on build 149, TestFlight, **physical device**: "Subscriptions Coming
Soon". `no-key` is excluded by the binary and RC misconfiguration by the API
probe, and a device excludes the Simulator — so it is `no-offering`, and the
remaining causes are the Apple-side items below.

**One correction to that list:** the missing RC↔Apple In-App Purchase `.p8`
(item 5) **cannot** cause this. It gates granting the `pro` entitlement *after*
a purchase completes; it never suppresses product listing. Still an open gap,
just not this one.

⚠️ **CORRECTED 2026-08-23 — this paragraph was wrong, and it cost sessions.**
It used to read *"ASC remains unqueryable from here… its Issuer ID is recorded
nowhere, so items 2 and 3 still need a human in the ASC UI."* That was true of
the ONE key it looked at (`AuthKey_LAU7D8HU29.p8`) and false of the account: key
`AM32RK7DAY` has its issuer stored in **EAS**, and `~/Documents/Sparrow/Keys/`
holds the `.p8`. See `docs/ASC_API_KEY.md`. **"I could not find it" was written
down as "it does not exist"** — enumerate before declaring a capability
unavailable ([[feedback_enumerate_before_declaring_unavailable]]).

What the API genuinely cannot answer is the **agreement** itself; no endpoint
returns it. That half still needs a human on the Business page.

**And this doc's inference about the products was VERIFIED FALSE.** It concluded
from the submit modal that the subscriptions were *"still missing price, a
localization, or the review screenshot"*. Measured 2026-08-23: both carry prices
in every territory, an `en-US` localization, an uploaded review screenshot and
175-territory availability. The modal's complaints are about the **app version**
(`1.0`, `build: null` — no binary attached) and about a draft review submission
holding only the subscription GROUP version, not the two products. A modal that
names no field is not evidence about which field is missing.

### ANSWERED 2026-08-21: there is no Paid Applications Agreement

Screenshotted from ASC → Business. The Agreements table contains exactly one
row:

| type | countries | effective | status |
|---|---|---|---|
| **Free Apps Agreement** | All | 9 jul 2026 – 7 mei 2027 | Active (New Agreement Available) |

**There is no Paid Applications row at all** — it has never been requested, so
it is not "pending", it does not exist. Until it does, StoreKit returns **zero
products in every environment**, sandbox and TestFlight included. That is the
whole of `reason=no-offering`, and it is why every RC-side check kept coming
back healthy: RevenueCat was right, the binary was right, and Apple had nothing
to sell.

This closes the question the doc had been carrying as *"not checkable from
here"* since 2026-08-15. It was never an API question — the ASC API does not
expose agreements at all — it was a screenshot.

**Two other things are visible on the same page and both matter:**

- ⚠️ **The Apple Developer Program License Agreement has been updated and is
  unaccepted.** Apple's banner: *"In order to update your existing apps and
  submit new apps, the Account Holder must review and accept the updated
  agreement."* This gates app submission, and Apple generally will not let you
  start a new agreement while it is outstanding — **accept it first**.
- **Digital Services Act compliance is `In Review`** (27 countries). EU trader
  status; it gates EU distribution, not IAP.

### The subscriptions cannot be submitted yet either (same day)

The Draft Submission modal refuses with:

> **Unable to Submit for Review**
> - New subscription groups must be submitted with an auto-renewable
>   subscription from within that group.
> - To submit your items for review, add an app version for the selected
>   platform.

and lists only **"Pro — Subscription Group"** under *Item Ready to Submit*.

Read that carefully: the GROUP is ready, and **no subscription inside it is**.
`sparrow_pro_monthly` and `sparrow_pro_yearly` exist (RevenueCat resolves both
product ids), so they are present but not in a submittable state — i.e. still
missing price, a localization, or the review screenshot. So item 3 of the list
below is ALSO true, independently of the agreement.

**Order matters, and it is not the order in the list below:**

1. Accept the updated **Developer Program License Agreement** (account holder).
2. Request the **Paid Applications Agreement** and complete contact, **bank
   account** and **tax forms** (individual, not company — the account is
   registered to a person at an Amsterdam address). Apple verifies the bank
   account, so this is the step with a **multi-day tail**.
3. Take both subscriptions out of Missing Metadata, then add **a subscription**
   (not just the group) plus **an app version** to the draft submission.

Nothing in the app changes. There is no code fix for any of this, which is
exactly what the three-way diagnostic was built to tell us — and what six days
of chasing RevenueCat could not.

#### If the paywall shows no products

In order of likelihood, none of which the code can fix:

1. **Testing on the iOS Simulator.** StoreKit returns no products there, so
   `getOfferings()` yields an offering with zero `availablePackages` and
   `app/subscription.tsx` renders its unavailable state. IAP must be tested on a
   physical device via TestFlight.
2. **Paid Applications Agreement not signed** (ASC → Business). Until it is
   active, StoreKit returns no products anywhere, sandbox included.
3. **Subscriptions not in a purchasable state** — each needs price, a
   localization, and a review screenshot before it leaves *Missing Metadata*.
4. **No sandbox tester signed in** on the device (Settings → App Store → Sandbox
   Account), or signed in with a real Apple ID.
5. **RC ↔ Apple server credential missing** — the In-App Purchase `.p8` (or app
   shared secret) in RC → Apps → iOS. Without it a purchase can complete at
   StoreKit and still not grant the `pro` entitlement, because RC cannot verify
   the transaction. `docs/ASC_API_KEY.md` records this key as never created;
   confirm in the RC dashboard before believing it.

### What's Built

| Component | File(s) | Status |
|-----------|---------|--------|
| `react-native-purchases` SDK + init | `src/lib/purchases.ts` | Done |
| Plan selection + restore flow | `app/subscription.tsx` | Done |
| Entitlement gating hook | `src/hooks/useBillingLimits.ts` | Done |
| Beta-unlock flag override | `EXPO_PUBLIC_BETA_UNLOCK_ALL` (eas.json) | Done |
| EAS env var plumbing | `EXPO_PUBLIC_REVENUECAT_IOS_KEY` | Done |
| EAS env var plumbing (Android) | `EXPO_PUBLIC_REVENUECAT_ANDROID_KEY` | **NOT SET — Android cannot sell** |
| Stripe Checkout + Portal + Webhook (dormant) | `server/app/billing_router.py` | Done, NOT wired for iOS |

### To Activate (dashboard side — see `docs/PUBLIC_LAUNCH_CHECKLIST.md` Phases 1–2)

1. **ASC** → Monetization → Subscriptions → create `sparrow_pro_monthly` (€4.99/mo) and `sparrow_pro_yearly` (€39.99/yr) in a `Pro` group.
2. **ASC** → Users and Access → Integrations → In-App Purchase Keys → generate `.p8`. Note Key ID + Issuer ID.
3. **revenuecat.com** → Apps → Add iOS app `io.sparrowcollect.app` → upload `.p8` + Key ID + Issuer ID.
4. **EAS** → `eas env:create --environment production --name EXPO_PUBLIC_REVENUECAT_IOS_KEY --value 'appl_...' --visibility sensitive`.
5. **RC** → Product catalog → import products, create `pro` entitlement, configure `default` offering with `$rc_monthly` + `$rc_annual`.

### To Activate on Android (verified missing 2026-07-31)

`src/lib/purchases.ts` picks the key by platform, so the iOS key does nothing on
Android. With `EXPO_PUBLIC_REVENUECAT_ANDROID_KEY` unset, `initPurchases()`
returns early and `app/subscription.tsx` renders its `iapUnavailable` state —
**an Android build ships with no way to take money, and nothing fails loudly.**
`scripts/preflight_android.mjs` now checks for this key.

1. **Play Console** → Monetize → Products → Subscriptions → create
   `sparrow_pro_monthly` (€4.99/mo) and `sparrow_pro_yearly` (€39.99/yr). Use the
   **same product identifiers as iOS** so one RevenueCat `default` offering
   serves both — `app/subscription.tsx:151` reads `$rc_monthly` / `$rc_annual`
   by exactly those names.
2. **Play Console** → Setup → API access → link a GCP project and create the
   publishing service account (`bash scripts/setup_play_store.sh` walks this).
3. **revenuecat.com** → Apps → Add app → Google Play → package
   `io.sparrowcollect.app`, upload that same service-account JSON.
4. **EAS** → `eas env:create --environment production --name EXPO_PUBLIC_REVENUECAT_ANDROID_KEY --value 'goog_...' --visibility sensitive`.
5. Re-run `npm run preflight:android` — it must exit 0.

The `pro` entitlement and `default` offering from the iOS setup are shared; you
are adding a second store to the same entitlement, not building a second one.

## 2. Stripe (DORMANT — kept for future web/Android)

Three-tier code path (Free / Pro €4.99 / Premium €9.99) remains in `server/app/billing_router.py` with 25 passing tests. **Do NOT activate Stripe Live Mode for v1 iOS submission** — it duplicates RevenueCat and complicates compliance review. Revisit when:

- Building a web sign-up flow (`web/` Vercel site has no payments today).
- Submitting Android version (Google Play allows external billing in some markets but Stripe is simpler than Play Billing for our scale).

To re-activate later, set these env vars on EC2 `.env`:

```
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_PRO=price_...
STRIPE_PRICE_ID_PREMIUM=price_...
```

The Premium tier was deprecated when the model collapsed to Free + Pro — Pro now includes advanced analytics that Premium previously gated.

---

## 2. Affiliate Revenue (PARTIALLY BUILT)

Earn commission when users purchase collectibles through links in the app.

### What's Already Built

| Component | File | Status |
|-----------|------|--------|
| Affiliate URL builder | `app/lib/affiliate.py` | Done |
| eBay Partner Network tagging | `affiliate.py` (`_tag_ebay`) | Done |
| TCGPlayer affiliate tagging | `affiliate.py` (`_tag_tcgplayer`) | Done |
| Cardmarket affiliate tagging | `affiliate.py` (`_tag_cardmarket`) | Done |
| Deal discovery wiring | `deal_discovery_agent.py` line 134 | Done |
| Click tracking (`affiliate_click`) | `mandate_deals` table | Done |
| Commission tracking (`estimated_commission`) | `mandate_deals` table | Done |
| Affiliate URL in deal response | `purchase_router.py` (`DealResponse`) | Done |
| 8 affiliate builder tests | `test_affiliate.py` | Done |
| Config vars in `config.py` | `EBAY_AFFILIATE_CAMPAIGN_ID`, etc. | Done |

### How It Works Today

1. Deal discovery agent finds a listing on eBay/TCGPlayer/Cardmarket
2. `build_affiliate_url()` appends partner tracking params to the URL
3. Deal is stored with both `listing_url` (original) and `affiliate_url` (tagged)
4. When user taps "View Deal", `POST /purchase/deals/{id}/click` sets `affiliate_click=true`
5. User is sent to the `affiliate_url`, marketplace tracks the referral
6. Commission is earned if the user purchases

### To Activate

Set affiliate program credentials:

```
EBAY_AFFILIATE_CAMPAIGN_ID=        # Apply at https://partnernetwork.ebay.com
TCGPLAYER_AFFILIATE_ID=            # Apply at https://tcgplayer.com/affiliates
CARDMARKET_AFFILIATE_ID=           # Apply at https://cardmarket.com/affiliate
```

### Revenue Estimate

| Marketplace | Commission Rate | Avg Order | Est. Revenue/Click |
|------------|----------------|-----------|-------------------|
| eBay (EPN) | 1-6% (category dependent) | EUR 25 | EUR 0.50-1.50 |
| TCGPlayer | 5% | EUR 15 | EUR 0.75 |
| Cardmarket | 3-5% | EUR 12 | EUR 0.36-0.60 |

### Affiliate Links for ALL Users (BUILT)

Affiliate links now appear across the entire app for all users (including free tier):

**A. Affiliate links on item detail pages** — BUILT

"Shop this Item" section on `app/item/[id].tsx` with marketplace buttons (eBay + TCGPlayer + Cardmarket for TCG categories). Uses `GET /marketplace/affiliate-links` endpoint.

**B. Affiliate links in price evidence** — BUILT

PriceExplanationSheet source names are now tappable — opens matching marketplace with affiliate tag. Accent-colored text with ↗ indicator.

**C. Affiliate links in barcode scan results** — BUILT

After scanning a barcode, a "Find on eBay" link appears below the Save/Watchlist buttons. Uses the same `GET /marketplace/affiliate-links` endpoint.

| Component | File | Status |
|-----------|------|--------|
| Affiliate links endpoint | `affiliate_links_router.py` | Done |
| Item detail "Shop this Item" | `app/item/[id].tsx` | Done |
| Barcode scan marketplace link | `app/barcode-scan.tsx` | Done |
| PriceExplanationSheet tappable sources | `PriceExplanationSheet.tsx` | Done |
| API client `getAffiliateLinks()` | `collectorsApi.ts` | Done |
| 6 tests | `test_affiliate_links_router.py` | Done |

---

## 3. Sponsored Events (BUILT)

Let brands, retailers, and event organizers pay to promote events to CollectAI users.

### Tiers

| Tier | Price | What They Get |
|------|-------|--------------|
| Basic Listing | Free | Standard event listing (what exists today) |
| Featured Event | EUR 29/event | Highlighted card, "Sponsored" badge, top of feed |
| Promoted Event | EUR 79/event | Featured + push notification to category followers |
| Spotlight Package | EUR 199/event | Promoted + brand logo + analytics dashboard |

### What's Built

| Component | File | Status |
|-----------|------|--------|
| DB migration (sponsor columns + analytics table) | `20260219_sponsored_events.sql` | Done |
| Sponsor checkout endpoint | `sponsor_router.py` | Done |
| Webhook handler for sponsor payments | `billing_router.py` | Done |
| Sponsored events sort boost | `events_router.py` | Done |
| Expired sponsor filtering | `events_router.py` | Done |
| Push notifications (promoted/spotlight) | `billing_router.py` → `push.py` | Done |
| Admin sponsor analytics | `admin_dashboard.py` | Done |
| Frontend sponsor type fields | `events.ts` | Done |
| Sponsored event cards (badge + styling) | `events.tsx` | Done |
| Config (3 Stripe price IDs) | `config.py` + `.env.example` | Done |
| ~10 tests | `test_sponsor_router.py` | Done |

### To Activate

Set 3 env vars (create one-time payment products in Stripe Dashboard):

```
STRIPE_PRICE_ID_SPONSOR_FEATURED=price_...
STRIPE_PRICE_ID_SPONSOR_PROMOTED=price_...
STRIPE_PRICE_ID_SPONSOR_SPOTLIGHT=price_...
```

### Revenue Estimate

| Scenario | Monthly Events | Avg Price | Monthly Revenue |
|----------|---------------|-----------|----------------|
| Conservative (launch) | 10 featured | EUR 25 | EUR 250 |
| Growth (6 months) | 30 featured + 10 promoted | EUR 50 avg | EUR 2,000 |
| Mature (12+ months) | 50 featured + 20 promoted + 5 spotlight | EUR 75 avg | EUR 6,250 |

---

## 4. Additional Free-Tier Monetization Ideas (PROPOSED)

### A. Marketplace Referral Fees

When users list items for sale through CollectAI (future P2P marketplace / Deal Desk),
take a small transaction fee.

| Model | Rate | When |
|-------|------|------|
| Listing fee | EUR 0.50/listing | User lists an item for sale |
| Success fee | 5% of sale price | Item sells through the platform |
| Highlight fee | EUR 1.00 | Boost listing visibility for 7 days |

**Prerequisites:** Deal Desk P2P system (planned but not built yet)
**Effort:** Depends on Deal Desk — the fee layer itself is ~1 day on top

### B. Premium Insights (Freemium Upsell)

Show free users a teaser of premium data to drive upgrades:

- Free: "Your Charizard Base Set is worth approximately EUR 150-300"
- Pro: "EUR 187.50 (q50) with 83% confidence, trending +12% over 90 days"
- The valuation always shows, but the confidence interval, trend, and evidence
  are blurred/locked behind Pro

This is a UX change, not a new revenue stream — but it drives subscription conversions.

**Effort:** ~1 day (frontend blur + "Upgrade to see full valuation" CTA)

### C. Data Licensing (Future)

As the data moat grows (supply snapshots, demand signals, verified sales, price history),
aggregate anonymized market intelligence becomes valuable to:

- Insurance companies (collectibles valuation for policies)
- Auction houses (market trend reports)
- Marketplace platforms (category pricing benchmarks)
- Academic researchers (alternative asset class analysis)

**Model:** API access subscription, EUR 500-5,000/month depending on data scope
**Prerequisites:** Significant data volume (~100K+ verified sales, 1M+ price observations)
**Effort:** ~1 week (API gateway + usage metering + anonymization layer)

---

## 5. Revenue Model Summary

| Stream | Free Users | Pro Users | Status |
|--------|-----------|-----------|--------|
| Subscriptions | — | EUR 4.99/mo or EUR 39.99/yr (Pro) | Built |
| Affiliate (deal agent) | — | Passive per click | Built |
| Affiliate (item pages) | Passive per click | Passive per click | Built |
| Affiliate (barcode scan) | Passive per click | Passive per click | Built |
| Affiliate (price evidence) | Passive per click | Passive per click | Built |
| Sponsored events | Sees sponsored events | Sees sponsored events | Built |
| Marketplace referral fees | Per transaction | Per transaction | Future |
| Premium insights upsell | Drives conversions | N/A (already paying) | Proposed |
| Data licensing | — | — | Future |

### Projected Monthly Revenue (at 10,000 MAU)

| Stream | Conservative | Optimistic |
|--------|-------------|-----------|
| Subscriptions (5% conversion) | EUR 2,500 | EUR 5,000 |
| Affiliate clicks (200/day) | EUR 1,500 | EUR 4,500 |
| Sponsored events | EUR 250 | EUR 2,000 |
| **Total** | **EUR 4,250** | **EUR 11,500** |

---

## 6. Implementation Priority

| Priority | Item | Effort | Revenue Impact |
|----------|------|--------|---------------|
| ~~P0~~ | ~~Activate Stripe (set env vars)~~ | ~~30 min~~ | ~~Enables subscriptions~~ — **SUPERSEDED**: subscriptions ship via RevenueCat IAP (Free + Pro), not Stripe. Stripe is dormant/web-only. |
| P0 | Apply for eBay Partner Network | 1 hour | Enables affiliate revenue |
| ~~P1~~ | ~~Affiliate links on item detail pages~~ | ~~1 day~~ | ~~Free-tier monetization~~ | **DONE** |
| ~~P1~~ | ~~Affiliate links in barcode scan results~~ | ~~0.5 day~~ | ~~Free-tier monetization~~ | **DONE** |
| ~~P2~~ | ~~Sponsored events system~~ | ~~3 days~~ | ~~New B2B revenue stream~~ | **DONE** |
| P2 | Premium insights upsell (blurred data) | 1 day | Drives Pro conversions |
| ~~P3~~ | ~~Affiliate links in price evidence~~ | ~~0.5 day~~ | ~~Incremental~~ | **DONE** |
| P3 | Apply for TCGPlayer + Cardmarket affiliates | 1 hour | More affiliate sources |
| P4 | Marketplace referral fees | Depends on Deal Desk | Future |
| P4 | Data licensing API | 1 week | Future (needs data scale) |

---

## 7a. CORRECTION — most of §7 does not earn money (2026-08-08)

Merle's response to the list below: *"these are not good monetization ideas.
nothing earns us money."* He is right, and the critique is worth keeping next to
the list so it is read with it.

Scoring §7 honestly by **direct cash**:

| § | Idea | Actually earns? |
|---|---|---|
| 1 | List an item, earn Pro time | **NO — it COSTS money.** Gives subscription away. It is a growth tactic wearing a monetization hat |
| 2 | Sold comps as a data product | No. A bet that Pro converts better |
| 3 | Seller pricing intelligence | No. Same bet |
| 4 | First-look alert latency | No. Same bet |
| 5 | Affiliate | **YES — direct cash per click** |
| 6 | B2B market reports | Yes, but there is no buyer today and it needs sales effort |
| 7 | Power-seller tooling | No |

So five of seven were "make Pro more attractive", which is the business we
already have, not a new revenue line — and the top-ranked one is a cost.

### What I got structurally wrong

§8c of the spec rules out marketplace advertising on the grounds that Apple
takes 30%. That is true of the form I considered — **a seller tapping "boost" in
the app**, which is the case Apple's guideline names.

It is NOT true of the other form. Advertising sold **B2B, off-platform, invoiced
or via Stripe Checkout on the web**, is not an in-app purchase. No ad-supported
app pays Apple 30% of its ad revenue. Apple's clause targets in-app purchase
flows by individuals and small businesses buying a boost for their own post.

**This codebase already proves the distinction** — §3 above, Sponsored Events:
€29/€79/€199 tiers, billed through **Stripe**, fully built (checkout endpoint,
webhook handler, sort boost, expiry filtering, push, admin analytics, ~10 tests)
and shipped. Apple takes nothing from it.

So the marketplace equivalent is available and I wrongly excluded it:
**sponsored dealer / shop placement in the marketplace**, sold to businesses on
the same rails Sponsored Events already uses. That is real revenue, it does not
touch §5b (we are not a party to any trade), it does not touch DAC7 (no
consideration is withheld from a member sale), and it does not tax the seller
(§8a) because members still list free — the buyer of the placement is a business.

### The two revenue systems that are BUILT and switched OFF

Measured on prod 2026-08-08. This is the actual answer to "nothing earns us
money": two complete systems are sitting at zero.

**1. Sponsored Events — three environment variables from live.**

```
STRIPE_PRICE_ID_SPONSOR_FEATURED   = (UNSET)
STRIPE_PRICE_ID_SPONSOR_PROMOTED   = (UNSET)
STRIPE_PRICE_ID_SPONSOR_SPOTLIGHT  = (UNSET)
STRIPE_SECRET_KEY                  = SET
```

Everything else is done and tested. Create three one-time products in the Stripe
dashboard, set the ids, restart. €29–199 per event, no Apple cut.

**2. Affiliate — 16 providers wired, every one EMPTY.**

`build_affiliate_url` is deployed and called from the alerts screen, the
notifications screen and the push handler. The env declares 16 affiliate ids —
`EBAY_AFFILIATE_CAMPAIGN_ID`, `CARDMARKET_AFFILIATE_ID`, `TCGPLAYER_AFFILIATE_ID`,
`STOCKX_AFFILIATE_ID`, `BRICKLINK_AFFILIATE_ID`, `CHRONO24_AFFILIATE_ID` and ten
more — **and all of them are set to the empty string.**

Proved on prod rather than inferred:

```
build_affiliate_url('https://www.ebay.com/itm/123456', 'ebay')
  -> tagged=False  network=''   (URL returned unchanged)
```

So **every Target Hit, every Shop tap and every notification tap currently earns
exactly €0**, and has since launch. `demand_signals` has 370 rows — that is 370
recorded outbound intents that were all untagged.

> This is the silent-fallback pattern in its purest form: `VAR=` with no value
> reads as *configured* to `env | grep`, the function returns the input
> unchanged, nothing logs an error, and the revenue is simply absent. It is the
> same shape as `learning_hasattr_guard_turns_a_typo_into_a_silent_noop`.
>
> **Gate to add:** a preflight that fails when an affiliate id is declared but
> empty, or a startup warning naming each empty provider. A revenue integration
> that silently no-ops is worse than one that is absent, because the absent one
> gets noticed.

### Revised priority

1. **Fill the affiliate ids.** The code is deployed and every click is already
   being routed through it. This is not a build; it is signing up for the
   programmes and pasting values. Highest revenue per hour of work in the repo.
2. **Add the empty-affiliate-id gate**, so this cannot silently revert.
3. **Set the three Sponsor price ids.** A built product, three fields from live.
4. **Sponsored dealer placement in the marketplace**, reusing the Sponsored
   Events rails (Stripe, B2B, no Apple cut).
5. Everything in §7 below is subscription conversion. Real, but it is the
   existing business getting better — judge it that way, not as new revenue.

---

## 7. Marketplace monetization — Vinted's lessons under our constraints (2026-08-08)

Written after researching what actually made Vinted work (`docs/P2P_MARKETPLACE_SPEC.md`
§8) and reading it against §5b's facilitation rule, DAC7, and Apple's IAP rules.

### The reframe that generates everything below

Vinted's real lesson is **not** "buyer protection". It is:

> **Charge the BUYER. Never tax the SELLER.**

Buyer Protection is ~75–80% of their €1.1bn (2025); sellers pay nothing. Removing
seller fees in 2016 is what took them from a zero valuation to liquidity, because
they were **supply**-constrained. Every guide-level tactic follows from that.

We are forbidden from their specific implementation — a buyer fee needs funds
flow (EMI licence), and committing to buyer protection is DAC7 trigger #2 (§5a).
A commission withheld from the sale amount is DAC7 trigger #3. So the
transaction is closed to us in every direction.

**But Vinted charges the buyer at the moment of TRANSACTION, and that is not the
only moment a buyer has willingness to pay.** Ours is earlier:

> **The moment of DISCOVERY — knowing a thing exists, at a price, before someone
> else does.**

That moment is already our product. It needs no funds flow, no licence, no
dispute org, and no new regulated activity. Everything below monetizes it.

### The four hard constraints every idea must pass

| Gate | Rule |
|---|---|
| **§5b** | May know everything, do nothing. No funds, no guarantee, no carriage, no adjudication, no verification badge |
| **DAC7** | Do not commit to buyer protection (trigger #2). Do not withhold a commission set against the amount paid (trigger #3) |
| **Apple** | Anything digital consumed in-app is IAP at 30% — explicitly including "buying advertisements to display in the same app". Physical goods between users are outside IAP |
| **§8a** | Never charge to list, never meter supply. That is the 2015 Vinted mistake, and it is the one that nearly killed them |

### The list

Ranked by leverage per unit of build and risk.

---

**1. List an item, earn Pro time.** *(supply flywheel — the strongest idea here)*

Listing stays free and uncapped (§8a). But listing **pays the seller in
subscription**: list an item that reaches Target Hit (`reaches_target_hit`
true, i.e. it carries a `canonical_key`), get N days of Pro.

Why this is the best one:

- It attacks the **cold-start problem directly**. We are supply-constrained in
  exactly the way 2015 Vinted was, and the marketplace is judged on
  `market_hits` created (§1), not GMV.
- It pays for supply **in kind**, at near-zero marginal cost — Pro is software.
- It is the *opposite* of a listing fee, so §8a is satisfied in the strongest
  possible way.
- Apple: giving away subscription time is not a purchase. No IAP surface.
- It rewards the RIGHT behaviour: gated on `reaches_target_hit`, so it pays for
  listings that are canonically identified and can actually feed the alert —
  not for junk volume. That single gate makes it a data-quality incentive rather
  than a spam incentive.

Risk to manage: a farm of throwaway listings for free Pro. Mitigated by the
`canonical_key` gate (junk cannot match the catalogue), the existing one-active-
listing-per-item rule, and capping earned days per period.

---

**2. Sold comps and price history as the paid data product.** *(the moat)*

`_sold_comp_hook` (§1g) now writes a real, two-sided-confirmed sale price into
`market_hits` on every completed trade. **~62,000 catalogue items have no price
data at all** because `ebay_caller.sold_comps()` returns `[]` — so for those
items a Sparrow trade is the *only* sold comp in existence.

Free sees the current estimate. Pro sees the sold history, the P2P prints, and
the confidence band (`q10/q50/q90` already exist on the Ridge models).

- Zero regulatory surface: it is our own data about our own platform.
- The marketplace feeds the paid feature **twice** — supply for alerts, and
  sold comps for pricing.
- Nobody else can build this for these categories. Scryfall has prices; nobody
  has *what collectors actually paid each other*.

---

**3. Seller pricing intelligence — free to list, paid to price well.**

Listing is free and unlimited. What costs money is the answer to *"what should I
ask?"*: the demand signal (`GET /p2p/demand/{item_id}` — watchers, top target),
comparable sold prices, and a suggested range.

- Not a listing fee: nothing is metered, nothing is gated behind paying to sell.
  You pay for **intelligence**, which is the app's actual product.
- Never touches the transaction, so DAC7 #3 is untouched.
- Already partly built — the demand preview exists and is ownership-gated.

This is the piece Vinted structurally cannot copy. Their sellers guess; ours
would be told, from a corpus the platform itself generates.

---

**4. First-look latency on Target Hit.** *(monetizes buyer urgency, no ads)*

In a marketplace where one item has exactly one buyer, **being first is the
entire value**. Pro alerts fire immediately; free alerts carry a delay.

- **Not advertising.** Nothing is sold to a seller, no listing is promoted, so
  Apple's "buying advertisements to display in the same app" clause does not
  apply. It is a subscription tier attribute, already IAP'd through RevenueCat.
- Precedent is ordinary: real-time vs delayed market data is how every financial
  terminal is priced.
- §8a untouched — the seller pays nothing and their reach is not throttled.

> ⚠️ Honest risk: latency tiering can read as hostile in a consumer app in a way
> it does not in finance. Free is already capped at 1 alert/day
> (`max_daily_deal_alerts`), so this stacks a second penalty on the same user.
> Test it as *Pro gets earlier*, framed positively, not as *free gets delayed*.

---

**5. Turn on the affiliate IDs that are already built.** *(money on the floor)*

`build_affiliate_url` exists and is wired into both the alert screen and the push
deep link — but `project_affiliate_ids_unconfigured` says the IDs are not set.
Every Target Hit that fires on an eBay or Cardmarket listing currently earns
**nothing**.

- Outside IAP entirely: the purchase happens on the web, on someone else's site.
- Outside DAC7: eBay is the platform for that sale, not us.
- §5b-clean: a hyperlink is not payment initiation (PSD2 Art. 4(15)).

The member marketplace makes the app worth opening; the external marketplaces
monetize the very same alert. This is the cheapest revenue in the document
because the code is already deployed.

---

**6. Aggregate market reports, sold OUTSIDE the app.** *(0% Apple)*

The data lake (`s3://collectai-warehouse-prod-eu-north-1`) plus P2P sold comps
supports anonymised, category-level reporting: "MTG duals +12% this quarter, 340
member trades." Sell it to shops and dealers **on the web**, not in the app.

- Apple takes **nothing** from a web sale to a business.
- No personal data, no DAC7 relevance, no §5b exposure — it is aggregate
  statistics about a market.
- It is the marketplace earning a second time from data it already produced.

---

**7. Power-seller tooling — bulk, not access.** *(lowest ranked, closest to the line)*

Bulk CSV import, bulk re-price (now that `PATCH /p2p/listings/{id}` exists),
inventory export. Listing stays free and unlimited; you pay for **efficiency**.

Ranked last deliberately: it is the idea nearest to the 2015 mistake, and the
volume to justify it does not exist. Revisit only when someone actually has 200
listings.

### Explicitly rejected — do not revisit without a lawyer

| Idea | Why not |
|---|---|
| **Paid bumps / promoted listings** | Apple's guideline names this case: "buying advertisements to display in the same app… must use in-app purchase" → 30%. And it is a seller fee wearing a different hat (§8a). Vinted earns from bumps, but they are the minority slice of a business funded by Buyer Protection |
| **Buyer protection / escrow / any refund promise** | EMI licence (€350k initial capital, EMD2 Art. 4), a staffed dispute org, and DAC7 trigger #2. §5b's whole point |
| **Commission on the sale** | DAC7 trigger #3, and it needs funds flow we cannot have |
| **Shipping insurance** | Insurance distribution under IDD (§5b) |
| **"Verified seller" / authentication** | Forfeits hosting safe harbour on counterfeits (§5) |

### The shape of the answer

Vinted monetizes the **transaction**, which is closed to us.
We monetize the **information** — which is the thing we actually have, and the
thing the marketplace generates more of with every listing and every trade.

Ideas 1 → 2 → 5 are the sequence: **1** buys supply with software, **2** turns
that supply into a data moat, **5** collects the revenue that is already sitting
uncollected. None of them touches money moving between two members, which is
what keeps the whole thing inside §5b.
