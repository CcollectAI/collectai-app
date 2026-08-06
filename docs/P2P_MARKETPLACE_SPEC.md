# Sparrow Marketplace — user-to-user selling (spec)

**Status (2026-08-07):** Stage 1 **and Stage 2 built and deployed** — schema,
API, and UI. Stage 3 (payments/escrow) remains a proposal and is deliberately
not started.
**Governing decision:** ship **listings without payments** first. Escrow only
after volume proves it earns its operational cost.

---

## 1. Why do this at all

Not for transaction revenue. **For supply.**

Measured 2026-08-06, buyable listings per category over 7 days:

```
mtg      276,125 hits →      0 buyable   (100% scryfall price rows)
pokemon  193,472 hits →      0 buyable   (tcgplayer + cardmarket)
yugioh   139,820 hits →      0 buyable   (cardmarket + tcgplayer)
warhammer 10,945 hits → 10,945 buyable   (crawl4ai + ebay)
lego       3,414 hits →  3,414 buyable   (100% ebay)
```

96% of the price corpus is unbuyable, and it is the three categories the app
sells to. **Target Hit cannot fire for them at all** — it requires
`url IS NOT NULL AND is_listing IS TRUE`.

A user listing is a buyable row *in the exact categories where we have none*,
and unlike eBay rows we own it: no rate limit, no ban risk, no adapter drift.
The marketplace is the supply fix for the paid feature. Judge it on
`market_hits` created, not on GMV.

## 1b. "Why not just scrape harder?" — the honest answer

This is the obvious objection, and on 2026-08-06 we ran the experiment rather
than argue about it. Both halves of the answer are measured.

**Scraping can, in fact, close the buyable gap.** An eBay listings pass now
gives mtg/pokemon/yugioh their first buyable rows (`docs/MARKET_DATA.md`), and
Firecrawl was verified to scrape **cardmarket.com** — Europe's biggest TCG
marketplace, and the site Crawl4AI is Cloudflare-blocked on. So "we cannot get
supply without users" is **false**, and this spec should not claim it.

**But scraped supply is rented, and the rent is volatile.** Same day, same
system:

| Evidence | What it cost |
|---|---|
| tcgcsv.com has 403'd us since 2026-08-01 ("flagged for overuse") | **lorcana, digimon, one_piece_tcg went to zero market_hits** — 24,404 catalog items with no price data at all, unnoticed for 5 days |
| Cardmarket answers Crawl4AI with a Cloudflare challenge | Reachable only via **paid** Firecrawl |
| Firecrawl allocation | **1,000 credits/month**, 1 per page → ~33 Cardmarket pages/day, and it expires monthly |
| eBay free-text search | Cannot identify a card *printing*; needed three stacked defences to stop a €1.20 novel firing an alert against an €8015 target |

So the real argument for P2P is **not** "we have no other way to get supply".
It is:

1. **Owned supply has no rent and no ban risk.** A user listing cannot 403 us,
   cannot put up a Cloudflare challenge, and costs zero credits.
2. **It is structurally correct data.** A listing created from an `items` row
   already carries `canonical_key`, category and photos — no free-text
   guessing, no printing ambiguity, none of the three defences above. It joins
   the snipe's **exact-identity** arm rather than the fuzzy title arm.
3. **It is differentiated.** eBay listings are on eBay. Collections in this app
   are not anywhere else.

Judge Stage 1 against that, not against "scraping is impossible". If the only
goal were raw buyable volume, the cheaper move is more scraping — and it should
be done regardless, because supply from both sources is strictly better than
either alone.

## 1c. What is actually built (2026-08-06)

Verified across all three layers before this section was written.

**Database** — `server/migrations/20260806_p2p_marketplace_stage1.sql`, applied
to prod. Additive only. Confirmed present: `marketplaces` row `sparrow`;
`listing_reports` table; 5 new `marketplace_listings` columns
(`canonical_key`, `category`, `ships_from`, `delisted_at`, `reports_count`);
5 indexes; 2 RLS policies. **`schema.lock.json` was regenerated** — DDL stales
it and a stale lock hard-downs the API on the next bake restart.

**Backend** — `server/app/features/p2p_listing_router.py`, registered in
`main.py`. Five endpoints, exercised over authed HTTP against prod:

```
POST /p2p/listings                    -> 201   (create from an owned item)
GET  /p2p/listings?mine=true          -> 200   (browse)
GET  /p2p/listings/{id}               -> 200   (deep-link target)
POST /p2p/listings  (same item twice) -> 409   ALREADY_LISTED
POST /p2p/listings  (not your item)   -> 404   ITEM_NOT_FOUND
POST /p2p/listings/{id}/delist        -> 200   + supply row removed
```

Ownership is enforced **server-side**, not by hiding UI.

The deep-link chain is verified end to end: publish writes
`https://sparrowcollect.com/l/<id>` into `market_hits.url`, and GET on that id
returns the listing. **After a sale it returns `status: "sold"`, not 404** — a
buyer who taps a Target Hit should learn the item went, not that something
broke.

**Tests** — `server/tests/test_p2p_listing_router.py`, 15 passing. They pin the
*contract* (legal status values, `fixed_price`, `marketplace_id` being TEXT)
and the *hook semantics* (WHERE-NOT-EXISTS not ON CONFLICT; delist awaited,
publish not), because those are exactly what the four bugs below violated.

**Frontend** — `src/api/p2pApi.ts`, exposed through `collectorsApi`. Typed
client only; no screens yet.

### Five bugs the audit caught (all fixed)

Listed because each is a class that will recur:

0. **The deep link resolved to nothing.** The supply hook wrote
   `https://sparrowcollect.com/l/<id>` into `market_hits.url` and *no endpoint
   served it* — `app/alerts.tsx` would `Linking.openURL` a 404. That is the
   dead-button failure the snipe query was fixed to avoid, reintroduced from
   our own side. Fixed with `GET /p2p/listings/{id}`.

1. **`marketplace_id` is TEXT, not an FK.** It holds a key like `'ebay'`, not
   `marketplaces.id` (bigint). The name reads like a foreign key and is not
   one. Passing the numeric id raised `expected str, got int`.
2. **CHECK constraints narrower than the code.** `format` must be
   `'fixed_price'` (not `'fixed'`), and `'withdrawn'` is **not** a legal status
   — the constraint allows `draft|active|sold|expired|delisted|error`. Same
   class as `learning_db_constraints_narrower_than_code`.
3. **`ON CONFLICT DO NOTHING` that can never fire.** `market_hits`' only unique
   key is `(id, seen_at)` with `id` from a sequence, so a republish wrote a
   SECOND buyable row and Target Hit would surface one listing twice. Now
   `WHERE NOT EXISTS`, matching `persist_comps_to_db`.
4. **The delist supply-hook was fire-and-forget.** The test showed the
   `market_hits` row surviving a sale. Publish stays async (a missing row is a
   non-event); delist is now **awaited**, because a lingering row sends a buyer
   to something already sold and spends their daily Target Hit.

## 1d. Stage 2 — offers, completion, grading (built 2026-08-07)

**Schema.** `p2p_offers` is its OWN table. `public.offers` was unusable: its FK
points at `public.listings` (the deal/mandate table) and
`app/agents/{deal_completion,deal_risk}.py` both JOIN through it, so sharing it
would have broken those agents and dropping the FK would leave `listing_id`
ambiguously referencing one of two tables. **The Stage 2 E2E surfaced this as
an `offers_listing_id_fkey` violation on its first run** — a mocked test would
have missed it entirely. Same collision recurred in the FE: `collectorsApi`
already exported a deal-desk `respondToOffer`, so the P2P methods are namespaced
`p2p*`.

**The three decisions, as implemented:**

| Decision | Implementation | Why not the obvious alternative |
|---|---|---|
| Accept = agreement, not a lock | sets `reserved_offer_id`; listing stays live and browsable | With no payment rail a hard reserve is unenforceable and lets a bad actor block competitors free. Walking away sets `withdrawn_by` — the only honest sanction |
| Completion is two-sided | `seller_confirmed_at` + `buyer_confirmed_at`; both ⇒ `completed` | One-sided completion lets a single actor with two accounts manufacture trades |
| Grades anchored to a completed trade | `member_grades.offer_id NOT NULL`, unique per rater, API rejects with `TRADE_NOT_COMPLETE` | An unanchored grade is the farmable rating this design exists to prevent |

`'withdrawn'` is **not** a legal status (`p2p_offers_status_check`), so a
walk-away writes `cancelled` + `withdrawn_by`. Same constraint-narrower-than-
English trap as `'fixed'` vs `'fixed_price'`.

Reputation hides `positive_pct` below **3 grades**: "0% positive" off one grade
is a smear, "100%" off one is not credibility.

**E2E: 22/22 passing** (`server/tests/e2e_p2p_stage2.py`), covering offer →
counter → accept → soft-reserve-does-not-delist → one-sided confirm (grading
still blocked) → two-sided completion → supply row removed → mutual grading →
re-grade edits rather than double-votes.

**UI**: `app/offers.tsx` (both sides of every trade in one screen — a member is
usually both), offer ladder on the listing detail, and the confirm/grade
actions. `can_confirm` / `can_grade` come from the SERVER; the client never
re-derives the state machine, because two implementations of one state machine
drift apart.

## 1e. The demand signal (built 2026-08-07)

The differentiator, and the reason a seller lists at all:

> **4 members are watching this · highest target €40**

No generic marketplace can say this. Facebook infers intent from a feed; eBay
waits for a search. Sparrow knows what members want *before* they look, because
a watchlist row with a target price is pre-declared demand.

- `GET /p2p/demand/{item_id}` — pre-listing, **ownership enforced** (demand is
  competitive information and would otherwise be scrapeable).
- `watchers` / `watchers_above_price` on the listing detail — the latter counts
  members who would get a Target Hit at the asking price, which is the number
  that actually predicts a sale.
- Joins `watchlist_items.item_id` (BARE) to `marketplace_listings.canonical_key`
  (BARE) — direct, unlike `market_hits.item_ref` which is namespaced.
- **Excludes the seller's own watchlist row.** Telling someone "1 person is
  watching" when it is them is a lie.
- Returns `is_catalog_matched: false` for unmatched items so the UI shows the
  match prompt instead of a meaningless "0 watching".

Verified with a seeded watcher: a €35 target against a €20 ask returned
`watchers=1, above=1, top=35.0`, and an unrelated item stayed at 0.

## 1f. `item_images` — NOT a bug (checked 2026-08-07)

Earlier notes flagged add-photo as dead since 2026-02. **That is now stale.**
`20260801_fix_item_images_schema.sql` rebuilt the table, and on inspection the
shape (`id, item_id, image_url, label, position, created_at`), the RLS INSERT
`WITH CHECK`, and the FE multipart contract are all correct — a probe INSERT
succeeded. The 0 rows simply mean nobody has uploaded in the six days since.
Do not re-investigate this without first writing a row.

## 2. Scope — three stages, each shippable

### Stage 1 — Listings (no money changes hands)

A seller lists an item they own. A buyer sees it, and taps through to contact
the seller. **Sparrow never touches funds.**

- List from an item you already own (`items` row → prefilled title, category,
  photos, `canonical_key`, predicted value as a price suggestion).
- Buyer discovery: listings appear in search, on the catalog item page, and —
  critically — **as `market_hits` rows**, so they feed Target Hit like any
  other marketplace.
- Contact: opens the existing chat (`app/chat/[threadId]`), already built.
- No checkout, no escrow, no fees, no payouts.

**Why this is the right v1:** it dodges PSD2, chargebacks, refund disputes and
most of DAC7, while delivering 100% of the supply benefit. The feature that
makes money (Pro subscriptions via Target Hit) gets its inventory; the feature
that costs money (payments ops) is deferred.

### Stage 2 — Offers

`offers` already exists (`id, listing_id, buyer_id, seller_id, amount, status,
message, counter_count, expires_at`) with 0 rows. Wire buy/counter/accept as
*intent*, still settled off-platform. Gives negotiation without regulation.

### Stage 3 — Payments + escrow (only if Stage 1–2 volume justifies it)

Stripe Connect Express: Stripe is the payment institution, holds funds, runs
KYC and payouts. See §5 before starting.

## 3. What already exists (do not rebuild)

| Asset | State |
|---|---|
| `marketplace_listings` table | 38 columns, **0 rows**. Built for *external* listings (eBay), has `marketplace_id`, `external_listing_id`, `listing_url` |
| `offers` + `offer_events` | Exist, 0 rows |
| `marketplace_listing_router.py` | 14 endpoints: create listing, list mine, record sale, fee schedules, eBay OAuth |
| `app/sell/` screens | `offers.tsx`, `dashboard.tsx`, `[offerId].tsx`, `ebay-defaults.tsx` |
| `SELLING_ENABLED` | `false` — the whole surface is hidden because there is no eBay OAuth behind it |
| Chat | Built and working — the Stage 1 contact channel |

**Reuse `marketplace_listings` with a `sparrow` marketplace_id** rather than a
new table. `external_listing_id`/`listing_url` stay NULL for native listings;
everything else (price, condition, shipping, status, photos via `item_images`)
already maps. This also means the existing dashboard and fee code keeps working.

Flipping `SELLING_ENABLED` alone is **not** the move — it reveals eBay OAuth UI
that has no backend. Stage 1 needs its own flag, `P2P_MARKETPLACE_ENABLED`.

## 4. The supply hook (the part that matters)

On listing publish, write a `market_hits` row:

```
provider   = 'sparrow'
is_listing = TRUE
url        = sparrow://listing/<id>   (deep link, not an external URL)
item_ref   = '<category>:<canonical_key>'   -- from the item's canonical_key
price_eur  = converted from listing currency
seen_at    = now()
```

That single write is what makes a user listing snipeable. It must use
`upsert_market_hits_batch` like every other writer, and `item_ref` must be
**namespaced** (`mtg:sum-283-bayou`) — see
`learning_canonical_key_vs_item_ref_namespace`.

Delist/sell → mark the hit stale so Target Hit stops surfacing it. A snipe that
opens a sold listing is worse than no snipe.

**Affiliate note — verified 2026-08-06, no change needed.** `app/alerts.tsx`
opens `affiliate_url || listing_url`. `build_affiliate_url` validates the scheme
against `_ALLOWED_SCHEMES` and returns `(original_url, "")` untagged for
anything that is not http(s) (`affiliate.py:96`). A `sparrow://` deep link
therefore passes through unmodified and earns nothing — which is correct; there
is no affiliate on our own inventory. It does log a warning per call ("Rejected
non-HTTP URL scheme"), so either accept the log noise or skip the call for
`provider = 'sparrow'`.

> **Alternative worth considering:** use an `https://sparrowcollect.com/l/<id>`
> universal link instead of `sparrow://`. Same in-app routing, no scheme
> warning, and it works when shared outside the app — which matters if a seller
> posts their listing anywhere.

## 5. Legal exposure — ranked by what actually bites a solo founder

> Not legal advice. Get a Dutch lawyer before Stage 3. KvK 99596326.

| Risk | Applies at | Mitigation |
|---|---|---|
| **PSD2 / payment institution** | Stage 3 only | Stripe Connect Express — Stripe is the regulated party. Never hold funds in our own account |
| **DAC7** (EU platform tax reporting) | Stage 3, arguably Stage 2 | Applies to platforms facilitating "relevant activity" where we know the consideration. Stage 1 does not process or know the price paid. Stage 3 = collect seller TIN + address, report by 31 Jan |
| **DSA notice-and-action** | Stage 1 | Report button on every listing, act on notice, give a statement of reasons. Micro-enterprise exemption covers *some* Art. 19 obligations but **not** notice-and-action |
| **Counterfeits** | Stage 1 | Hosting safe harbour holds only while we stay a neutral host. **Never label a listing "authenticated by Sparrow"** — that forfeits it |
| **Consumer law** | Stage 2+ | Consumer sellers owe no 14-day withdrawal right; traders do. Must not present one as the other |
| **AML** | Stage 3, watches especially | Stripe's KYC covers it; high-value categories need a threshold flag |
| **Apple 30%** | Never | Physical goods shipped between users are outside IAP. Must **not** use IAP for this — that is the rule, not a loophole |

**The unbounded risk is operational, not legal.** Disputes, "not as described",
fakes, shipping. Vinted staffs that with hundreds of people. Stage 1 has none of
it by construction, which is the entire argument for stopping there first.

## 6. Build order

1. `P2P_MARKETPLACE_ENABLED` flag + `marketplace_id = 'sparrow'` seed
2. Create-listing flow from an owned item (reuse `ListForSaleModal`)
3. `market_hits` write on publish / stale on delist ← **the supply hook**
4. Listing detail + "Message seller" → existing chat
5. Report button + takedown path (DSA)
6. Listings surfaced in search + catalog item page
7. *Then measure:* buyable rows created in mtg/pokemon/yugioh, and Target Hits
   fired from `provider = 'sparrow'`. That number decides whether Stage 2/3 ever
   happens.

### The measurement that decides it

Run this after Stage 1 has been live a month. It is deliberately a comparison,
not a vanity count — scraped supply is the control group:

```sql
SELECT provider,
       count(*)                                        AS buyable_rows,
       count(*) FILTER (WHERE seen_at > now() - interval '7 days') AS last_7d
FROM public.market_hits
WHERE is_listing IS TRUE AND url IS NOT NULL
GROUP BY 1 ORDER BY 2 DESC;

SELECT trigger_value->>'provider' AS src, count(*)
FROM public.alert_trigger_history
WHERE trigger_type = 'watchlist_snipe'
GROUP BY 1;
```

If `sparrow` is not a meaningful share of Target Hits after a month of Stage 1,
**do not build Stage 2 or 3.** Offers and escrow multiply the operational load
of a marketplace that is not producing alerts, and the scraping path already
covers the supply need at lower cost.

## 7. Open questions — three answered 2026-08-06

**Photos — do NOT assume `item_images` works.** The table exists with the right
shape (`id, item_id, image_url, label, position, created_at`) but has **0 rows
in prod**. Per `learning_create_if_not_exists_silently_noops`, add-photo was
dead on both platforms from 2026-02 and the read seam still carries the
workaround aliases. A listing with no photo is not a listing, so **Stage 1 must
begin by proving an end-to-end photo upload with a real login** — not by reading
the migration. If it is still broken, that is the first ticket, not a footnote.

**Listing items not in your collection — allow it, but expect degraded
matching.** Only **4 of 16** `items` rows carry a `canonical_key`. Without one
there is no `item_ref`, so the listing can only ever match Target Hit's fuzzy
title arm (`similarity(title) >= 0.55` within category), never the exact arm.
Consequence: the create-listing flow should push hard toward picking a catalog
item (that is what sets `canonical_key`), and free-text listings should be
accepted but flagged internally as low-match-quality. This is the same gap that
makes the watchlist weak today — fixing it once helps both.

**Universal link over custom scheme** — see §4. Decided.

Still open:

- Shipping: display-only in Stage 1, or structured (carrier/price) from day one?
- Geography: NL-only first? Cross-border consumer law is materially harder
- Does a `sparrow` listing count toward the free plan's watchlist/alert caps, or
  is listing always free? (Recommend: listing always free — supply is the point)
