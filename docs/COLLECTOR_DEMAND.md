# What collectors complain about — demand-side research

> Written 2026-08-30. Weighted to Sparrow's live categories: the six
> valuation-eligible TCGs (`mtg, pokemon, yugioh, digimon, one_piece_tcg,
> lorcana` — `src/constants/categories.ts:159`) first, then LEGO, anime
> figures, vinyl and whiskey, which appear in real user holdings.
>
> **Deliberately negative.** Asked for as *"what they are missing or complaints
> are — this is more important than the really positive things."* Praise for
> competitors is omitted unless it names a gap in ours.

## ⚠️ Method, and its one big limitation

**Reddit could not be read.** `reddit.com` blocks this crawler outright
(HTTP 400, "domains are not accessible to our user agent"), so nothing below
comes from the subreddits, and this document should not be described as Reddit
research. What replaced it: competitor **1–2 star reviews**, review
aggregators, category blogs, and one quantitative teardown. That skews toward
*articulate* complaints and away from casual grumbling — treat frequencies here
as directional, not measured.

If Reddit evidence is wanted specifically, it needs a human to pull threads, or
an API route with credentials. Do not let a future reader assume it was covered.

---

## 1. The finding that matters most: nobody says which price they measured

TCGinvest priced **one identical 25-card Pokémon collection** four legitimate
ways and got **$17,148 → $27,516 — a 60% spread**. Across 3,049 cards the same
exercise gave $136,241 → $213,270 (57%).

| method | total |
|---|---|
| Lowest ask (EU) | $27,516 |
| Median completed sales (US) | $21,350 |
| Modelled estimate (US) | $19,670 |
| Trend line (EU) | $17,148 |

**No app was wrong. They measured different things and none of them said so.**
Their conclusion is the sentence to design against:

> *"If an app cannot tell you which of those three it used, its total is a
> number without a question attached."*

Neither Collectr nor Pokedata disclosed pricing method or sales counts on the
cards examined, and both ran **7–25% above the 180-day completed-sale median** —
i.e. showing *what someone wants*, not *what someone paid*.

**Sparrow's position:** this is the one place we are already ahead.
`value_source` shipped end to end on 2026-08-19 and the item card renders a
provenance chip. ⚠️ But per that project note, **the column names lie** — so the
chip's correctness is not something to assume. If we market on transparency, the
provenance path needs a test that discriminates, not a glance.

## 2. Thin markets break the single-number promise — and every tail category is thin

Cards with **fewer than 31 completed sales showed a 2.46× median gap** between
pricing methods, vs 1.82× for liquid cards. *"The more vintage and thinly-traded
your collection is, the further apart different pricing methods become."*

Discogs shows the same failure from the other side: a release with **no prior
Discogs sales contributes zero** to collection value, so obscure-heavy
collections are "vastly underestimated" — and its median **ignores condition
entirely**, mixing Fair and Mint copies in one number.

**Sparrow's position:** q10/q50/q90 and the `_MIN_COMPS_FOR_MODEL = 3` floor with
a confidence cap below it are the right shape for this — an interval and an
admission beat a confident point estimate. The constraint is data, not design:
as last measured, **19,992 of 20,000 valuations had fewer than 3 comps** (so the
model is bypassed for essentially everything) and 45 categories / 61,727 rows
were unpriceable at all.

⚠️ **Those two figures are carried forward, not re-measured for this document.**
Before quoting them anywhere external, re-run the comps-per-valuation
distribution over `v_price_predictions_latest_with_valuation_key_v1.comps_count`.
Everything else in this file is sourced to a link below.

## 3. A 31% geographic gap nobody surfaces

EU and US markets price identically-valued cards ~31% apart — before any
methodology difference. An app on EU data and an app on US data disagree by a
third and neither mentions it.

**Sparrow's position:** 7 currencies ship, but currency conversion is not the
same claim as *which market this price came from*. Worth checking whether the
provenance chip distinguishes marketplace region; if it does not, that is a
cheap, defensible differentiator.

## 4. Database gaps with no manual escape hatch — the most common single complaint

Across every category, the same shape: the item is missing, **and there is no
way to add it yourself**, so the collection total is silently wrong.

| category | what is missing |
|---|---|
| Yu-Gi-Oh | "missing a lot of the high end stuff… no option to add them manually" |
| Pokémon | Japanese promos, Chinese cards/packs, Red Cheeks Pikachu (Base Set), most play-stamped cards |
| Whiskey | mainstream bottles absent (e.g. Glenlivet 12 Double Oak) — "makes tracking pretty worthless" |
| Vinyl | anything never sold on Discogs contributes **zero** |
| Figures | MFC search "clunky af"; short names and unpopular tags return only the top 10 |

Note the asymmetry: a **missing item** is an annoyance, but **a missing item that
silently contributes €0** is a wrong number presented as a right one. That is
our own `learning_empty_answer_rendered_as_zero`, shipped as a product.

## 5. Cost basis is the universal blind spot — and the clearest unserved need

Collectors in the $2,500–10K/year range *"track card prices and values but not
their true cost basis."* People who have spent $5,000+ cannot state profit after
grading, shipping and tax.

The worked example is the whole pitch:

> $900 card + $56.25 tax = **$956.25 basis**. Sells for **$1,000** — looks like
> profit. After eBay's 13.25% + $0.30 and $15 shipping, net is **$852.20**: a
> **$104.05 loss** on an apparent gain.

Why it fails: *"start tracking with good intentions, then let it fall behind and
give up"* or never start. The barrier is manual entry across disconnected
platforms — no app consolidates purchase, fees, grading submissions and sale.

**Sparrow's position — verified in code while writing this.** `cost_basis` and
`unrealized_pl` do ship (`app/analytics.tsx`, and the item card at
`app/item/[id].tsx:1285`), built from `purchase_price` / `purchase_price_eur` /
`purchase_currency`. But a grep for `grading_fee`, `shipping_cost`,
`marketplace_fee`, `tax_paid` and `fees` across `src/api/types.ts` and the item
card returns **nothing**. So our basis is the purchase price alone — exactly the
$900-not-$956.25 error in the example above, and it produces the same false
profit on sale.

Nobody in this research has solved the fee-and-tax-aware net position, it is the
most concrete "collectors would pay for this" signal found, and it needs **no new
data source** — it is arithmetic over fields the user already enters, plus a
per-marketplace fee table we can hardcode.

## 6. Grading: narrow support, and a feature that half-works

Collectr **supports PSA only** — no BGS, CGC or Beckett — and its *"Grading Price
is not currently functional: adding a graded card kind of works, but it will not
calculate price."*

**Sparrow's position:** we have no PSA/CGC integration either, and the FE was
shelved 2026-05-02 for exactly the right reason. The lesson from Collectr is that
**shipping a half-working grading feature is worse than not shipping it** — their
users cite it as a specific grievance. Staying shelved is validated; if it is
ever revived, condition→value must actually compute or it earns the same review.

## 7. LEGO: no tracker does purchase price, ROI, condition, or sealed-vs-used

Measured across the category's own comparison writeups:

| tool | gap |
|---|---|
| Brickset | retail prices only — **cannot tell you what a retired set is worth today**; tracker has no purchase price, no ROI, no condition, no market value |
| BrickEconomy | investor-grade data but **web only, no native app**, no scanning, machine-estimated values |
| Rebrickable | reference only — no pricing, no scanning, "not a portfolio tracker" |
| BrickLink | its own 6-month sales only; no collection tracking |
| Brickit | build ideas only; **"no identification for value, no pricing"** |

> *"None track purchase price, ROI, condition grades, or sealed vs. used."*

This is the widest open gap found in any live category, and it is the same
cost-basis theme as §5. Sealed-vs-used is a **condition axis LEGO valuation
cannot work without** — worth checking whether our schema can even express it.

## 8. Monetization complaints — what makes people angry

- **Taking a free feature behind a paywall** draws the sharpest reviews:
  OnlyDrams moved following friends and marking finished bottles to $5/mo and
  users called it out by name. Ties directly to
  `learning_shelving_a_feature_leaves_the_paywall_selling_it` — the inverse
  error, equally visible.
- **Free tiers capped by item count** frustrate before the value is felt.
- **Paying for accuracy that is not accurate** is the compounding one: a
  subscription for "real-time pricing" that shows asking prices is the complaint
  behind most 2-star pricing reviews.

**Sparrow's position:** our €4.99 Pro sells *unlimited watchlist, Target Hit
alerts, deal discovery, set completion, market prices, no ads*. Nothing there is
"pay to see accurate numbers", which is the right side of this line. Keep it
there — gating **provenance** or **confidence** would land us in §8's third
bullet immediately.

---

## Verified against the codebase (2026-08-30)

Every row below was checked in code or on prod, not inferred from the research.

| # | Complaint | What Sparrow actually does | Verdict |
|---|---|---|---|
| 1 | Apps show asking prices as value | `valuation_worker.py:315` filters `AND (is_listing IS NOT TRUE)`, which excludes 310,759 rows flagged as listings. **But the corpus it admits is NOT completed sales** — see the correction below | **⛔ CORRECTED — we have the same problem** |
| 1b | Nobody discloses method or sample size | `catalog-item/[key].tsx:281` says *"Median of N recent comps"*. The **item card does not** — `ValueSourceChip` collapses `catalog_daily`/`catalog_model`/`quick_scan` into one label, "Market estimate" | **Right disclosure, wrong screen** |
| 2 | Thin markets break a single number | q10/q50/q90 in `PriceBand`, `_MIN_COMPS_FOR_MODEL = 3`, `_LOW_COMP_CONF_CAP` below it. `CompSource` carries `source`, `count`, `avgPrice`, `dateRange` | Design ✓, **data ✗** |
| 3 | EU/US markets differ ~31% | 7 currencies convert, but nothing states **which market** a comp came from | **Gap** |
| 4 | Missing item, no manual escape hatch | `app/add-manual.tsx` exists; the `/catalog/match` lookup is **advisory, never required** | ✓ **already solved** |
| 5 | Cost basis ignores fees and tax | `cost_basis` + `unrealized_pl` ship from `purchase_price`. `grading_fee`, `shipping_cost`, `marketplace_fee`, `tax_paid` — **none exist** | **Gap — biggest opportunity** |
| 6 | Half-working grading draws 2-star reviews | Shelved 2026-05-02, no PSA/CGC API, FE imports removed 2026-08-30 | ✓ **correct as-is** |
| 7 | No LEGO purchase price / condition / sealed-vs-used | `CONDITION_OPTIONS_GENERAL = ['Not set','Mint','Near Mint','Excellent','Good','Fair','Poor']` — a **card-grading vocabulary applied to every non-TCG category** | **Gap** |
| 8 | Paywalling free features / paying for accuracy | Pro sells caps and access, never accuracy. Audited and gated 2026-08-30 | ✓ **right side of the line** |

### The two that change what we build

### ⛔ CORRECTION (same day): our comps are not completed sales

This document first claimed *"91.4% of comps are completed sales — we sit on the
sold median by construction."* **That was wrong**, and it was wrong in the exact
way the research condemns: a column called `is_listing` was read as if the name
settled the question, without checking what the rows are.

Measured on prod, over the 3.31M rows that `is_listing IS NOT TRUE` admits:

| provider | rows | share | `observed_at` NULL | `ended_at` NULL |
|---|---|---|---|---|
| scryfall | 1,608,058 | 48.6% | **1,608,058** | **1,608,058** |
| tcgplayer | 945,688 | 28.6% | **945,688** | **945,688** |
| cardmarket | 723,739 | 21.9% | **723,739** | **723,739** |
| lorcast | 32,520 | 1.0% | **32,520** | **32,520** |
| ebay | 1,002 | 0.03% | 1,002 | 1,002 |
| pricecharting | 815 | 0.02% | 1 | 1 |

**99.98% of the comps feeding valuations carry no sale timestamp at all.** A
completed sale has a time. These are **catalogue price-index snapshots** from
Scryfall / TCGplayer / Cardmarket price APIs — roughly 49 rows per card for
scryfall, 28 for tcgplayer, 22 for cardmarket. Only **814 pricecharting rows**
have a real `ended_at`.

Three consequences:

1. **We cannot say "median of N completed sales."** `catalog-item/[key].tsx:281`
   already says *"Median of N recent comps"* — where N counts snapshots. That
   copy is closer to misleading than to the differentiator it looked like.
2. ~~Temporal decay is still collapsed.~~ **ALSO WRONG — corrected same day.**
   `valuation_worker.py` selects `COALESCE(observed_at, seen_at)` precisely for
   this case, and **`seen_at` is populated on 100% of rows** (2026-08-01 →
   08-30, the retention window). Decay works. The real, narrower defect:
   `upsert_market_hits` never wrote `sold_at` into the row, so the three
   importers that supply the SOURCE'S OWN price date — `import_pokemon`
   (TCGplayer + Cardmarket `updatedAt`) and `import_lorcana` — had it silently
   discarded, and those rows decayed on *when we fetched* instead of *when the
   price was computed*. Fixed 2026-08-30.
3. **The honest claim is different and still good.** TCGplayer Market Price and
   Cardmarket trend are sales-derived indices, and Scryfall republishes both. So
   the truthful label is *"market price index, TCGplayer/Cardmarket"* — not
   "asking price", not "completed sales". That is a real answer to §1's
   *"which of those three did you use"*, and it is one we can state today.

**What §1 becomes:** not "advertise that we use sold data" (we largely do not),
but "state the method we actually use, name the provider, and stop counting
snapshots as if they were sales." That is still the cheapest high-value change
here — it is now a *correctness* fix as well as a marketing one.

**§7 is `learning_a_ported_gate_carries_the_wrong_vocabulary` in the schema.**
"Mint / Near Mint / Excellent" is TCG language. A **sealed** LEGO set and an
opened-but-perfect one are both "Mint" and are not the same asset. The same break
hits every non-TCG live category: whiskey (fill level, seal, box), vinyl (sleeve
and disc grade **separately** — precisely the Discogs complaint in §2), figures
(box vs figure). One condition list cannot carry four vocabularies.

## What this implies, ranked

1. **Make provenance the product claim, and prove it.** §1 is a category-wide
   failure and we have the mechanism already. Verify the `value_source` chain
   with a discriminating test first — the column names are known to lie.
2. **Finish fee-and-tax-aware cost basis.** §5 is unserved everywhere, needs no
   new data, and is what people say they cannot do.
3. **Fix the thin-market data, not the thin-market UI.** §2 — 19,992/20,000
   valuations bypass the model. eBay Marketplace Insights is the unblock.
4. **Add a manual-add escape hatch wherever the catalogue misses.** §4 — cheap,
   and it converts a silently-wrong total into a right one.
5. **Do not revive grading without a real API.** §6 — validated by a competitor's
   own reviews.
6. **LEGO purchase price / condition / sealed-vs-used** is the widest open gap in
   a non-TCG live category. §7.

## Sources

- [Is Collectr Accurate? Collectr vs Pokedata on the Same 25 Cards — TCGinvest](https://tcginvest.io/blog/pokemon-collection-value-different-apps)
- [Collectr Reviews 2026 — JustUseApp](https://justuseapp.com/en/app/1603892248/collectr-tcg-portfolio-app/reviews)
- [Collectr — App Store ratings & reviews](https://apps.apple.com/us/app/collectr-tcg-collector-app/id1603892248?see-all=reviews&platform=iphone)
- [CollX Review 2026: Legit, Pricing & Worth It?](https://postunreel.com/blog/collx-review-2026)
- [ManaBox MTG — App Store](https://apps.apple.com/us/app/-/id1460407674)
- [How to Track Your Sports Card Collection Finances (Without Spreadsheet Hell) — The Smarter Collector](https://www.thesmartercollector.com/post/how-to-track-your-sports-card-collection-finances-without-spreadsheet-hell)
- [Best LEGO Collection Tracker Apps 2026 — Brickify](https://brickify.com/blog/best-lego-collection-tracker-apps-2026)
- [GameSetBrick vs BrickEconomy vs Brickset — The Earl of Bricks](https://theearlofbricks.com/blog-gamesetbrick-vs-brickeconomy-brickset/)
- [The Discogs "Median Price" Myth — Every Record Tells A Story](https://everyrecordtellsastory.com/2020/03/27/the-discogs-median-price-myth/)
- [Accuracy of "Collection Value" — Discogs Forum](https://www.discogs.com/forum/thread/728023)
- [Is nobody going to talk about this horrible new interface? — MyFigureCollection](https://myfigurecollection.net/blogpost/57713)
- [Does MFC have a clunky search function? — MyFigureCollection](https://myfigurecollection.net/blogpost/46720)
- [Best Whiskey Tracking Apps in 2026 — Whiskey Social](https://whiskeysocial.app/blog/best-whiskey-tracking-apps-in-2026)
- [12 Best Collection Tracking Apps — Packz](https://packz.io/blog/collection-tracking-apps)
