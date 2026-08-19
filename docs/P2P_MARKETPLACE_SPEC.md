# Sparrow Marketplace — user-to-user selling (spec)

**Status (2026-08-07):** Stage 1 **and Stage 2 built and deployed** — schema,
API, and UI. Stage 3 (payments/escrow) remains a proposal and is deliberately
not started.
**Governing decision:** ship **listings without payments** first. Escrow only
after volume proves it earns its operational cost.
**Compliance correction (2026-08-07):** §5 was wrong on two counts — Vinted runs
its own EMI rather than Stripe, and **DAC7 is triggered by Stage 2 as built, not
by Stage 3**. Read **§5a** before planning any payment or logistics work, and
**§5b** for the rule that decides what we may facilitate.

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

**E2E: 40/40 passing** (`server/tests/e2e_p2p_stage2.py`), covering offer →
counter → accept → soft-reserve-does-not-delist → one-sided confirm (grading
still blocked) → two-sided completion → supply row removed → **settlement** →
mutual grading → re-grade edits rather than double-votes.

### Settlement — completion moves the OBJECT, not just the paperwork

Added 2026-08-09. Until then completion updated `p2p_offers`, marked the listing
sold, removed the buyable row and wrote a sold comp — and left `items` untouched.
The seller kept what they had sold; the buyer got nothing. A census of prod found
the only completed trade there had leaked three of the four below.

`_settle_completed_trade` runs before the completion notifications, so a trade
never announces itself while the object is still in the seller's collection:

| # | What settles | Why it is not the obvious thing |
|---|---|---|
| 1 | Seller's item retired — `archived`, or `quantity - 1` if they hold several | Archiving a stack of three would delete two items they still own |
| 2 | Buyer gets a **NEW** row | Reassigning `items.user_id` would hand over the seller's `purchase_price`, `purchase_notes`, `acquired_from` and `cost_basis`. The buyer receives the PUBLIC facts plus what THEY paid |
| 3 | `reserved_offer_id` / `reserved_at` cleared | A completed listing otherwise still reads as reserved |
| 4 | Every OTHER live offer declined + notified | Rival buyers otherwise sit on an open offer for an object that is gone |

`acquired_from = 'sparrow:offer:<id>'` doubles as the idempotency key, so
re-running settlement mints nothing. The seller's photo is copied only under
`photo_catalogue_consent`; otherwise the buyer's item falls back to the
catalogue image. The function never raises — a settled trade is a fact, and
failing to move an item must not 500 a completion that already happened.

**`for_sale` is deliberately not written here.** Trigger `trg_sync_item_for_sale`
recomputes it from the live listing set, scoped to `marketplace_id = 'sparrow'`,
and the caller marks the listing `sold` first, so it has already fired.

**Why archive rather than delete:** 29 tables FK to `items.id`, mostly
`ON DELETE CASCADE` — including `marketplace_listings`, `price_ground_truths`
and `verified_sales`. Deleting a sold item would cascade away the listing and
the exact sold-comp / ground-truth rows the completion had just written for the
model. Archiving keeps the row addressable. `items.archived` is honoured by
reads as of the same date, with `/archived` as the route back
(`npm run check:archived`).

**UI**: `app/offers.tsx` (both sides of every trade in one screen — a member is
usually both), offer ladder on the listing detail, and the confirm/grade
actions. `can_confirm` / `can_grade` come from the SERVER; the client never
re-derives the state machine, because two implementations of one state machine
drift apart.

## 1d-bis. Stage 2 walked on a device (2026-08-08)

The 24/24 E2E proves the state machine. It cannot prove the screens, and Merle's
rule applies: *walking screens catches errors tests don't*. So the whole
transaction was driven on a booted simulator, one stage at a time, against live
prod.

| Stage | What the screen shows |
|---|---|
| offer received | `You sell` · "Waiting for your reply" · Accept / Counter / Decline |
| accepted | "Agreed — take payment, then send the item" (seller) / "Agreed — pay the seller and share your address" (buyer) · `○ Seller sent` `○ Buyer received` · Mark sent / Add tracking / Withdraw |
| seller confirmed + tracking | `✓ Seller sent` `○ Buyer received` · PostNL block · **Mark sent replaced by Edit tracking** |
| completed | "Trade complete" · **Rate the seller / Rate the buyer** appears |
| sold listing | "This listing is no longer available (sold)" · **"1 completed trade"** on the seller card |

**Every status line is written from the reader's side (2026-08-15).** The
neutral wording above was reported as unreadable: *"i don't get 'buying', is
this the user is buying?"*, *"what is 'arrange the exchange'"*, *"'2 needs you'
makes no sense"*, *"'countered, 1 counter' is just not very easy to follow"*.
One status is two different instructions depending on which side you are on, so
`statusLabel(status, iAmBuyer)` in `app/offers.tsx` is the single place that
decides, and the role pill says `You buy` / `You sell` rather than naming a
category. Counter count renders only from the second round on — at one, the
status line has already said it.

### The buyer answers a counter (fixed 2026-08-15)

`counter` overwrites `p2p_offers.amount` with the seller's figure, so a
`countered` offer is **the seller's offer sitting in front of the buyer**. All
three of `accept` / `decline` / `counter` were nonetheless seller-only, which
left a buyer facing a counter with no accept and no decline — `withdraw` was
their only move. The app already disagreed: `offerNeedsMyAction` returns true
for a buyer on a countered offer, so the card was stamped `YOUR MOVE` and
counted in the badge while the only control rendered was Delete. Reported as
*"where is the accept button for example / or reject"*.

**One rule, in `who_may_respond(action, status)`:** whoever did not set the
current number is the one who answers it.

| status | whose number | accept / decline | counter |
|---|---|---|---|
| `pending` | the buyer's | **seller** | seller |
| `countered` | the seller's | **buyer** | seller |

`counter` stays seller-only in both: a buyer raising their own bid is just a new
offer, and letting both sides write `amount` makes "whose number is this?"
unanswerable.

It lives in a named function rather than inside the request handler because the
30 tests around this router inspect SOURCE TEXT — nothing could call the rule,
so nothing checked it, and it stayed wrong through every green run. The tests
now call `who_may_respond` directly, and were confirmed to FAIL against the old
seller-only rule before being kept.

The buyer's controls are **Accept bid** and **Turn it down** (confirmed, like
the seller's Decline — turning a counter down ends the negotiation).

### `i_withdrew` — who walked, as a tri-state

Either side may `withdraw` (a seller may retract a counter), so `status:
'cancelled'` alone never says who. `withdrawn_by` had been written since Stage 2
and returned to nobody; `app/offers.tsx` briefly asserted the buyer always
walked.

`OfferOut.i_withdrew` is `Optional[bool]`, **not `bool`**: `None` means nobody
is recorded as having walked (a row cancelled before that column was written).
Sending `False` there would let the client say "the other side withdrew" on the
strength of a missing value. The client must test `== null`, not `=== undefined`
— it arrives as JSON `null`, which is falsy and otherwise falls straight through
to the wrong branch.

It is read with `_row_opt`, because `create_offer`'s `INSERT ... RETURNING`
cannot join and does not select it — reading it directly would be a 500 on the
primary Stage 2 entry point only.

### Two gaps, stated rather than left to be discovered

**Offers never expire.** `p2p_offers.expires_at` exists, is `NULL` on every row,
is written by nothing in `server/app/`, and no worker expires anything. The
`expired` status is legal and has never been produced. A bid rests until
somebody acts on it. If a deadline is wanted it needs a writer AND a worker —
the column alone changes nothing.

**What the offers screen does about that instead (2026-08-19): nothing that
implies a deadline.** A bid still in play whose last activity is more than
`STALE_AFTER_DAYS` (3) ago carries a *"Still waiting"* marker in
`colors.warning`. That is a real fact about a real timestamp. A countdown would
not be: the FTC's September 2022 dark-patterns report names fake countdown
timers specifically, and a timer on a deadline we do not enforce is exactly
that. **If expiry is ever built, the countdown becomes legitimate and this
marker should be replaced — not kept alongside it.**

Three days, not one: a hobby marketplace is not a trading desk, and a bid that
arrived on Friday should not be shamed on Saturday. It is NOT gated on "needs
you" — a buyer whose bid has sat with a seller for three weeks is not the one
who has to move and is the person most in the dark.

**Counters are capped at five** (`MAX_COUNTERS`, both sides of the wire).
`counter` was uncapped, and every round REWRITES `amount`, so an endless haggle
leaves no history to look back on — just a number that keeps moving. The server
returns 409 `COUNTER_LIMIT`; the client hides the Counter button at the cap and
says why, and leaves Accept and Decline reachable so a capped offer is never
stranded. The two constants are pinned against each other by
`__tests__/lib/counterCapParity.test.ts`, because a comment saying "must match"
is not a gate.

**A seller cannot compare competing bids — CLOSED 2026-08-19, in the offers
list.** The data model allows many offers per listing, and `app/offers.tsx` was
a flat list across ALL your listings ranked by "needs you" then recency, so two
bids on the same item could sit ten cards apart with unrelated trades between
them. `src/lib/offerGrouping.ts` now pulls them adjacent **inside** a section
and draws one banner above the group: *"3 bids on this listing · €28 – €41"*.

Three things about that fix are load-bearing and must not be "simplified":

1. **Grouping happens inside a section, never as a section of its own.** The
   three sections (needs you / waiting on them / closed) are a PRIORITY order.
   A listing-scoped section would outrank that order and sink a member's own
   move below a listing nobody is asking them about.
2. **A group takes the position of its FIRST member**, not of its highest bid,
   for the same reason. Inside the group the highest bid comes first.
3. **The banner carries count and spread, and nothing else.** That is all a
   seller HAS: comparing on *distance* is impossible by construction, since
   addresses are only collectable after `accepted` (§5a).
4. **The count describes the LISTING, not the section.** A seller who counters
   one of three bids splits that listing across two sections — the countered
   bid is "waiting on them" while the other two still need an answer. Counted
   per section the banner said *"2 bids"* while three were live, which is a
   wrong number stated to someone in the middle of choosing. Both calls are
   handed the same population (every active offer); `done` is excluded, since
   a declined bid is not something anyone is still choosing between.

All four are pinned by `__tests__/lib/offerGrouping.test.ts`, which runs in
`verify:prebuild`.

**And grouping is what made the next bug visible.** With three bids stacked
under one banner, one accepted and two still stamped `YOUR MOVE`, the screen
was plainly asking the seller to answer bids for an object they had already
promised. §1d is deliberate that **accept is an agreement, not a lock** — the
listing stays live, the rivals stay `pending`, and `_settle_completed_trade`
only closes them at COMPLETION, which can be a week of shipping later. So the
rivals must NOT be auto-declined on accept; killing the fallbacks would leave a
seller with nothing if the accepted buyer ghosts.

`OfferOut.superseded` splits the two claims that had been fused: the bid is
still live and still answerable (every control stays exactly where it was), and
it is **not your move right now**. `offerNeedsMyAction` returns false for it, so
it leaves the badge, leaves the Home row and leaves the "Needs you" section; the
card recedes to `opacity: 0.72` and says `YOU ACCEPTED ANOTHER BID`. The flag is
checked BELOW `can_confirm` / `can_grade`, or it would silence the confirm
prompt on the accepted trade itself. Pinned by
`__tests__/lib/offerNeedsMyAction.test.ts` and six server tests. The seller framing of the copy is safe by construction: a
buyer sees only their own offers and the server allows one open offer per buyer
per listing (409), so a group can only ever be bids a seller is choosing
between — and all bids on one listing share its currency, so the spread is a
real range.

The offer ladder described in §1d is still not built (`app/listing/[id].tsx`
still says "Stage 1 deliberately stops here: no offers") — the comparison now
happens in the offers list rather than on the listing.

**The offers list dates a card off `updated_at`, not `created_at`** (same
change). Every state transition in `p2p_offers_router.py` already set
`updated_at = now()`; nothing read it, so a haggle opened three weeks ago and
countered yesterday read *"3 weeks ago"* — backwards for the judgement that line
exists to support. `updated_at` is optional on the FE type, so an older server
build falls back to `created_at` rather than rendering blank.


**"Grade" is the stored concept, "rate" is the word on screen.** The table is
`member_grades` and the server flags stay `can_grade` / `already_graded`; only
the label changed, because a member is rating the *person* on the other side,
and "grade" already means condition grading elsewhere in this app.

**No bugs found.** Recording that as a fact rather than a shrug: three things
were confirmed that no test asserts.

1. **The §7 carrier rule is legible.** PostNL renders the code with *"Search this
   code on the carrier's site"* and NO button — because it needs the recipient
   postcode we deliberately do not hold. The E2E asserts `linkable: false`; this
   is what that means to a user.
2. **Two-sided completion explains itself.** The `○ Seller sent` / `○ Buyer
   received` pair makes the model obvious with no copy, and the primary action
   correctly swaps once one side confirms.
3. **Reputation lands at the right moment.** "1 completed trade" appears on the
   seller card immediately after grading — on the same screen that sold the item.

**One detail worth knowing:** the sold listing displays **€420**, the ASKING
price, while the trade completed at **€380**, the AGREED amount. That is correct
and deliberate — the listing shows what was asked, and `_sold_comp_hook` writes
the AGREED figure, which is the one `valuation_worker` consumes (§1g). Verified
in the same walk:

```
Charizard  sold    is_listing=f  380  sparrow_p2p    <- the comp
Bayou      active  is_listing=t  250  sparrow        <- still buyable
```

Prod restored to 0 listings / 0 offers / 0 grades / 0 sparrow hits afterwards.

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

## 1h. Discovery: the entry point was two grey rows (2026-08-10)

Build-order item 6 says "listings surfaced in search". Until today it was not
built, and the marketplace tab carried the whole feature as **two stacked
`memberMarketRow`s** — "Member marketplace" and "Open bids" — identical styling,
chevron on the right. They read as settings entries, so neither was findable.
They are also not the same kind of thing: one is **discovery**, the other is your
own **in-flight negotiation state**.

Three changes:

- **Open bids removed from the marketplace tab.** Not lost — `listings.tsx:682`
  already renders offers as an icon with a live count badge, refreshed on focus.
  A "Browse | My offers" segment was considered and **rejected**:
  `listings.tsx:611-627` records that exact control being removed on 2026-08-07
  because "a first-time user with nothing listed saw a toggle for something they
  do not have". The same objection applies to offers.
- **The remaining entry is a rail of real listings** — photo, title, price. When
  nothing is listed, or the fetch fails, it falls back to the old link row rather
  than showing an empty shelf, for the same reason as the removed segment.
  Catalogue images are labelled "Stock photo": passing stock art off as the
  seller's item hides condition, the one thing a second-hand buyer cannot judge.
- **Listings appear in search**, as a "From members" group above the external
  results. A third element of the existing `Promise.allSettled`, not a new
  effect, so it shares the `searchId` stale-guard — a slow member search cannot
  overwrite a newer query. Only live listings reach it: browse is restricted to
  `delisted_at IS NULL AND status = 'active'`.

⚠️ The empty-state condition counted **three** result sets. With a fourth, a
query matching only a member listing rendered the listing *and* "no results" at
once. Any new result group must be added there too.

⚠️ The rail fetch shipped without an auth gate and 401'd twelve times behind the
login screen — found in the simulator, not by a checker. `/p2p/listings` is
authed; gate any new fetch on `!authLoading && session`.

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
| **PSD2 / payment institution** | Stage 3 only | Stripe Connect Express — Stripe is the regulated party. Never hold funds in our own account. **But Stripe explicitly does not offer escrow** — see §5a |
| **DAC7** (EU platform tax reporting) | **Stage 2 — i.e. NOW.** Not Stage 3 | Corrected 2026-08-07; the earlier "arguably Stage 2" was wrong. `p2p_offers.amount` is communicated to both parties and driven to `completed`, which meets the OECD "reasonably knowable" test with zero money moving. See §5a |
| **DSA notice-and-action** | Stage 1 | Report button on every listing, act on notice, give a statement of reasons. Micro-enterprise exemption covers *some* Art. 19 obligations but **not** notice-and-action |
| **Counterfeits** | Stage 1 | Hosting safe harbour holds only while we stay a neutral host. **Never label a listing "authenticated by Sparrow"** — that forfeits it |
| **Consumer law** | Stage 2+ | Consumer sellers owe no 14-day withdrawal right; traders do. Must not present one as the other |
| **AML** | Stage 3, watches especially | Stripe's KYC covers it; high-value categories need a threshold flag |
| **Apple 30%** | Never | Physical goods shipped between users are outside IAP. Must **not** use IAP for this — that is the rule, not a loophole |

**The unbounded risk is operational, not legal.** Disputes, "not as described",
fakes, shipping. Vinted staffs that with hundreds of people. Stage 1 has none of
it by construction, which is the entire argument for stopping there first.

## 5a. Correction — what Vinted actually is, and what Stage 2 already triggered

Written 2026-08-07 after checking the primary sources rather than reasoning from
the table above. Two things in §5 were wrong.

### "Stripe Connect Express is how you do the Vinted thing"

Vinted does not use Stripe. **Vinted Pay, UAB holds its own electronic money
institution licence** from the Bank of Lithuania (granted 25 Sep 2023), plus a
separate UK EMI licence. The "Vinted wallet" is e-money issuance. Vinted became
the regulated party rather than renting one.

The other two things that make Vinted feel safe are also entities, not features:

| What the buyer sees | What is actually behind it |
|---|---|
| Funds held until delivery | An EMI licence — €350k initial capital (EMD2 Art. 4) is the *floor*, plus fit-and-proper management and an AML function |
| Integrated shipping labels | **Vinted Go** — a separate company, 60+ carriers, ~600k pickup points, which had to **acquire Homerr** to get NL coverage |
| Refund if it doesn't arrive | Buyer Protection (~5% + €0.70, non-optional) funding a staffed dispute org, with a 48h post-delivery window |

And **Stripe does not offer escrow** — its own position is that escrow has a
precise legal definition and Connect is not it. What Connect gives is
*escrow-like* behaviour via manual payouts and delayed transfers (up to 90 days).
That distinction matters when we are the ones writing the terms.

So Stripe Connect covers the *licence*, not the *marketplace*. DSA, DAC7,
consumer law, AML flagging, chargebacks and every dispute still sit with us.

### DAC7 is already live, and it is not about money

DAC7 defines Consideration as compensation *"the amount of which is known or
reasonably knowable by the Platform Operator."* The OECD lists three ways it
becomes reasonably knowable. We hit two of them:

1. **The platform communicates the agreed terms including the amount.**
   `p2p_offers.amount` is shown to both parties, accepted, and driven to
   `status='completed'` by `confirm_exchange` in `p2p_offers_router.py`. This
   is the trigger, and it fires with **no funds flow at all**.
2. *(Not hit, and must stay that way)* the platform commits to a refund or other
   buyer protection. This is the second reason never to offer one — see §5b.

The third — withholding a commission set against the amount paid — we do not hit
for the marketplace, but note that `app/legal/terms.tsx:159` already claims a
**5% platform fee on event tickets**. Whether ticketed events are a DAC7
relevant activity is genuinely arguable; the clause predates the marketplace and
should be looked at in the same conversation.

**The mitigation is proportionate, which is the point.** The NL de-minimis
excludes sellers under 30 sales *and* under €2,000/yr, so at our volume
essentially every seller is an Excluded Seller and the report is near-empty. The
cost is registration plus enough data to *demonstrate* exclusion — not a tax
operation. But it has to actually exist.

**Action:** a Dutch tax adviser on the registration question **before the
marketplace has real users**, not before Stage 3. One conversation, not a
retainer.

## 5b. The facilitation rule

> **Sparrow may know everything and do nothing.**

Every risk above comes from one of two things: becoming a **party to a contract**
(carriage, payment, guarantee), or **assuming an obligation** (refund,
adjudication, verification). Neither is triggered by knowing, displaying, or
introducing — which is where nearly all the user value is anyway.

"Zero risk" is not reachable and is the wrong target: DSA is live at Stage 1 and
DAC7 at Stage 2, both bounded and both already incurred. The target is **no new
regulated activity, no assumed obligation, no unbounded liability.**

| We may | We may not |
|---|---|
| Deep-link out with the amount prefilled — a hyperlink is not payment initiation under PSD2 Art. 4(15); the user's own PSP initiates the order | Hold funds, even momentarily. There is no de-minimis |
| Compare payment rails **neutrally** (reversible vs not) | Say "we recommend X" — that is a representation |
| Record a payment *claim* the seller asserts | Issue a receipt in Sparrow's name |
| Capture a tracking code and link to the **carrier's own** page | Auto-complete a trade from carrier status — see below |
| Hand over addresses between parties after `accepted` | Generate labels under a Sparrow carrier account — that makes us the contracting party for carriage |
| Show `completed_trades`, a fact about platform history | Show a "Verified Seller" badge — that is a representation about a person |
| Point at the payment rail's own dispute process | Mediate, or offer any refund or guarantee |
| — | Arrange shipping insurance. That is insurance distribution under IDD. The seller buys it from the carrier |

**The trap that looks free: auto-completing on tracking status.** If we poll a
carrier and flip `buyer_confirmed_at` on "delivered", we have substituted our
judgment for the buyer's — and we own it when the box arrives empty. Tracking is
**display-only**; `confirm_exchange` stays the only writer of those columns. This
is the same class as never labelling a listing "authenticated by Sparrow".

**What this buys.** Two-sided confirmation plus mutual grading is the Vinted
trust model minus the money — their 48h window is an automated "buyer confirms",
and we already have the manual version. Tracking visibility and address hand-off
close most of the *felt* gap while the licence, the subsidiary and the support
org stay on their side of the line.

### Sources

- [Bank of Lithuania — EMI licence granted to a subsidiary of Vinted](https://www.lb.lt/en/news/electronic-money-institution-licence-granted-to-a-subsidiary-of-vinted)
- [Vinted — Vinted Pay receives UK EMI licence](https://company.vinted.com/newsroom/vinted-pay-receives-UK-EMI-license)
- [Silicon Canals — Vinted Go acquires Homerr](https://siliconcanals.com/vinted-go-acquires-homerr/)
- [Stripe Docs — Using manual payouts](https://docs.stripe.com/connect/manual-payouts)
- [Belastingdienst — DAC7 for platform operators](https://www.belastingdienst.nl/wps/wcm/connect/en/business/content/information-for-platform-operators-dac7)
- [MTCA — DAC7 Guidelines (consideration definition)](https://mtca.gov.mt/docs/default-source/documents/top-bar/eservices/international/dac7/dac-7-guidelines-final.pdf)

## 1g. The closed loop — a completed trade is a sold comp (built 2026-08-07)

The marketplace was designed to feed Target Hit with **supply**. It also
produces something rarer, and until 2026-08-07 it threw it away.

`valuation_worker` selects `WHERE is_listing IS NOT TRUE` — it consumes **sold**
data and deliberately ignores asking prices. Every row P2P wrote was
`is_listing = TRUE`. So on two-sided completion the code deleted the buyable row
and recorded nothing about what the item actually sold for.

That is the exact data the pipeline is starved of. **~62,000 catalogue items
have no price at all for one reason**: `ebay_caller.py:387 sold_comps()` returns
`[]`, so those categories have no sold-comp source. A completed Sparrow trade is
a real sale, at a price both parties confirmed, on an item that already carries
a canonical identity.

`_sold_comp_hook` now writes it on completion:

| Field | Value | Why |
|---|---|---|
| `price` | **`p2p_offers.amount`** | The AGREED figure after any counter. `marketplace_listings.price` is what was hoped for; storing the ask as a sale biases every prediction upward |
| `is_listing` | **`FALSE`** | What makes valuation_worker read it at all |
| `source` | `sparrow_p2p` | Separable forever — the lever to exclude P2P prices, and the way to measure the marketplace's contribution |
| `item_ref` | `category:canonical_key` | Namespaced, same as the publish hook |

Awaited, not fire-and-forget: a lost buyable row is a non-event (the listing is
gone anyway), a lost sale cannot be reconstructed. Idempotent via `WHERE NOT
EXISTS`, because `market_hits` has no usable unique key.

Verified on prod: asked €250, agreed €180, comp recorded **180**, and the row
matches valuation_worker's predicate exactly.

### The manipulation surface, stated plainly

Two colluding accounts can complete a trade at any price and inject a comp. For
an item with many comps the median absorbs it. **For one of the 62k items with
zero other comps, a single fake sale becomes the entire price** — which is
exactly where manipulating pays best.

This ships anyway, because the data is worth having and is fully auditable
(`listing_id` traces to both parties). `source = 'sparrow_p2p'` is the filter to
pull if predictions start looking wrong:

Audit from **`p2p_offers`, not `market_hits`** — `PARTITION_RETENTION_MONTHS_MARKET_HITS=1`,
so a `market_hits`-based query goes blind after a month and would read as "no
P2P comps" exactly the way §6's supply count read as "no supply". `p2p_offers`
keeps completed trades permanently, and both parties are on the row:

```sql
-- Every member sale that fed valuation, with who traded and how isolated it was.
SELECT o.created_at, o.amount, o.currency,
       l.category || ':' || l.canonical_key AS item_ref,
       o.buyer_id, o.seller_id,
       (SELECT count(*) FROM public.market_hits m
         WHERE m.item_ref = l.category || ':' || l.canonical_key
           AND m.is_listing IS NOT TRUE
           AND m.source <> 'sparrow_p2p') AS independent_comps
FROM public.p2p_offers o
JOIN public.marketplace_listings l ON l.id = o.listing_id
WHERE o.status = 'completed' AND l.canonical_key IS NOT NULL
ORDER BY independent_comps ASC, o.created_at DESC;
```

`independent_comps = 0` is the row to look at: that sale is setting a price by
itself. A repeated `(buyer_id, seller_id)` pair across several such rows is the
collusion signature.

**Confidence is protected separately.** `valuation_worker`'s `diversity_factor`
counts distinct sources, so a member sale would otherwise have counted as an
independent market and raised the model's stated confidence as well as its
price. `sparrow_p2p` is excluded from that count — it still contributes its
price and to `n`, but it cannot make us more sure of a number a colluding pair
chose.

## 5c. The C2C boundary is load-bearing — and currently undefended

Researched 2026-08-07, against the regulations rather than from memory.

### What being purely C2C buys us

Both **GPSR** and **DSA Arts 29–32** define an online marketplace the same way:
an intermediary that lets consumers conclude distance contracts **with traders**.
A platform where every seller is a consumer falls outside *both*.

| Regime | Applies to a marketplace | Applies to Sparrow today |
|---|---|---|
| GPSR (in force 13 Dec 2024) — internal safety procedures, Safety Gate registration, seller traceability | yes, if traders sell | **No** — no traders |
| DSA Arts 29–32 — trader traceability / KYBC | yes, if traders sell | **No** — no traders |
| GPSR obligations on the *seller* | traders only | **No** — consumers selling second-hand owe nothing |
| DSA Arts 16–17 — notice-and-action, statement of reasons | **every hosting provider** | **Yes**, regardless of size |

GPSR *does* cover second-hand goods, so "it's all used collectibles" is not the
reason we are out of scope. **Being C2C is.**

### Why that is fragile

`app/legal/marketplace-terms.tsx` says *"You must identify yourself as a trader
if you are one."* That is self-declaration with no detection and no consequence.
One member selling regularly for profit pulls us into GPSR marketplace
obligations and DSA trader traceability at once — and we would not know.

**This is exactly the boundary Vinted polices.** Vinted Pro verifies a business
registration number at sign-up, and where Vinted sees trader-like signals —
sales pattern, volume, sourcing — it *requires* conversion to Pro and **blocks
accounts that refuse**. Their C2C side stays genuinely C2C because something
enforces it. We have the clause; they have the mechanism.

**Recommended, and deliberately not Vinted's pipeline:** a threshold alert to
the founder (e.g. N completed sales by one member in a rolling year), so we
learn we have a trader before a regulator does. That preserves the posture at
near-zero cost. Building verification, Pro accounts and trader disclosure is
Stage 3-scale work and is not justified until the alert actually fires.

### What was built instead (2026-08-07)

Two gaps that were real regardless of the trader question:

- **Blocking now covers the marketplace.** `user_blocks` was enforced only in
  chat, so a blocked member's listings still showed and they could still send
  offers. Apple App Review Guideline 1.2 asks for blocking *from the service*.
  One shared implementation in `app/lib/blocks.py`; chat delegates to it.
- **DSA Art 17 is implemented.** `listing_reports` had carried `status`,
  `resolution_note` and `resolved_at` since Stage 1 with nothing writing them.
  `POST /ops/listing-reports/{id}/action` now resolves reports, removes the
  listing, awaits the supply hook, and writes a statement of reasons to the
  seller — all in one transaction, so a removal cannot stand with the seller
  un-notified.

### Still open

- **Apple 1.2 has two limbs we do not meet**: no filtering of objectionable
  material in listing titles/descriptions, and no 24-hour action commitment in
  the terms. The report path and blocking are done; these are not.
- **Trader detection**, per above.

## 6. Build order

1. `P2P_MARKETPLACE_ENABLED` flag + `marketplace_id = 'sparrow'` seed
2. Create-listing flow from an owned item (reuse `ListForSaleModal`)
3. `market_hits` write on publish / stale on delist ← **the supply hook**
4. Listing detail + "Message seller" → existing chat
5. Report button + takedown path (DSA)
6. Listings surfaced in search + catalog item page
   — **search half DONE 2026-08-10**, catalog item page still open. See below.
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

**Run this THIRD query or the first two will lie to you** (added 2026-08-07):

```sql
-- Did members not list, or did the hook skip them?
SELECT count(*)                                                   AS listings,
       count(*) FILTER (WHERE canonical_key IS NOT NULL
                          AND category IS NOT NULL)               AS could_reach_target_hit,
       count(*) FILTER (WHERE canonical_key IS NULL
                           OR category IS NULL)                   AS skipped_no_canonical_key
FROM public.marketplace_listings
WHERE marketplace_id = 'sparrow';
```

`_publish_supply_hook` writes nothing when a listing has no canonical identity —
correct, because a weakly-identified buyable row can only match the fuzzy title
arm, which is where the false positives live. But **measured 2026-08-07, only 4
of 16 `items` carry a `canonical_key`**, so the hook skips the majority, and the
first query counts that as zero supply.

Zero buyable `sparrow` rows therefore has two completely different meanings —
"nobody listed" and "everybody listed and we skipped them all" — and only the
third query separates them. Deciding *"do not build Stage 2 or 3"* off the first
query alone would be deciding on the wrong number.

The skip now logs at WARNING (it was INFO, inside a 90MB file of INFO) and
`ListingOut.reaches_target_hit` exposes it per listing, so the seller is told at
the time rather than discovering their listing reached nobody.

> **Where the server logs actually go.** `collectai-bake.service` sets
> `StandardOutput=append:/opt/collectors/bake.log` — **not** journald. `journalctl -u
> collectai-bake` shows systemd's own lines and none of the application's, which
> reads exactly like "the code never ran". Grep `/opt/collectors/bake.log`.

If `sparrow` is not a meaningful share of Target Hits after a month of Stage 1
**and `could_reach_target_hit` is healthy**, then the supply thesis genuinely
failed: **do not build Stage 2 or 3.** If `skipped_no_canonical_key` dominates,
the thesis was never tested — fix catalogue matching on `items` first and re-run
the month. Offers and escrow multiply the operational load
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

- ~~Shipping: display-only in Stage 1, or structured (carrier/price) from day
  one?~~ **Answered 2026-08-07: structured, but display-only.** `ships_from` and
  `shipping_cost` already exist on the listing; `tracking_carrier` /
  `tracking_code` were added to `p2p_offers`. We capture and display, and never
  become a party to the carriage — see §5b. Note that PostNL and DPD deep links
  need the **recipient's postcode**, which we deliberately do not hold, so those
  carriers render a copyable code and no link rather than a link that 404s.
- ~~Geography: NL-only first? Cross-border consumer law is materially harder~~
  **Answered 2026-08-09: worldwide.** The app ships worldwide, so terms written
  as if EU/NL were the only jurisdiction were simply wrong for most readers. The
  legal screens were rewritten to name EU/UK rules as EXAMPLES of a general
  pattern rather than as the universe, and the governing-law carve-out now
  protects any consumer's mandatory local rights, not only an EU consumer's.
  Sparrow remains established in NL, which is a fact about where we report — not
  a limit on who may use the marketplace.
- Does a `sparrow` listing count toward the free plan's watchlist/alert caps, or
  is listing always free? (Recommend: listing always free — supply is the point)

## 8. What actually made Vinted work — and which parts we can copy

Researched 2026-08-08. §5a already covers what Vinted **is** structurally (an
EMI licence, a logistics subsidiary, a staffed dispute org). This section is the
other question: what did they *do* that made the marketplace work, and which of
it is available to us under §5b's facilitation rule.

Sorted by leverage for **this** app, not by how famous the feature is.

### 8a. The finding that reframes everything: they were supply-constrained

Vinted was written down to **zero** by investors in early 2016. The turnaround
was one decision: **remove seller fees entirely.** Their read was that the
marketplace was not short of buyers, it was short of *listings* — and that
casual sellers offloading low-value items were the liquidity engine, while a
seller fee was taxing exactly that behaviour. Supply rose sharply and the
flywheel (more listings → more buyers → better matching → more listings) started
turning.

This is the same diagnosis §1 reaches from a completely different direction:
**we are building this for supply, and should judge it on `market_hits` created,
not GMV.** Two independent routes to one conclusion is the strongest signal in
this document.

**What it forbids, concretely:** never charge to list, and never count a
`sparrow` listing against a plan cap. The open question at the end of §7 —
"does a sparrow listing count toward the free plan's watchlist/alert caps?" —
is answered by this: **no.** Metering supply is the 2015 Vinted mistake.

### 8b. Price drops alert watchers — BUILT 2026-08-08

On Vinted, dropping a listing's price **pushes a notification to every member
who favourited or viewed it**. It is the single most recommended seller action
in every guide, because it converts stored interest into a sale on demand.

We had the better half already and could not use it. `p2p_listing_router.py` had
exactly three write endpoints — create, delist, report — and **no price edit of
any kind**. A seller who wanted to drop their price had to delist and relist,
and forgetting to delist first returned `409 ALREADY_LISTED`, which reads as the
app being broken.

| Piece | Us | Status |
|---|---|---|
| Stored interest | a `watchlist_items` row with a **target price** | built (watchlist, catalog item page) |
| The alert rail | Target Hit, which already fires on price | built |
| A way to change a listing's price | `PATCH /p2p/listings/{id}` | **built 2026-08-08** |

**Ours is stronger than Vinted's**, because a watchlist row carries a *target*:
we do not notify everyone who saved the item, we notify the people whose declared
target the new price now meets. That is Target Hit firing on a member listing —
the whole thesis of §1.

#### How it works, and what it deliberately does NOT add

No new alert type, no new worker, and **no `user_price_alerts` row**.
`docs/alerts-and-insights.md` records that the Rules tab is empty *by design*,
that the watchlist target IS the rule, and that re-adding a writer there has now
been the same bug three times.

`_check_watchlist_snipes` already selects `market_hits` rows with
`seen_at > now() - interval '30 minutes'` and `price_eur <= w.target_price`. So
`_price_change_hook` re-points the listing's existing buyable row at the new
price and refreshes `seen_at`. The next cycle matches it against every watcher
whose target the new price meets, with the existing 24h-per-watchlist dedupe and
plan gating already applied. The hook knows nothing about users.

Three decisions worth keeping:

- **UPDATE, never INSERT.** The publish hook guards with
  `WHERE NOT EXISTS (provider='sparrow' AND listing_id=…)` precisely because a
  second buyable row makes Target Hit surface one listing twice. Verified on
  prod that the UPDATE works even when `seen_at` moves the row across a monthly
  partition boundary.
- **A price RISE corrects the row but does not refresh `seen_at`.** "Listed
  below your target" is the promise; waking someone because an item got more
  expensive is a notification with no action — what the 2026-08-06 consolidation
  deleted three workers to stop doing.
- **Price only.** Title, category and `canonical_key` decide what the listing
  *is*; editing those after members have watched and been alerted turns one
  listing into a different product with the same history.

#### The pull side: `GET /p2p/watchlist-matches`

The marketplace and the watchlist were built separately and never met on screen.
Someone could be watching a Bayou while another member had one listed, and only
a push firing at the right moment would connect them. This is the same join with
no time window and no alert: open your watchlist, see what is buyable now.
Rendered on `app/(tabs)/wishlist.tsx`, accented only when the member's own
target is met.

Exact-identity matches only — deliberately **not** the snipe's trigram title
fallback. That arm exists so free-text rows can still fire an alert and is tuned
at 0.55; an alert that is occasionally loose is recoverable, but a permanent row
asserting "a member is selling this" about the wrong item is not.

#### Not built: the Vinted heart

A favourite heart on the grid tile was built and then **removed 2026-08-08** at
Merle's decision. Adding to the watchlist stays where it already is — the item
page and the watchlist screen. Two traps found while it existed, which apply to
any future version of this control:

1. The optimistic fill and the `watchers` count disagreed, because the count was
   the raw server figure. At zero watchers the number was hidden entirely, so a
   freshly-hearted tile showed a filled heart and no count at all.
2. It wrote a watchlist row with **no target price**, and
   `_check_watchlist_snipes` requires `target_price IS NOT NULL AND > 0` — so
   every row it created was inert while its own label promised alerts. Any
   one-tap "watch this" control must set a target or say plainly that it has not.

### 8c. Freshness decays, and that is the point

Vinted gives a new listing a visibility boost that **fades within a couple of
days**, which is why sellers who list a few items several times a week beat
sellers who dump thirty and vanish.

We sort `created_at DESC` by default, which is the same thing at our volume —
there is no reason to build decay for a grid that fits on one screen. Worth
knowing that the mechanism is *decay*, not recency, before anyone tunes ranking
later.

**Bump / Wardrobe Spotlight — paid visibility — is NOT free money for us.**
Checked against the actual guideline 2026-08-08 rather than reasoned about, and
the wording is decisive. Apple's rule names this case explicitly:

> "Digital purchases for content that is experienced or consumed in an app,
> **including buying advertisements to display in the same app** (such as sales
> of 'boosts' for posts in a social media app) must use in-app purchase."

A Sparrow bump is a seller buying an advertisement displayed in Sparrow. That is
the named case, not an analogy. Physical goods between users stay outside IAP
(§5) — the ITEM is untaxed, the PROMOTION is not.

This is settled precedent, not a grey area: Apple added the clause in October
2022 aimed at Meta, and from February 2024 boosting a post in the Facebook or
Instagram iOS app is billed through Apple with a 30% charge. Meta's response was
to tell advertisers to buy outside the app, which is the only real workaround and
is pure friction for a solo founder to build.

**And it cuts against §8a anyway.** Vinted's own numbers: Buyer Protection is
~75–80% of revenue, and bumps/spotlights/ads are the minority slice of €1.1bn
(2025). So the stream that actually funds Vinted is the one §5b forbids us
outright, and the small stream is the one Apple taxes at 30% *and* that §8a
identifies as a seller fee wearing a different hat — the exact thing that nearly
killed them in 2015.

Conclusion: **do not build paid bumps.** Not because of the 30% alone, but
because it is a small, taxed, strategically wrong stream. Sparrow's marketplace
is judged on `market_hits` created (§1), not on marketplace revenue — the
revenue lives in the subscription the supply makes worth buying.

### 8d. Listing completeness is measurable, and ours is thin

Two numbers worth designing against:

- listings with **4+ photos sell ~3.5× faster** than single-photo listings
- **complete** listings get **3–4× more views** than incomplete ones

`app/sell/new.tsx` holds a single `photoUri: string | null` — **one photo, no
more.** `item_images` supports many (it is keyed on the item, and takes a
`label`), so this is a client limit, not a schema one.

The Sparrow-specific twist: the field that matters most here is not one Vinted
has. **`canonical_key` is what decides whether a listing can reach Target Hit at
all**, and `sell/new.tsx` never sends one — so a marketplace-only listing is
currently invisible to the alert that is the reason the marketplace exists.
`reaches_target_hit` reports this back honestly, and the screen shows the notice,
but honesty about a dead end is not the same as a way out of it.

### 8e. Trust: we must build the felt half without the funded half

Buyer Protection is *why* buyers trust strangers on Vinted — money held until
the buyer confirms, with a refund path. §5b forbids all of it, and §5a records
the second reason: committing to buyer protection is DAC7 trigger #2, which we
must not hit.

So the trust model has to be built from facts we already hold, never from
representations we would then owe:

| Vinted | Sparrow equivalent | Why it is allowed |
|---|---|---|
| Money held until delivery | two-sided `confirm_exchange` | both parties assert; we adjudicate nothing |
| Refund on "not as described" | **nothing, said plainly** | the listing screen states there is no buyer protection |
| Ratings | `member_grades` → `completed_trades`, `seller_positive_pct` | a fact about platform history, not a badge about a person (§5b) |
| Verified seller | **never** | that is a representation, and it forfeits hosting safe harbour |

Their 48h auto-confirm window is an automated "buyer confirms". We have the
manual version, and §5b explains why the automated one is a trap: auto-completing
on carrier status substitutes our judgment for the buyer's, and we own it when
the box turns up empty.

### 8f. Ranked backlog out of this

1. ~~**`PATCH /p2p/listings/{id}` for price**, wired into Target Hit~~ —
   **DONE 2026-08-08** (§8b), along with the pull side,
   `GET /p2p/watchlist-matches`.
2. **Catalogue match in the sell flow**, so a marketplace-only listing can carry
   a `canonical_key` and actually reach Target Hit (§8d). Now the top item: with
   the price rail built, this is what decides how many listings can use it.
   `sell/new.tsx` never sends a `canonical_key`, and the item-id path inherits
   from the item, which usually has none either — measured 4 of 16.
3. **Multi-photo listing** in `sell/new.tsx` (§8d). Client-side only.
4. Never meter or charge for listing; close §7's open question as "always free"
   (§8a).
5. Explicitly **not doing**: paid bumps (§8c), buyer protection (§8e), anything
   in §5b's right-hand column.

### Sources

- [Sharetribe — How does Vinted make money?](https://www.sharetribe.com/how-to-build/how-does-vinted-make-money/)
- [Vinted Help — What is an item Bump?](https://www.vinted.com/help/340-what-is-item-bump)
- [Vinted Help — The Vinted Refund Policy](https://www.vinted.com/help/465-the-vinted-refund-policy)
- [Vinted — Trust and safety](https://www.vinted.co.uk/safety)
- [Zipsale — How the Vinted algorithm works](https://www.zipsale.co.uk/blog/how-the-vinted-algorithm-works-2026-tips-to-get-more-views-sales)
- [Vinta.App — Vinted Buyer Protection: what sellers need to know](https://blog.vinta.app/blog/vinted-buyer-protection-sellers-guide)
- [Sharetribe — Vinted revenue mix (Buyer Protection ~75–80%)](https://www.sharetribe.com/how-to-build/how-does-vinted-make-money/)
- [CNBC — Apple's App Store rules on boosted ads (Oct 2022)](https://www.cnbc.com/2022/10/26/apples-new-app-store-rules-over-boosted-ads-provoke-facebook-again-.html)
- [AppleInsider — Meta billed through Apple for boosts from Feb 2024](https://appleinsider.com/articles/24/02/15/apple-and-metas-latest-fight-is-over-social-media-boosted-post-fees-on-iphone)

## 9. Deal Desk removed, DAC7 implemented (2026-08-09)

### 9a. Three generations of the same feature — two deleted

The app had grown **three** implementations of member-to-member trading. Only
the third had ever carried a trade:

| Gen | Tables | Code | Rows | Fate |
|---|---|---|---|---|
| 1 | `agreements`, `ratings` | none at all | 0 | **deleted** |
| 2 | `listings`, `offers`, `offer_events`, `offer_evidence`, `deal_ratings` | router + 6 RPCs + 2 screens + 20 tests | 0 | **deleted** |
| 3 | `marketplace_listings`, `p2p_offers`, `member_grades` | P2P Stage 1+2 | 19 / 4 / 2 | **live** |

Generation 2 ("Deal Desk") shipped behind `SELLING_ENABLED=false` and never
completed a single trade. Its cost was not runtime, it was attention: every
schema, RLS, account-deletion and orphan-store audit carried entries a reader
had to recognise as expected-dead — which is precisely how a gate stops being
read. Two of its screens were still reachable, from Settings and from the item
bar, so a user could walk into a subsystem that could not complete a trade.

### 9b. The near-miss: "deal" means two different things

The removal's real risk was vocabulary, not dependencies. **`deal_discovery_worker`
drives Target Hit — the paid alerting feature — and shares the word "deal" with
Deal Desk while sharing nothing else.** It reads and writes `purchase_mandates`,
`mandate_deals`, `watchlist_items`, `alert_trigger_history`, `market_hits` and
`subscriptions`; it touches none of the seven dropped tables. Its only
occurrences of "offers"/"listings" are prose in a docstring.

Two more things looked like Deal Desk and were not:

* **`src/api/dealsApi.ts`** held BOTH the Deal Desk offer calls and the
  purchase-**mandate** calls. Deleting the file — the obvious move — would have
  broken the live mandate feature. It was split, not deleted.
* **`dealsProvider.toggleForSale`** drives `items.for_sale`, which a DB trigger
  keeps in sync with live listings. Kept.

An FK is not a feature boundary, and neither is a filename.

### 9c. What was rescued rather than deleted

Deal Desk's `execute_complete` called `record_price_ground_truth`; the P2P
completion path did not. Deleting Deal Desk would have quietly dropped the model
**calibration** loop. It never carried data (0 completions), but the wiring was
the good part, so it moved to `_ground_truth_hook` in `p2p_listing_router.py`.

This is **not** a duplicate of the neighbouring `_sold_comp_hook`, and the two
are easy to confuse:

| hook | writes | consumer | answers |
|---|---|---|---|
| `_sold_comp_hook` | `market_hits` | `valuation_worker` | what is this item worth? |
| `_ground_truth_hook` | `price_ground_truths` | calibration | how wrong was our forecast? |

Same input price, two different consumers. Dropping either loses something the
other cannot supply. `_ground_truth_hook` needs `marketplace_listings.item_id`,
so a marketplace-only listing (§5c) correctly records nothing — calibration
needs a predicted item.

The price-outlier detection from `deal_risk.py` had already been ported into
`p2p_offers_router` (§ price sanity). Its seller-trust half was deliberately not
ported: `member_grades` already answers that.

### 9d. DAC7 — a written promise that had no code behind it

`app/legal/marketplace-terms.tsx` §6 told members, in writing, that above the
threshold we would ask them for details and warn them before reporting. **Nothing
implemented that.** No counter, no notice, and no way to demonstrate that
everyone else was below the line — which §5a identifies as the actual cost of
compliance ("registration plus enough data to DEMONSTRATE exclusion").

`dac7_seller_year` (user_id, year) is that data, accrued by `_dac7_accrue` on the
completion path — the only moment consideration becomes KNOWN, which is what
triggers DAC7 in the first place.

**The rule, and the one thing that can be wrong.** A seller is an EXCLUDED
SELLER only when BOTH limbs hold: fewer than 30 sales **and** at most EUR 2,000
in a calendar year. So a seller becomes reportable when **either** is breached:

```
reportable  ⇔  sales_count >= 30  OR  gross_eur > 2000
```

Writing `and` there would under-report every high-volume/low-value seller — 40
sales at EUR 20 is the exact shape that slips through — and nothing would
notice, because the failure mode is silence. `server/tests/test_dac7_thresholds.py`
pins both single-limb cases and both boundaries; the connective was
mutation-tested (`or` → `and` fails 4 tests) rather than assumed.

Other deliberate choices: amounts converted to EUR before comparison (the limit
is EUR-denominated); `notified_at` guards against re-warning on every subsequent
sale; `reportable_at` is never cleared, because crossing is a fact about the year
that a later refund does not undo; and every failure is swallowed and logged —
a completed trade must not 500 because a compliance counter could not be written.

### 9e. Verification performed

Before dropping: row counts on all seven tables (0), FKs into the set from
outside (`ratings -> agreements` only, itself in the set), dependent views
(`v_offer_summary_v1`), functions referencing the set (exactly 6 RPCs, resolved
by `oid::regprocedure` — **not** by guessed signatures, since a wrong signature
makes `DROP FUNCTION` a silent no-op that still reports success), and triggers.

After: all seven tables and the view gone, 6 RPCs gone, survivors intact with
their rows; `schema.lock` and `rpc.lock` regenerated and installed on EC2 **and**
in the repo; the 9-stage preflight chain run manually and passing 9/9; service
restarted; `/healthz` 200; `/deals/*` → 404 and `/p2p/*` → 401.

Two failures were caught by that chain rather than by a user, and both were
real: `preflight_rpc_lock` still named the 6 dropped RPCs (my first lock diff
compared top-level JSON keys instead of function names, and wrongly reported "no
change"), and `preflight_router_drift` correctly refused a DB whose tables no
longer matched the deployed code. Neither would have been visible without
running the gate.

## 10. Six user-reported defects, and what they were instances of (2026-08-09)

Every one came from Merle *using* the app, not from an audit. Each turned out to
be an instance of a class, so each fix ends in a gate rather than a patch.

### 10a. The carrier picker was dead on every open

"Carriers don't load on add tracking." `GET /p2p/carriers` served 9 carriers to
curl the whole time and prod hash-matched the repo, which is why reading the
network layer found nothing. The effect guarded on `carriersState !== 'idle'`
**and listed `carriersState` in its dep array**, so `setCarriersState('loading')`
changed a dependency of the effect that had just set it; React tore it down and
the cleanup set `cancelled = true` while the request was in flight. `.then` and
`.catch` both no-op'd and the sheet sat on "Loading carriers…" with the retry
unreachable, because the error branch never rendered.

Its own comment asserted the opposite — *"bounded by construction — httpClient
aborts every fetch at REQUEST_TIMEOUT_MS — so this cannot hang on 'loading'
forever."* A timeout bounds the REQUEST; the request was never the problem.

Gate: `npm run check:effects`. Rule: **a state value an effect writes can never
be that effect's own dependency.** Guard belongs in a `useRef`, retries on a
separate nonce.

### 10b. Listing from your collection asked for everything again

"It does not take the already filled in information from the item card… this is
double work." The composer opened blank *and* the server was only inheriting
three fields:

```sql
SELECT id, name, category, canonical_key, image_url   -- that was all
```

`condition_label`, `condition_notes` and `listing_description` came from the
request only. Prefilling the form would have papered over that and left
`SellOnSparrowSection` still dropping them, so the fix is server-side:
`_inherit_from_item(sent, *from_item)` — request wins where it says something,
the item fills the silence, one direction only so clearing a field on the listing
does not get the item's old value pushed back. Blank-after-strip counts as
silence, because `""` is how an untouched input arrives.

Copied **field-for-field, never composed**: brand/year/series exist and are
deliberately left out. Assembling a description out of them would be writing
sales copy in the seller's name.

The wiring test earned its keep: the binds were already correct while
`return ListingOut(...)` still handed back `payload.description`, so the row would
hold the item's description and the 201 would claim it was empty.

### 10c. Route params: the navigation axis had never been swept

`app/sell/pick.tsx` passed only `itemId`. Writing a checker for the *shape*
instead of fixing the instance found **five more** dead handoffs — including
"Add to watchlist" on the barcode scanner, which pushed `mode: 'watchlist'` to a
screen that has no watchlist mode, so it opened the empty **collection** form and
would have filed the item as owned.

`typedRoutes` is on, but every static route is typed `params?:
Router.UnknownInputParams` — an open record — so a wrong key is legal TypeScript,
and 49 `as Href` casts erase even the pathname check. Gate: `npm run
check:params`, comparing against the destination's **declared** params.

### 10d. Offer amounts: presets with no percentages and no way out

Both ladders were `Alert.alert` with hardcoded multipliers and money-only labels
(buyer 0.9/0.8/0.7, seller 1.1/1.2/1.35). Neither limitation was a product
decision — `Alert.prompt` is iOS-only, so a free-text amount was impossible in
that container.

`src/components/p2p/OfferAmountSheet.tsx` is one component for both sides:
−10/−5/+5/+10 with the percentage AND the money on each chip, plus a custom field
that shows the percentage of whatever you type and enforces the server's own
`gt=0, le=1_000_000`.

**The counter's reference is the ASKING price, not the buyer's offer.** Against
the buyer's own offer, "−5%" means *less than they already offered* — a button no
seller would press. That required `listing_price` on `OfferOut`; the
`INSERT … RETURNING` cannot join the listing, so that path sets it from the row it
already fetched and the mapper reads it through a KeyError-tolerant helper.

### 10e. Seller profiles are tappable — gated on the stricter of two views

`seller_profile_public` is `EXISTS` against `user_public_profiles`, never a copy
of its rule. **There are two profile views and they differ:**

| View | Condition | Used by |
|---|---|---|
| `user_public_profiles` | has a name **AND** `allow_discovery` not off | search / find-collectors |
| `user_public_profile_v1` | has a name | the profile SCREEN |

Gating on the stricter one respects a member who turned discovery off, and
because its condition implies the screen's, a tap that is offered can never
dead-end on an empty profile. Present in BOTH listing queries, since a column in
one read by a mapper used from both is a KeyError on whichever path was missed.

### 10f. DAC7 is inform-only — and the terms had promised otherwise

§6 and the crossing notice both said we would *"ask you for the details the rules
require."* There is no form and **no column anywhere** for a TIN, address, date of
birth or IBAN — a promise with no mechanism, the same shape as §6 itself before
2026-08-09. Both now inform instead, and `app/tax-reporting.tsx` (Settings →
Sales & tax reporting) shows a member their own counters, the thresholds from the
SERVER, and that reporting above them is a legal requirement on marketplaces
rather than a Sparrow policy.

`GET /p2p/dac7/me` is authed and self-only — no `user_id` parameter exists,
because another member's tax exposure is not something this router will answer.

**What informing does NOT do:** discharge the operator's own duty if a seller
becomes reportable. Nobody is reportable today (0 completed trades), the counters
demonstrate exclusion, and the watchdog now pages when that changes — but
registration and the 5% ticket-fee question remain for the adviser (§5a).

`dac7_reportable()` is now module-level and shared by the accrual, the endpoint
and the tests. The test file had defined its **own copy** of the predicate, so the
suite would have stayed green if `or` had become `and` — the one thing it exists
to prevent. Mutation-proven: that flip now fails 4 tests.


## 11. Navigation: the Market tab IS the marketplace (2026-08-11)

The tab called **Market** opened a discovery hub — search bar, find-collectors,
open bids, demand heat, movers — and the member marketplace sat one tap deeper
behind a row on it. Same name-vs-destination mismatch as the old "Search" tab
that opened the marketplace: the word on the bar did not describe the screen it
produced.

| before | after |
|---|---|
| Market tab → discovery hub → row → `/listings` | Market tab → the listings grid |
| Browse-by-category on the Market tab | on the **Search** tab, as its idle state |
| hub = `app/(tabs)/marketplace.tsx` | hub = `app/market-hub.tsx`, **deleted 2026-08-12** |

`(tabs)/marketplace.tsx` is now a wrapper rendering the SAME component as
`/listings` with `asTab` — one marketplace, not two that drift. `asTab`
suppresses the back chevron and the in-body `QuickNavBar`, neither of which
belongs on a tab. Identical pattern to `(tabs)/search.tsx`.

**The hub was parked for a day, then dissolved (2026-08-12).** It was kept only
until each of its modules had an answer, because deleting it while it still held
the last of them is the bug this work exists to fix:

| module | outcome |
|---|---|
| Market Movers | moved to the Market tab, under the grid, `!query` only |
| Regional insights | moved **with its loader** (`src/hooks/useRegionalDemand.ts`) |
| Demand heat | **deliberately not moved** — `app/analytics.tsx` renders it behind `advanced_analytics`; a free copy would have given the paid feature away |
| Open bids | deleted. A summary card whose only job was to link to `/offers`; the Market tab already carries the labelled Offers pill with a needs-you badge |
| Find Collectors | deleted. Behind `COMMUNITY_GATED`, rendering nothing (<50 public profiles ⇒ 0 results), duplicating the user search `/search` already runs |

Deleting the screen also stranded seven components nothing else imported
(`DemandHeatBanner`, `MarketplaceFilterPanel`, `MarketplaceSearchBar`,
`MarketplaceResultCard`, `MarketplaceEmptyState`, `MarketplacePageHeader`,
`SearchResultQuickView`); they went with it rather than being left as a feature
reachable from nowhere.

⚠️ **The "view all marketplace results" link on item detail**
(`MarketplacePricesSection`) now pushes **`/search?q=`**, and specifically not
`/(tabs)/search`. This link has had three targets and the constraint never
changed: it must land somewhere that RUNS a query and READS `q`.

`check-route-param-handoff` caught the sharp edge twice. First when it pushed
`?q=` at `/(tabs)/marketplace`, which after the swap reads no params — the query
would have been silently dropped. And it is why the target is `/search` rather
than the Search tab: the gate resolves a push target to its route FILE, and
`(tabs)/search.tsx` is a one-line re-export with no `useLocalSearchParams` of
its own, so pushing there would report "that route reads: (none)" and this
contract would stop being checkable. `app/search.tsx:229` reads it.

**New gate:** `npm run check:reachable`
(`scripts/check-unreachable-screens.mjs`) builds the push/`Link`/`Redirect`
graph over `app/**` and reports screens with no inbound edge — the question
`check-dead-nav` cannot answer, since it only proves a target RESOLVES, never
that anyone can arrive. Verified against this very case: with `market-hub.tsx`
restored and its entry point repointed, the gate names it. It is **advisory**
(exit 0) like `audit_orphan_tables.py`, because it currently reports a backlog
of four pre-existing orphans — `/franchise/[id]`, `/sell/dashboard`,
`/sets-to-complete`, `/twitch`. Flip `--strict` on and add it to
`verify:prebuild` once that list is empty.

### 11a. The offers screen — deciding, not just listing

`app/offers.tsx` showed Accept / Counter / Decline as three near-identical
buttons, and Decline fired instantly.

- **The percentage sits under the amount.** "EUR 380" is neither good nor bad
  until you know you asked EUR 428. Rendered only when the server sent a
  `listing_price` — a computed "0%" would be a claim we cannot back. Same
  reference as the counter sheet: the ASKING price, never the buyer's own offer
  (§10d).
- **Decline confirms.** It cannot be undone on that offer, and it sat one
  mis-tap from Accept.
- **Hierarchy:** Accept fills, Counter outlines in accent, Decline recedes to
  plain `danger` text. Per docs/ui-playbook.md, the amount dropped `xl` → `lg`:
  with the percentage line beneath it, the figure no longer carries the
  comparison alone.

`OfferAmountSheet` was NOT rebuilt — it already does percentage+money presets
with a bounded custom field.

### 11b. The offers screen, second pass (2026-08-19)

Driven by published practice rather than taste — eBay's Seller Hub offers page,
Mercari and Depop's offer tabs, NN/g on card-vs-list, NN/g on progressive
disclosure, Apple's HIG on swipe actions, and the FTC's dark-patterns report.
Grouping, `superseded`, staleness and the counter cap are documented above; the
rest:

- **Finished trades collapse to a reference row.** A closed offer used to render
  the full card — thumbnail, title, amount, percentage of asking, two pills,
  status, quoted message, tracking block — all de-emphasised and none of it
  actionable. docs/ui-playbook.md, "a list card is a reference row, not a call
  to action". One line now: thumbnail, title, outcome, age, amount, still
  opening the listing. The card is kept for anything still in play.
  - Two paths died with it and were REMOVED rather than left: `styles.cardDone`
    and the card's `already_graded` line. `already_graded` implies a completed
    trade, which is terminal and not `mine`, so it can no longer reach the card
    — an unused branch left behind is how a dead path survives a cleanup.
  - The `offerId` deep-link highlight was re-applied to the history row. A push
    asking you to rate a trade lands you on that trade; once rated, the card
    collapses, and without this the one row the push was about arrived looking
    like every other line of history.

- **A truncated list says so.** The client sent no `limit`, so the server
  defaulted to 50 and returned the 50 NEWEST — with nothing on screen admitting
  it. "Needs you" includes ungraded completed trades, which are old by
  construction, so the row most likely to fall off the bottom was one that still
  wanted something. The client now asks for the server's ceiling (200) and
  `OfferListResponse.total` lets the footer state the shortfall. The count is
  computed in the same `acquire()` with the **same predicate** as the page — a
  total that disagrees with the list is worse than no total.

- **Swipe left to decline**, seller-side, on an open offer only. eBay's API
  allows declining many offers in one call and never accepting many, because a
  decline is a sweep and an accept is a commitment: **a gesture must not be able
  to sell something.** It shares `confirmDecline` with the button rather than
  carrying its own copy of the confirm, and the button remains as the
  non-gesture equivalent that both docs/gesture-navigation.md and the HIG
  require.

- **"N bids need you" on Home** (`src/components/home/OpenBidsRow.tsx`).
  `countOffersNeedingAction` had exactly one caller — the marketplace badge — so
  a bid waiting on an answer was invisible unless you opened that tab or caught
  the push. A ROW, not a card: Home has twice shed accreted cards on purpose
  (Deal Agent moved out 2026-08-11, the Insights CTA deleted), and this renders
  `null` when nothing is waiting. Above the chart, not at the bottom of the
  scroll, where set progress and the ad slot live. `useFocusEffect`, not
  `useEffect` — Home stays mounted, and the first version would have kept
  advertising bids you had already answered.

**Known cost, stated rather than discovered:** Home and `/listings` each call
`GET /p2p/offers` purely to count, and that endpoint runs a `market_hits`
aggregate per distinct item for `price_verdict`, which neither caller uses —
now over up to 200 rows rather than 50. Harmless at current volume and worth a
`?price_sanity=false` branch before it isn't. Not fixed by having the counters
request fewer rows: a count from a truncated page is the bug above.

## 5e. Settle-up handoff — payment and carriage, by region (2026-08-14)

Both halves of finishing a trade now link OUT. Sparrow is a directory in each
and a participant in neither, which is what keeps §5a's line intact.

**Payment** — `server/app/lib/payment_rails.py`, `GET /p2p/payment-rails`.
Region resolves from `user_settings` server-side (not the client, so two members
cannot see different lists because one has a stale build), falling back to the
global rails when unset or unknown — showing a Dutch member Zelle is worse than
showing them fewer options.

| region | rails |
|---|---|
| europe | Bank transfer (SEPA), Bizum, PayPal, Revolut, Swish, Tikkie, Wise |
| americas | Cash App, Interac e-Transfer, PayPal, Revolut, Venmo, Wise, Zelle |
| japan / korea / oceania | local bank transfer or PayID, plus PayPal and Wise |
| other | PayPal, Wise |

Three properties are load-bearing, not styling:

1. **Alphabetical order.** A pinned or preferred first entry is a representation
   about a payment provider. `rails_for_region` sorts and the client renders in
   the order it is given; a test would be worth adding if anyone reorders.
2. **`reversible` is the only comparison we make**, and §5a names it explicitly.
   PayPal is the one `null` — Goods & Services carries buyer protection,
   Friends & Family does not, and that difference is how people get burned.
3. **The disclaimer renders with every list**, not once at onboarding.

**Carriage** — `_CARRIER_BOOKING` beside `_CARRIER_TRACKING`, same keys, exposed
on `GET /p2p/carriers` as `book_url` + `regions`. The link opens the carrier's
own flow; the seller buys carriage in their own name and pays the carrier
directly. europe gets 10 carriers, americas 5, the rest the global integrators.

### What is deliberately NOT built

- **No amount prefill.** `paypal.me/<handle>/<amount>` needs the seller's
  handle and no column holds one — the only handle columns in the live schema
  are display names. The amount renders `selectable` instead. §5a permits the
  prefilled deep link, so this is a missing column, not a missing permission.
- **No payment state.** Sparrow never learns whether money moved. Completion
  stays the two-sided human confirm; a "paid" flag we did not witness would be
  a representation.
- **No labels under a Sparrow account, no insurance, no auto-complete on
  carrier status.** Those are the three lines in §5a, and each is one API call
  away from being crossed by someone trying to be helpful.

### The deploy-order trap

`book_url` is new. Until the server ships, `GET /p2p/carriers` returns rows
without it, the client filters every one out, and the ship sheet renders its
empty state. That is honest but reads as a bug — deploy the server before the
build that shows this sheet.

## 5f. The logistics half — delivery address, EU and US (2026-08-14)

The counterpart of the payment handle. Payments needed the seller's handle
before a link could carry the amount; carriage needs the buyer's address before
a shipment can be booked at all.

`p2p_offer_addresses` (migration 20260814b), **per offer, not per user**. An
address is given for one trade with one person and dies with it: cascade from
`p2p_offers` on trade deletion, cascade from `auth.users` on account deletion.
A reusable address book would keep home addresses alive indefinitely for a
feature that needs them for a week. Before this table the app held no postal
address anywhere — the only address-shaped column in `public` was
`beta_signups.ip_address`.

| Endpoint | Who |
|---|---|
| `PUT /p2p/offers/{id}/address` | **Buyer only**, and only once `accepted` — §5a permits handing addresses over *after* acceptance, and collecting one earlier means holding a home address for a trade that may never happen |
| `GET /p2p/offers/{id}/address` | Either party of a live trade. This is the ONLY path by which a seller sees it; the table is buyer-only under RLS |

**EU and US differ in exactly one field.** `state` is required for the US and
absent from most of Europe, enforced in the router rather than as a CHECK —
baking one country's postal grammar into the schema is how the next country
becomes a migration. A US address without a state is rejected at write time,
because a carrier rejecting it after the seller has bought postage is worse.

### What this unlocks: PostNL tracking

`_CARRIER_TRACKING["postnl"]` was `None` for one reason — its public page takes
`barcode-COUNTRY-POSTCODE` and we held no postcode. With an address, the link
builds. `_tracking_url` takes optional `postcode`/`country` and returns **None**
when a template needs them and they are absent, so the client falls back to the
copyable code exactly as before. A half-built URL is the worse failure: it looks
tappable and 404s, which reads as "Sparrow lost my parcel".

DPD stays `None` deliberately — it also wants a postcode, but its consumer URL
format is not documented well enough to guess, and the payment-rails rule
applies: a guessed format 404s at the worst possible moment.

Every query feeding `_row_to_offer` now joins the address and selects
`delivery_postcode` / `delivery_country` through the shared `_OFFER_COLUMNS`
chokepoint — verified that all four users of that constant carry the join, so
adding the columns there could not orphan a caller.

### The sweep that had been red for months was a false positive

`test_every_p2p_offers_query_feeding_the_serializer_has_tracking` failed on the
rival-offer auto-decline: `RETURNING buyer_id, amount, currency`, consumed by a
notify loop reading exactly those three. It never reaches the serializer, so
demanding five tracking columns there would have added columns nothing reads.

Two fixes, both making the sweep stricter:

- **Split on `await conn.` AND `await pool.`.** Only conn was split, so every
  pool query's text bled into a neighbouring chunk — which is how the new
  address endpoints made an unrelated DAC7 chunk "fail".
- **A `RETURNING` without `id` cannot feed `_row_to_offer`**, which opens with
  `str(r["id"])`. Every real feed selects it.

Proved by breaking it: dropping `tracking_set_at` from `_OFFER_COLUMNS` fails
immediately.

### 5e-bis. Two of the five payment links were invented (corrected 2026-08-14)

The rails module's own rule — *"guessing a format produces a link that 404s at
the worst moment"* — was written in the same commit that broke it. Checked
against the providers' documentation afterwards:

| Rail | What shipped | What is actually documented |
|---|---|---|
| PayPal | `paypal.com/paypalme/<h>/<amt><CUR>` | ✅ format right; `paypal.me` is the canonical domain |
| Venmo | `venmo.com/<h>?txn=pay&amount=` | ✅ documented — **and `audience` defaults to PUBLIC** |
| Revolut | `revolut.me/<h>/<amt><CUR>` | ❌ **invented.** Only `revolut.me/<tag>` exists; links are generated in-app |
| Cash App | `cash.app/$<h>/<amt>` | ❌ **invented.** Only `cash.app/$<cashtag>` |
| Wise | `wise.com/pay/me/<h>` | ✅ no amount, as documented |

Revolut and Cash App now link to the person and nothing more. The buyer types
the figure, which is what they did before any of this existed.

**`audience=private` on Venmo is the find that matters.** Venmo posts payments
to a social feed and defaults to public, so a prefilled link would have
broadcast to the buyer's followers what they bought and from whom. A marketplace
has no business making that public by omission.

Three more corrections in the same pass:

- **`pay_url_has_amount`**, because the client said "amount filled in" beside
  every built link. For Revolut and Cash App that sent a buyer looking for a
  figure that was never there.
- **Zero-decimal currencies.** `f"{amount:.2f}"` renders JPY 1000 as `1000.00`,
  which is a different number to a provider parsing the path. JPY and KRW —
  exactly the two zero-decimal currencies the app supports — now format without
  minor units.
- **Rate limits.** Both new write endpoints shipped without the
  `_rl=Depends(_offer_limit)` that every other write in the router carries.

### 5f-bis. One question, one source: carrier region moved server-side

`/p2p/payment-rails` resolved region from `user_settings` while the booking list
was filtered on the CLIENT against device settings. Two sources for the same
question, which diverge the moment a member changes region on another device.

`/p2p/carriers` now takes `?region=`, defaults to `user_settings.region`, and
filters server-side. An unknown region filters NOTHING rather than everything —
an empty carrier list reads as "Sparrow does not ship where I live".

`region=all` is the escape hatch and the tracking picker uses it: recording a
code is a fact being entered, not a choice being made, and a seller who shipped
with a carrier outside their region must still be able to type its number in.

---

## 12. Ratings reach the profile and the tile (2026-08-18)

Asked for as *"i want it possible to have your trade rating visible on your
profile and the same should be reflected when you are offering products for
sale on the marketplace… just like uber you need to be able to be rated and
hand out ratings as both the buyer and seller"*.

**The two-sided half already existed.** `member_grades` takes a grade from
EITHER party of a completed trade, anchored to `offer_id` and unique per rater
(§1d), and `app/offers.tsx` renders "Rate the seller" / "Rate the buyer" off the
server's `can_grade`. That is the Uber shape minus the stars, and the stars stay
off deliberately: completion is two self-confirmations, not a settled payment,
so a 4.7/5 would imply a precision the data cannot carry (§8e). Confirmed with
Merle before building — **thumbs stay, `positive_pct` stays hidden below 3
grades.**

What was missing was everywhere the rating was supposed to be READ.

| surface | before | after |
|---|---|---|
| listing DETAIL | "92% positive · 12 trades" | unchanged |
| member PROFILE (`/users/[userId]`) | nothing | `TradeReputationSection` |
| marketplace TILE (`/listings`) | seller name only | name · 92% (or · N trades) |
| `GET /p2p/members/{id}/reputation` | **zero callers** | the profile section |

### The endpoint had been built and reached from nowhere

`getMemberReputation` shipped with Stage 2, was exported through
`collectorsApi.p2pMemberReputation`, and had **no call site in the app**. The
listing screen showed the same numbers by a different query, so a rating you
left appeared on the seller's *items* and never on the *seller*
([[learning_complete_feature_reachable_from_nowhere]]).

### The tile was worse than empty — it was ready to lie

`ListingOut` has carried `seller_completed_trades` / `seller_positive_pct`
since Stage 2, and **only the detail query selected the underlying columns**.
The browse response therefore served Pydantic's defaults. Rendering the field
on the tile without touching the query would have printed **"0 trades" for
every seller on the platform**, with nothing erroring anywhere — `unknown-as-zero`
wearing a reputation.

Both queries now share `_SELLER_REPUTATION_SQL` and both mappers go through
`_reputation_fields(r)`, so the threshold and the rounding are defined once.
`server/tests/test_p2p_listing_router.py::TestSellerReputationReachesBrowse`
pins it and was **proven to fail against the old browse query** before being
kept.

### Splitting the SQL exposed a read the gate had never seen

Concatenating the shared fragment turned one string literal into three, and
`check:archived` reports per literal. The detail query had been passing only
because its `WHERE l.id = $1` made the whole literal look like a by-id lookup —
so `seller_collection_size` had been counting **archived** items all along.
Settlement archives the seller's item when a trade completes, so that number
credited a seller for everything they had already sold. Now
`AND si.archived IS NOT TRUE`. The gate found a real bug by being made able to
see the query, which is the argument for keeping gates literal-scoped.

### What is still deliberately not shown

- **No stars, no score, no "verified seller".** §5b's right-hand column is
  unchanged; the profile section renders `completed_trades` and a percentage
  and nothing else.
- **No client-side percentage.** The FE must never divide
  `positive_grades / total_grades` to fill the gap below the threshold — that
  re-derives a rule the server owns and publishes exactly what the threshold
  exists to withhold.
- **Nothing renders at zero.** `TradeReputationSection` returns null until the
  member has a trade or a grade: on a pre-launch marketplace an
  always-rendered card would be an empty grey box on every profile in the app.
