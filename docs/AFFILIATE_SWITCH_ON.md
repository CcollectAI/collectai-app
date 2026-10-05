# Affiliate Switch-On Plan

How to turn on Sparrow's affiliate revenue stream. The code rail is already
built (`server/app/lib/affiliate.py` tags 16 networks; clicks are tracked into
`demand_signals`). What's left is **enrollment** (your hands) and **conversion
reconciliation** (a small deferred build).

This is **additive** to the subscription — it monetises the buy-side for *all*
users (including Free) without touching the paywall. Deal Discovery stays
gated; Item Shop and Set Completion are free and still earn affiliate on the
buys they route.

---

## Step 1 — Enroll in the networks (your hands)

> ⚠️ **Rewritten 2026-09-28** (class AV in `docs/CLASS_SWEEPS.md`). The old
> table treated every network as "paste an id, params get appended". Only eBay
> works that way. The helpers for the rest built links the networks do not
> read, and three of the programmes do not exist.

What goes in each env var (`server/app/config.py:302+`) depends on the
network. A value of the wrong shape is refused (logged, link ships untagged),
so a bare id pasted where a tracking link belongs cannot build a dead link.

**Checked — tags as soon as the var is set** (apply in this order):

| # | Network | Programme | Commission | Env var holds |
|---|---------|-----------|-----------|---------------|
| 1 | eBay | eBay Partner Network (partnernetwork.ebay.com) | 1–4% | `EBAY_AFFILIATE_CAMPAIGN_ID` = the 10-digit campaign id |
| 2 | Catawiki | Partnerize | 80% (new) / 40% (existing) of Catawiki's OWN fee, + up to €40 per new bidder — not a % of the hammer price | `CATAWIKI_AFFILIATE_ID` = `https://prf.hn/click/camref:<id>` |
| 3 | TCGPlayer | Impact (their only programme) | 3.5% | `TCGPLAYER_AFFILIATE_ID` = `https://tcgplayer.pxf.io/c/<pub>/<ad>/<prog>` |
| 4 | Whatnot | Impact | 1–3.5% | `WHATNOT_AFFILIATE_ID` = the Impact tracking link |
| 5 | StockX | Impact | varies | `STOCKX_AFFILIATE_ID` = the Impact tracking link |
| 6 | Mercari | Impact (unconfirmed — if it turns out to be Awin, the format needs adding) | varies | `MERCARI_AFFILIATE_ID` = the Impact tracking link |

eBay: the rotation id (`mkrid`) is picked from the listing's eBay site
(`ebay.nl`, `ebay.de`, …), so one campaign id covers every site. Note that
`affiliate_links_router.py` builds every eBay *search* on `ebay.com` today, so
EU members are sent to the US site — a product decision, not a tagging bug.

**Unchecked — var is read but NEVER applied** (a set value logs a warning):
KEH (ShareASale), MPB (FlexOffers/Sovrn), Master of Malt (Affiliate Future),
PopMart (Digidip), Drop (FlexOffers), Chrono24, AmiAmi (Sovrn). To enable one
at enrollment: copy a deep link from the network's dashboard, add its format to
`_PROGRAMMES` in `affiliate.py`, with a test. Do not guess the format.

**No programme — env var removed:** Cardmarket (signup referral only, capped at
€10/month), Discogs, BrickLink.

**The URL's host picks the network, not the caller's label** (2026-09-28): a
scraper row (`crawl4ai`, `firecrawl`) at ebay.de or catawiki.com is tagged as
eBay / Catawiki, and an Impact or Partnerize link is only built for the brand's
own domain (`_source_from_host` in `affiliate.py`).

**The signup checklist, in order, lives in `docs/OPEN_DECISIONS.md` #16.**

**eBay switched on 2026-10-05.** Verified: live `/marketplace/affiliate-links` → eBay `affiliate_url` with `campid=5339218687&customid=sparrow&mkevt=1`, and a click wrote its `demand_signals` row (test row deleted). A scripted fetch of the tagged link gets 403, but so does eBay's plain homepage from `curl` (bot block), so the 403 says nothing about the tag. **Falsifier:** the EPN dashboard shows clicks within ~24h of a real tap from a phone. Do not buy through your own link (EPN policy).

**To set on EC2**: add the value to `/opt/collectors/.env`, run the 9
`ExecStartPre` stages by hand, restart bake, then check that
`/marketplace/affiliate-links` returns a tagged `affiliate_url`.

---

## Step 2 — Tag rebrand + per-click sub-ID  ✅ DONE (this change)

`server/app/lib/affiliate.py`:
- All tags rebranded `collectai` → `sparrow`.
- `build_affiliate_url(url, source, subid=None)` now embeds a per-click sub-ID,
  defaulting to `"sparrow"`: `customid` (eBay), `subId1` (Impact), `pubref`
  (Partnerize) — the field each network puts in its conversion report.
- `deal_discovery_agent.py` passes `subid=deal_id` — so every discovered deal's
  link is attributable back to a row in `public.mandate_deals`.

Covered by `server/tests/test_affiliate.py` (26 passing as of 2026-09-28).

---

## Step 3 — Conversion reconciliation  ⏳ DEFERRED (post-launch wave)

Today we track **clicks** only (`POST /marketplace/affiliate-click` →
`demand_signals` where `signal_type='affiliate_click'`); `estimated_commission`
on a deal is an *estimate*. To book **real** revenue we ingest each network's
confirmed-sale reports and join them back via the sub-ID.

> Do **not** build this until volume justifies it and the pre-launch minimum
> manifest is lifted. At low volume, reconcile manually from each network's
> dashboard. This section is the ready-to-apply design.

### 3a. Schema — `affiliate_conversions`

```sql
CREATE TABLE IF NOT EXISTS public.affiliate_conversions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    network         text NOT NULL,           -- 'ebay_partner_network', 'catawiki', ...
    subid           text,                     -- == mandate_deals.id when sourced from a deal
    external_txn_id text NOT NULL,            -- network's transaction/order id (dedup key)
    sale_amount     numeric(12,2),
    sale_currency   text DEFAULT 'EUR',
    commission      numeric(12,2),            -- what the network actually pays us
    status          text NOT NULL DEFAULT 'pending',  -- pending|confirmed|paid|reversed
    posted_at       timestamptz,              -- when the network recorded the sale
    ingested_at     timestamptz NOT NULL DEFAULT now(),
    raw             jsonb,                    -- full report row for audit
    UNIQUE (network, external_txn_id)         -- idempotent re-ingest
);
CREATE INDEX IF NOT EXISTS idx_affconv_subid  ON public.affiliate_conversions (subid);
CREATE INDEX IF NOT EXISTS idx_affconv_posted ON public.affiliate_conversions (posted_at DESC);
```

Apply via Alembic (`server/migrations/versions/`), **then regenerate
`scripts/schema.lock.json`** or `preflight_schema_lock` will fail-fast on the
next bake restart and take the API down. Add an RLS policy (service-role write,
no client read) consistent with other server-owned tables.

### 3b. Attribute a conversion back to the user

```sql
SELECT c.network, c.commission, c.sale_amount,
       d.user_id, d.mandate_id, d.listing_price
FROM   public.affiliate_conversions c
LEFT JOIN public.mandate_deals d ON d.id = c.subid
WHERE  c.status = 'confirmed';
```

`subid` = the `deal_id` we put in `customid`/`utm_content`, which is exactly
`mandate_deals.id`. Item-shop / catalog clicks (no deal row) carry `subid =
'sparrow'` and reconcile at the aggregate network level only.

### 3c. Ingestion worker (design)

- One worker, daily, pulling each enrolled network's report API/CSV:
  - eBay → EPN Reporting API
  - Impact (Whatnot/Mercari/StockX) → Impact Reporting API
  - Partnerize (Catawiki) → Partnerize API
  - ShareASale / FlexOffers / Sovrn / Affiliate Future → their report endpoints
- Upsert into `affiliate_conversions` on `(network, external_txn_id)` (idempotent).
- Register in the bake manifest + `record_run` like other workers; smoke-run
  once before declaring shipped (asyncpg interval/DSN gotchas — see MEMORY).
- Surface totals via a new `/intelligence/affiliate-revenue` endpoint alongside
  the existing `/intelligence/top-affiliates`.

---

## Step 4 — Lift routed GMV (product, ongoing)

Affiliate revenue ≈ routed GMV × conversion × blended commission. The lever is
**routed GMV**, not the %:
- Keep `ItemShopSection` / `MarketplacePickerSheet` prominent — shown to Free
  users too (these features are free; the affiliate cut is the monetisation).
- Ensure every Deal Hub "Buy It" uses the tagged `affiliate_url`.
- Prefer routing to high-rate niche networks (Catawiki, Master of Malt) where a
  category match exists.

### 4a. Wishlist Shop — fixed 2026-08-04

`MarketplacePickerSheet` was written but had **zero importers**. The only Shop
entry point, `app/(tabs)/wishlist.tsx::handleShop`, fetched the links itself and
opened `links[0]` with a bare `Linking.openURL`. Three consequences, all silent:

1. **Every category routed to eBay.** eBay was appended first unconditionally in
   `affiliate_links_router.py`, so `links[0]` was always eBay — a EUR-priced MTG
   single went to eBay US while Cardmarket sat unused at index 2. The response
   is now **ordered by category fit** (`_CATEGORY_PROFILES[cat].sources`), so
   `links[0]` is Cardmarket for TCG, BrickLink for LEGO, StockX for sneakers.
   Callers that open one link should open `links[0]`; that ordering is a
   contract, not cosmetics.
2. **The search was unshoppable.** The URL was `?_nkw=<bare title>` and nothing
   else. A watchlist row titled "Bayou" searched all of eBay. Searches now carry
   `_sacat` (browse category), `LH_BIN=1`, `_sop=15`, and `_udhi` when the user
   has a target price, plus a per-category query suffix.
3. **Clicks were invisible.** `Linking.openURL` bypassed
   `openAffiliateUrl`, so wishlist Shop taps never reached
   `demand_signals` — the one signal that tells you which marketplaces convert.
   Both the sheet and the wishlist now route through it.

**`_sacat` values are derived, not guessed.** They came from eBay's Taxonomy API
(`/commerce/taxonomy/v1/category_tree/0/get_category_suggestions`) and were then
widened by hand to the browse level containing the whole collectible type — the
API's top suggestion for gunpla was `261068` (Action Figures) and for pens
`14000` (Montblanc), both of which hide most real listings. All 40 were then
verified against live inventory via the Browse API: filtered vs unfiltered
result counts, zero empties. **A wrong category id fails silently** — the search
just looks like "no stock" — so re-derive with the API rather than editing by
intuition.

**Twelve sources can build a *search* URL** (`_SEARCHABLE_SOURCES`, 2026-09-28):
ebay, tcgplayer, cardmarket, mercari, discogs, stockx, bricklink,
yahoo_auctions_jp, amiami, chrono24, catawiki, google. (This said nine until
chrono24, catawiki and google were added.) Naming one of those six in a category profile makes it silently drop out of
the response — `test_every_profile_names_only_buildable_sources` guards this.
Adding their search builders is the obvious next lift for watches, cameras and
whisky, which currently fall back to eBay.

Also fixed: `_build_cardmarket_search_url` hardcoded `/en/Pokemon/` for every
category. Cardmarket namespaces its catalogue per game **in the path**, so every
MTG, Yu-Gi-Oh and Lorcana search ran against the Pokémon catalogue.

---

## Status

| Step | State |
|------|-------|
| 1. Enroll networks | ✅ eBay live 2026-10-05 (campaign 5339218687, Business account under the eenmanszaak); ⏳ Impact (TCGplayer/StockX/Whatnot), Partnerize (Catawiki), one aggregator: your hands |
| 1b. Link formats checked against each network | ✅ 2026-09-28 for eBay / Impact / Partnerize; 7 unchecked (class AV) |
| 1c. Every shop tap recorded | ✅ 2026-09-28, gate `check:affiliate-open` (class AW); needs a JS build |
| 2. Rebrand + sub-ID | ✅ done, tests green |
| 3. Reconciliation (table + worker) | ⏳ deferred design (above) |
| 4. Lift routed GMV | ⏳ product, ongoing |
