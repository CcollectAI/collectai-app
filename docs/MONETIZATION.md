# CollectAI Monetization Strategy

## 1. Current System — Stripe Subscriptions (BUILT)

Three-tier subscription model, fully wired end-to-end.

### Plans

| | Free | Pro (EUR 4.99/mo) | Premium (EUR 9.99/mo) |
|--|------|-------------------|----------------------|
| Purchase mandates | 3 | 10 | 50 |
| Deal discovery | No | Yes | Yes |
| Dossier PDF export | No | Yes | Yes |
| Advanced analytics | No | No | Yes |
| Basic valuation | Yes | Yes | Yes |
| Community events | Yes | Yes | Yes |

### What's Built

| Component | File(s) | Status |
|-----------|---------|--------|
| Stripe Checkout + Portal + Webhook | `billing_router.py` | Done |
| Subscription gating dependency | `subscription.py` (`require_plan()`) | Done |
| Dynamic mandate limits per plan | `subscription.py` (`get_user_mandate_limit()`) | Done |
| Subscriptions DB table + RLS | `20260218_subscriptions.sql` | Done |
| Frontend plan selection screen | `app/subscription.tsx` | Done |
| API client (status/checkout/portal) | `collectorsApi.ts` | Done |
| Settings link to subscription | `Settings.tsx` | Done |
| Webhook idempotency + error hardening | `billing_router.py` | Done |
| 25 tests (14 billing + 11 subscription) | `test_billing.py`, `test_subscription.py` | Done |

### To Activate

Set 4 env vars on the backend server:

```
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_PRO=price_...
STRIPE_PRICE_ID_PREMIUM=price_...
```

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

| Stream | Free Users | Pro/Premium Users | Status |
|--------|-----------|-------------------|--------|
| Subscriptions | — | EUR 4.99-9.99/mo | Built |
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
| P0 | Activate Stripe (set env vars) | 30 min | Enables subscriptions |
| P0 | Apply for eBay Partner Network | 1 hour | Enables affiliate revenue |
| ~~P1~~ | ~~Affiliate links on item detail pages~~ | ~~1 day~~ | ~~Free-tier monetization~~ | **DONE** |
| ~~P1~~ | ~~Affiliate links in barcode scan results~~ | ~~0.5 day~~ | ~~Free-tier monetization~~ | **DONE** |
| ~~P2~~ | ~~Sponsored events system~~ | ~~3 days~~ | ~~New B2B revenue stream~~ | **DONE** |
| P2 | Premium insights upsell (blurred data) | 1 day | Drives Pro conversions |
| ~~P3~~ | ~~Affiliate links in price evidence~~ | ~~0.5 day~~ | ~~Incremental~~ | **DONE** |
| P3 | Apply for TCGPlayer + Cardmarket affiliates | 1 hour | More affiliate sources |
| P4 | Marketplace referral fees | Depends on Deal Desk | Future |
| P4 | Data licensing API | 1 week | Future (needs data scale) |
