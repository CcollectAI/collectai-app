# App Store ASO — submission-ready copy

All copy below fits Apple's character limits (App Store Connect form field maxes inline). Replace `<APP_NAME>` with the final chosen name (in progress — see name-checklist conversation).

---

## App Information

| Field | Value | Limit |
|---|---|---|
| **App Name** | `<APP_NAME>` | 30 chars |
| **Subtitle** | "Scan, value & track collectibles" | 30 chars |
| **Bundle ID** | `com.ccollectai.app` (verify against `app.json:expo.ios.bundleIdentifier`) | n/a |
| **SKU** | `COLLECTAI001` | 100 chars |
| **Primary Language** | English (U.S.) | n/a |
| **Primary Category** | Lifestyle | n/a |
| **Secondary Category** | Shopping | n/a |
| **Age Rating** | 4+ (no objectionable content) | n/a |

## Pricing & Availability

- **Price tier:** Free (with In-App Purchases)
- **In-App Purchases:** Pro €4.99/mo, Premium €9.99/mo
- **Available territories:** all 175 (default)

---

## Promotional Text (170 chars max — editable without app review)

> Scan any collectible to instantly value it with AI. Track your portfolio, get price alerts, and discover what's trending in 54 collector categories.

(170 / 170)

---

## Description (4000 chars max)

> **<APP_NAME> — Your AI-Powered Collectibles Companion**
>
> Whether you collect Pokémon cards, watches, sneakers, vinyl, Funko Pops, or vintage cameras, <APP_NAME> turns your phone into a smart valuation and tracking tool for everything you own.
>
> **POINT, SCAN, KNOW**
>
> Snap a photo of any item and our AI identifies it, finds recent sales across 17+ marketplaces, and gives you a confident price estimate in seconds. No more digging through eBay sold listings, Discogs threads, or Reddit price checks — we do it instantly.
>
> **YOUR FULL COLLECTION, ORGANIZED**
>
> Build your collection one scan at a time. Each item gets:
> • Live market value (low / median / high)
> • Price history charts
> • Condition grading suggestions
> • Authenticity hints
> • Where to buy or sell
>
> Browse your portfolio by category, value, or recent activity. Filter, search, and bulk-edit with smart selection.
>
> **PRICE ALERTS THAT ACTUALLY WORK**
>
> Add items to your watchlist with target prices. Get notified the moment something hits your number — across the marketplaces we monitor 24/7. Auction ending soon? You get an urgent alert 15 minutes before.
>
> **54 COLLECTOR CATEGORIES**
>
> Pokémon TCG, Magic: The Gathering, Yu-Gi-Oh, Lorcana, Hot Toys, Funko, Lego, Warhammer, Gunpla, vinyl records, anime figures, watches, whiskey, sneakers, comic books, vintage cameras, K-pop merch, designer toys, plush, retro games, and many more — each with category-specific data sources and AI models.
>
> **DEAL DESK + EVENTS**
>
> See live deals across the marketplaces we track. Find collector meetups, drops, and conventions near you. Connect with sellers via in-app DMs.
>
> **SELL DIRECT TO eBAY** *(coming soon)*
>
> List items from your collection directly to eBay in 30 seconds — pre-filled from your scan data, photos, and our valuation. No copy-paste, no mistakes.
>
> **PRIVACY-FIRST**
>
> Your collection is yours. We don't sell data. EU-hosted (Frankfurt). End-to-end RLS. You can export or delete everything anytime.
>
> **PRO UNLOCKS**
>
> Pro (€4.99/mo) — unlimited scans, advanced analytics, deal desk full access, fresh-comp on-demand, ad-free.
> Premium (€9.99/mo) — everything in Pro plus higher API quotas, early features, and priority support.
>
> Start free. No credit card. Cancel anytime.
>
> Questions, requests, bugs? Email us at support@<APP_DOMAIN>.app — every message reaches a human within 24 hours.

(2,548 / 4,000 — room to add)

---

## Keywords (100 chars max, comma-separated, no spaces)

> collectibles,pokemon,tcg,funko,sneakers,vinyl,watches,price,scan,collection,tracker,marketplace

(98 / 100)

**Notes for tuning post-launch:** rotate based on App Store Connect Search Ads data. Top candidates to test: `appraisal`, `valuation`, `comp`, `discogs`, `ebay`, `psa`, `cgc`, `inventory`.

---

## What's New in This Version (4000 chars)

> Welcome to <APP_NAME>! This is our launch release. Here's what's in the box:
>
> • AI-powered scan + valuation across 54 collector categories
> • Live price comps from 17+ marketplaces (eBay, Vinted, Mercari, Catawiki, Yahoo Auctions, and more)
> • Watchlist with target-price alerts and auction-ending notifications
> • Deal desk: see active marketplace deals in your collection's categories
> • Events: find collector meetups, drops, and conventions
> • In-app DMs with other collectors
> • Multi-currency portfolio tracking (7 currencies)
> • Dark mode + 7 languages (EN, NL, DE, FR, ES, JA, KO)
>
> Got feedback? We answer every email. Tap Settings → Report a Bug.

---

## App Preview Video (optional, up to 30s)

- **Status:** Remotion compositions exist in `/video/` per project memory; render script is wired.
- **Spec:** 15-30s, no narration, captions in primary device locale, 9:16 aspect for portrait, no marketing references like "App Store" or "Apple".
- **Suggested cuts:** scan flow → valuation reveal → watchlist alert → portfolio dashboard.

---

## Screenshots (required: 6.5" + 6.7" iPhone sizes; iPad optional)

- **Status:** 6 Remotion compositions exist (per memory `Round 50j`). iPhone 16 Pro Max (1290×2796) baseline.
- **Order recommendation (App Store ranks discoverability by first 3):**
  1. Scan flow / hero
  2. Valuation result + price chart
  3. Portfolio overview
  4. Watchlist with alert
  5. Deal desk
  6. Events / Social

---

## Privacy URLs (required at submit)

- **Privacy Policy:** `https://<APP_DOMAIN>.app/legal/privacy-policy`
- **Terms of Service:** `https://<APP_DOMAIN>.app/legal/terms`
- **Support URL:** `https://<APP_DOMAIN>.app/support` (or `mailto:support@<APP_DOMAIN>.app`)
- **Marketing URL** (optional): `https://<APP_DOMAIN>.app`

All four routes already exist in `app/legal/*.tsx` + `web/`. Domain swap when DNS lands.

---

## Privacy Nutrition Labels (App Store Connect form)

Match `app.json:privacyManifests.NSPrivacyCollectedDataTypes`:

| Data | Linked? | Tracking? | Purpose |
|---|---|---|---|
| Email Address | Yes | No | App Functionality |
| Photos | Yes | No | App Functionality |
| Precise Location | No | No | App Functionality |
| Product Interaction | No | No | Analytics |
| Crash Data | No | No | App Functionality |
| Payment Info | Yes | No | App Functionality |

Tracking: **Off**. We do not share data with third parties for advertising.

---

## Submit checklist

- [ ] Final app name decided (in progress)
- [ ] Domain DNS resolves (`<APP_DOMAIN>.app`)
- [ ] Apple Developer enrollment complete
- [ ] App Store Connect record created (returns ascAppId for `eas.json`)
- [ ] EAS builds tested on TestFlight with real Apple ID
- [ ] Stripe live keys swapped + 4 price IDs verified live
- [ ] Screenshots uploaded (6, both required sizes)
- [ ] Description + keywords pasted from this file (with `<APP_NAME>`/`<APP_DOMAIN>` swapped)
- [ ] Promotional text + What's New text pasted
- [ ] Privacy URLs verified loadable
- [ ] Privacy nutrition labels filled (table above)
- [ ] Age rating questionnaire answered → 4+
- [ ] Demo account credentials filled (use ci-test@collectai.app per memory)
- [ ] Submit for Review

After submit: ~24-48 hr review window.
