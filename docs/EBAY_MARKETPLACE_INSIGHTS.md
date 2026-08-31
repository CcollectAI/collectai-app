# eBay Marketplace Insights — step-by-step

> **What this unlocks.** Real completed-sale prices with a real sale date. Today
> **99.98%** of our comps are daily price-index snapshots with no sale timestamp,
> and only ~814 PriceCharting rows are genuine sales. This is the single change
> that fixes both §1 and §2 of `docs/COLLECTOR_DEMAND.md`, and the reason
> 45 categories / ~62k rows are unpriceable.
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

## Step 1 — Confirm you do NOT already have access (2 min)

Do this first; it is occasionally granted with other API bundles.

1. Go to **https://developer.ebay.com/my/keys**
2. Sign in.
3. Under your **Production** keyset, click **"User Tokens"** then look at the
   **OAuth scopes** list.
4. Search that page for `buy.marketplace.insights`.

- **If it is there** → you already have access. Stop, and tell me. The work is
  then code-side and I will do it.
- **If it is not** → continue to step 2. This is the expected outcome.

---

## Step 2 — Open the application form (2 min)

1. Go to **https://developer.ebay.com/develop/apis/restful-apis/buy-apis**
2. Find **"Marketplace Insights API"** in the list.
3. Click **"Request Access"** (a link marked *"apply here"* or
   *"Buy API Access Request"*).

If that link is missing or dead, use the general form instead:
**https://developer.ebay.com/my/support/tickets?tab=contact-us** and choose
**"Business Development / API Access Request"**.

---

## Step 3 — Fill the form (10 min)

Answer these exactly. Vagueness is the most common rejection reason — they want
a specific, non-competing use.

| Field | What to put |
|---|---|
| API requested | **Buy Marketplace Insights API** |
| App ID | your Production Client ID from step 1 |
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
