# eBay Marketplace Insights — step-by-step

> **What this unlocks.** Real completed-sale prices with a real sale date. Today
> **99.98%** of our comps are daily price-index snapshots with no sale timestamp,
> and only ~814 PriceCharting rows are genuine sales. This is the single change
> that fixes both §1 and §2 of `docs/COLLECTOR_DEMAND.md`, and the reason
> ~50 categories / ~70k rows are unpriceable. **Re-measured 2026-09-05:**
> watchdog reports 49 categories / 69,251 rows; a direct query the same day
> gives 51 / 69,760 — the 30-day comp window rolls, so treat this as "about
> fifty categories and seventy thousand rows", not a fixed number. It was
> 45 / ~62k when this doc was written, so the gap is **growing**.
>
> **Who does this:** you. It is an application to eBay, in a browser. No code.
> The code side is already written and stubbed at
> `server/app/agents/adapters/ebay_caller.py:410`, where `sold_comps()` returns
> `[]`.
>
> **Expect it to take:** 20 minutes of forms, then **1–6 weeks** of waiting.
> Approval is not guaranteed and is granted per-application.

---

## Before you start — have these ready

| Thing | Where it is |
|---|---|
| eBay developer account | you already have one — the app uses eBay Browse API today |
| Your App ID (Client ID) | developer.ebay.com → **My Account → Application Keysets** → Production |
| Company name | Sparrow Collect |
| KvK number | 99596326 |
| Website | https://sparrowcollect.com |
| Privacy policy URL | https://sparrowcollect.com/privacy |

---

## Step 1 — Confirm you do NOT already have access (10 seconds, no browser)

The browser version of this step ("open the keyset, click User Tokens, read
the scope list") is fiddly and easy to misread. **Ask eBay instead** — the
token service is authoritative: request the scope, and it either issues a
token or refuses.

```bash
ssh collectai
set -a; . /opt/collectors/.env; set +a
B=$(printf '%s:%s' "$EBAY_CLIENT_ID" "$EBAY_CLIENT_SECRET" | base64 | tr -d '\n')
curl -sS -X POST https://api.ebay.com/identity/v1/oauth2/token \
  -H "Authorization: Basic $B" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'grant_type=client_credentials&scope=https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fbuy.marketplace.insights'
```

- `{"access_token": "v^1.1#..."}` → **granted.** Stop; the rest is code-side.
- `{"error":"invalid_scope", ... "exceeds the scope granted to the client"}`
  → **not granted.** Continue to step 2.

Sanity-check the credentials in the same breath by requesting the base scope
(`.../oauth/api_scope`) — that one must succeed. If BOTH fail, the problem is
the keys, not the entitlement, and applying would be the wrong fix.

**Measured 2026-09-06:** base scope issued a token; `buy.marketplace.insights`
returned `invalid_scope`. So: not granted, application required, and the
credentials are fine.

---

## Step 2 — Open the application form (2 min)

⚠️ **Corrected 2026-09-06.** The "Request Access" link this section used to
describe does not exist. eBay's mechanism is the **Application Growth Check**:

> **https://developer.ebay.com/my/support/growth-check**
> (equivalently `…/my/support/tickets?tab=app-check`)

eBay's own docs are titled *"Use the application growth check to get access to
restricted APIs"* — Marketplace Insights is a **Limited Release** API and the
growth check is how you request it.

**Two prerequisites that silently block submission**, and which match an empty
"My Tickets / no support history" page:

1. **Developer account support must be activated.**
2. **At least one contact must be activated.**

If the form will not submit, check those before assuming the request failed.

**Timeline: 3-5 business days** for a first response, 5-7 to conclude — not the
"1-6 weeks" this document used to claim.

⚠️ **Temper expectations.** Community reports from mid-2026 say applicants were
told access is now limited to "major partners". That is **forum hearsay, not an
eBay policy statement** — eBay's docs 403 automated fetches so it could not be
confirmed either way. Apply (it costs ten minutes) but do not plan around
approval.

---

## Step 3 — Fill the form (10 min)

Answer these exactly. Vagueness is the most common rejection reason — they want
a specific, non-competing use.

| Field | What to put |
|---|---|
| API requested | **Buy Marketplace Insights API** |
| App ID | `MerleSle-CollectA-PRD-36c1eb9bb-8723d8ad` (the Production Client ID; also in `EBAY_CLIENT_ID` on EC2) |
| Estimated daily peak calls | **60,000** — one lookup per catalogued item, refreshed daily |
| Estimated hourly peak calls | **3,000** — batched overnight, client-side rate limited |
| Company | Sparrow Collect (KvK 99596326), Netherlands |
| Website | https://sparrowcollect.com |
| Business model | Consumer subscription app, €4.99/month. **We do not resell data.** |
| Are you an eBay seller? | No |
| Do you compete with eBay? | No — we do not operate a marketplace for these goods |

**Use case** — paste this:

> Sparrow Collect is a collection-tracking app for collectibles (trading cards,
> LEGO, figures, vinyl, watches). Members catalogue what they own and we show an
> estimated value for each item.
>
> We currently derive value from catalogue price indices, which are list- and
> trend-based rather than realised sale prices. We want Marketplace Insights
> last-sold data so the values we show members are grounded in what items
> actually sold for, and so we can state the sample size and date range behind
> each figure.
>
> Volume is low: one lookup per catalogued item, refreshed daily, currently
> ~60,000 items. Data is used only to display an estimated value to the member
> who owns that item. We do not redistribute, resell, or expose the data as a
> feed, and we display it alongside a link to the eBay listing.

**Why that wording:** it names a concrete use, states low volume, and says
plainly that you are not reselling the data — the three things they screen for.

---

## Step 4 — Submit and record the ticket (1 min)

1. Submit.
2. **Copy the ticket / case number** into this file under "Status" below.
3. Add the submission date.

---

## Step 5 — While you wait

Nothing is blocked. `sold_comps()` returning `[]` is handled everywhere, and the
app already shows honest provenance for the data it does have.

**If they ask follow-up questions** (common) they usually want: expected calls
per day, whether data is cached and for how long, and whether it is shown to
one user or aggregated publicly. The true answers are: ~60k/day, cached for our
one-month retention window, shown only to the member who owns the item.

---

## Step 6 — When approved, tell me

Then it is code-side and I will do it:

1. Add the `buy.marketplace.insights` scope to the OAuth token request.
2. Implement `ebay_caller.py:410 sold_comps()` against
   `GET /buy/marketplace_insights/v1_beta/item_sales/search`.
3. Write those rows with `is_listing = false`, `ended_at` = the real sale date,
   and `provider = 'ebay'` — the first source at scale whose rows carry an
   actual sale time.
4. The valuation, the "recorded sales" wording and the confidence floor all read
   that automatically; no further change needed.

---

## Status

| | |
|---|---|
| Applied on | _(not yet)_ |
| Ticket number | _(none)_ |
| Outcome | _(pending)_ |

## If they say no

It happens, and it is not fatal. The fallbacks, in order:

1. **Scale PriceCharting** — already done 2026-08-31; 4 categories → 10, and it
   is the one source giving real `ended_at` rows.
2. **TCGplayer partner access** for their sold data (TCG only).
3. Keep the current index data and keep labelling it accurately, which already
   puts us ahead of Collectr and Pokedata on the category's loudest complaint.
