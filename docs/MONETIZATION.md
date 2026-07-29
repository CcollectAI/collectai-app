# Sparrow Collect Monetization Strategy

> Last refreshed 2026-05-19. Renamed from CollectAI 2026-05-04. **iOS IAP via RevenueCat replaced Stripe on 2026-05-09** (commit `652230a`); Stripe code path is preserved for future web/Android billing.

## 1. Current System — RevenueCat IAP (PRIMARY, SHIPPED 2026-05-09)

Two-tier model (was three-tier on Stripe; Premium folded into Pro).

### Plans

| | Free | Pro (€4.99/mo or €39.99/yr) |
|--|------|-----------------------------|
| Purchase mandates | 3 | 10 |
| Deal discovery | No | Yes |
| Dossier PDF export | No | Yes |
| Condition Grading (item card) | No | Yes |
| Set Completion (sets-to-complete) | No | Yes |
| Advanced analytics (price trend, history, market prices) | No | Yes |
| Basic valuation | Yes | Yes |
| Community events | Yes | Yes |
| Ads | Yes | No |

> **Two of these are easy to misread — verified 2026-07-29:**
>
> * **Purchase mandates** is **10**, not unlimited. Both
>   `PLAN_LIMITS["pro"]["max_mandates"]` (billing_router.py) and
>   `FORCED_LIMITS.pro` (useBillingLimits.ts) say 10; only this table said
>   "Unlimited". Corrected here rather than in code — raise both if you want it
>   to be truly unlimited.
> * **Set Completion works**, despite `sets`, `set_items` and `set_registry`
>   all being EMPTY. It is served by `GET /sets/auto-progress`, which computes
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

### What's Built

| Component | File(s) | Status |
|-----------|---------|--------|
| `react-native-purchases` SDK + init | `src/lib/purchases.ts` | Done |
| Plan selection + restore flow | `app/subscription.tsx` | Done |
| Entitlement gating hook | `src/hooks/useBillingLimits.ts` | Done |
| Beta-unlock flag override | `EXPO_PUBLIC_BETA_UNLOCK_ALL` (eas.json) | Done |
| EAS env var plumbing | `EXPO_PUBLIC_REVENUECAT_IOS_KEY` | Done |
| Stripe Checkout + Portal + Webhook (dormant) | `server/app/billing_router.py` | Done, NOT wired for iOS |

### To Activate (dashboard side — see `docs/PUBLIC_LAUNCH_CHECKLIST.md` Phases 1–2)

1. **ASC** → Monetization → Subscriptions → create `sparrow_pro_monthly` (€4.99/mo) and `sparrow_pro_yearly` (€39.99/yr) in a `Pro` group.
2. **ASC** → Users and Access → Integrations → In-App Purchase Keys → generate `.p8`. Note Key ID + Issuer ID.
3. **revenuecat.com** → Apps → Add iOS app `io.sparrowcollect.app` → upload `.p8` + Key ID + Issuer ID.
4. **EAS** → `eas env:create --environment production --name EXPO_PUBLIC_REVENUECAT_IOS_KEY --value 'appl_...' --visibility sensitive`.
5. **RC** → Product catalog → import products, create `pro` entitlement, configure `default` offering with `$rc_monthly` + `$rc_annual`.

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
