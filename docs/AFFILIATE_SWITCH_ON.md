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

Each program below maps to one env var in `server/app/config.py:274-289`. An
**empty** var = links are emitted untagged-but-working (no commission, nothing
breaks). Setting the var activates that network's tag immediately on next bake
restart. Apply in this order (rate × your traffic):

| # | Network | Program / Console | Commission | Env var |
|---|---------|-------------------|-----------|---------|
| 1 | eBay | eBay Partner Network (partnernetwork.ebay.com) | 1–4% | `EBAY_AFFILIATE_CAMPAIGN_ID` |
| 2 | Catawiki | Partnerize | ~7–10% | `CATAWIKI_AFFILIATE_ID` |
| 3 | TCGPlayer | TCGplayer Affiliate (direct) | varies | `TCGPLAYER_AFFILIATE_ID` |
| 4 | Master of Malt | Affiliate Future | 5–7.66% | `MASTEROFMALT_AFFILIATE_ID` |
| 5 | PopMart | Yeesshh / Digidip | 1–8% | `POPMART_AFFILIATE_ID` |
| 6 | Whatnot | Impact.com | 1–3.5% | `WHATNOT_AFFILIATE_ID` |
| 7 | Mercari | Impact / Awin | varies | `MERCARI_AFFILIATE_ID` |
| 8 | StockX | Impact | varies | `STOCKX_AFFILIATE_ID` |
| 9 | Cardmarket | direct | varies | `CARDMARKET_AFFILIATE_ID` |
| 10 | Discogs | direct | varies | `DISCOGS_AFFILIATE_TOKEN` |
| 11 | BrickLink | referral | varies | `BRICKLINK_AFFILIATE_ID` |
| 12 | KEH | ShareASale | 1.6–3.2% | `KEH_AFFILIATE_ID` |
| 13 | MPB | FlexOffers / Sovrn | 2% | `MPB_AFFILIATE_ID` |
| 14 | Drop | FlexOffers | 1.6–2.4% | `DROP_AFFILIATE_ID` |
| 15 | Chrono24 | direct partnership | varies | `CHRONO24_AFFILIATE_ID` |
| 16 | AmiAmi | Sovrn Commerce | varies | `AMIAMI_AFFILIATE_ID` |

**To set on EC2**: add the approved IDs to the bake `.env`, then restart bake.
⚠️ Run the preflight chain manually **before** restarting (schema-lock
staleness can take the API down — see MEMORY). Env-only changes don't touch the
schema lock, but the restart will run all gates regardless.

### Per-network sub-ID refinement (optional, during enrollment)
The tag builder carries a per-click sub-ID in `customid` (eBay) / `utm_content`
(everyone else). Most networks pass `utm_content` straight through to their
conversion reports, but a few use their own sub-ID param (e.g. Impact's `subId1`,
ShareASale's `afftrack`, Partnerize's `clickref`). When you read each network's
docs at enrollment, if it has a dedicated sub-ID field, swap `utm_content` →
that param in the matching `_tag_*` helper so attribution survives.

---

## Step 2 — Tag rebrand + per-click sub-ID  ✅ DONE (this change)

`server/app/lib/affiliate.py`:
- All tags rebranded `collectai` → `sparrow`.
- `build_affiliate_url(url, source, subid=None)` now embeds a per-click sub-ID
  (`customid` for eBay, `utm_content` for the rest), defaulting to `"sparrow"`.
- `deal_discovery_agent.py` passes `subid=deal_id` — so every discovered deal's
  link is attributable back to a row in `public.mandate_deals`.

Covered by `server/tests/test_affiliate.py` (18 passing, incl. sub-ID tests).

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

---

## Status

| Step | State |
|------|-------|
| 1. Enroll networks | ⏳ your hands |
| 2. Rebrand + sub-ID | ✅ done, tests green |
| 3. Reconciliation (table + worker) | ⏳ deferred design (above) |
| 4. Lift routed GMV | ⏳ product, ongoing |
