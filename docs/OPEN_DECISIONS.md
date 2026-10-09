# Open decisions

Product calls queued for Merle. Each entry carries the measurement it rests on
and how to re-check it — a decision taken on a stale number is a new bug.
When one is decided, move it to **Decided** with the date and the commit that
carried it out; do not delete it.

_Opened 2026-09-26 from the Android walk rounds._

## Open

_Opened 2026-09-28 from the affiliate / outbound-link sweep (classes AV–AY in `docs/CLASS_SWEEPS.md`). #1–#12 are decided; each entry as opened is kept under **As opened** at the end._

### 16. Affiliate enrollment — **recommend: eBay Partner Network first, then one aggregator**
- **✅ Step 1 done 2026-10-05:** eBay Partner Network, Business account under the eenmanszaak, campaign `5339218687` in `EBAY_AFFILIATE_CAMPAIGN_ID` (9/9 gates, bake restarted, the running process's environ has it). Live `/marketplace/affiliate-links` returns eBay links with `campid=5339218687`, `mkrid`, `customid`. Steps 2–4 below are still open.
- **⏸ PARKED 2026-10-06 (Merle: "not worth it for now").** Impact signup landed in Trackonomics and its brand search showed none of the brands; TCGplayer's direct join link is `app.impact.com/campaign-campaign-info-v2/TCGplayer.brand?io=…` (from docs.tcgplayer.com), StockX applies via stockx.com/news/stockx-affiliate-program. Whatnot needs 1,000+ social followers, so skip it. Re-open when outbound clicks justify it: `SELECT count(*) FROM demand_signals WHERE signal_type='affiliate_click' AND created_at > now() - interval '30 days'` (7 clicks ever on 10-05).
- **State (as opened):** all 16 `*_AFFILIATE_*` vars empty on EC2 (checked 2026-09-28). eBay is 336,880 of ~360k outbound links in 30 d. Of 18 shops the app links to, 8 pay per sale (eBay, TCGplayer, StockX, Catawiki, Reverb, HLJ, Solaris Japan, Sideshow); Reverb/HLJ/Solaris/Sideshow have no tagger yet.
- **Do (your hands), in this order** — send the value in brackets; it goes in `/opt/collectors/.env`, no app build:
  1. ~~**eBay Partner Network**~~ ✅ 2026-10-05 (see above).
  2. **Impact.com** as a Partner, then apply inside it to **TCGplayer**, **StockX** (and Whatnot — nothing links to it yet) → [each tracking link `https://<brand>.pxf.io/c/…/…/…`] → `TCGPLAYER_/STOCKX_/WHATNOT_AFFILIATE_ID`.
  3. **Catawiki via Partnerize** (join.partnerize.com/catawiki) → [`https://prf.hn/click/camref:…`] → `CATAWIKI_AFFILIATE_ID`.
  4. **Sovrn Commerce or Skimlinks** (one) → [account key] — covers Mercari, AmiAmi, Sideshow; its link format must be added in `affiliate.py` first.
  - Skip: Cardmarket (signup referral, €10/month cap), Discogs, BrickLink. Later: Reverb, HLJ, Solaris Japan, Sideshow direct (need link formats).
  - Applications ask for a site/app: sparrowcollect.com + the App Store link.
- **Re-check:** `grep AFFILIATE /opt/collectors/.env`.

## Decided

- **2026-10-09 — Payments at launch: in-app purchase ONLY (Apple via RevenueCat, Google Play); the web Stripe checkout stays OFF** (Merle: yes). Reasons: no paying users yet, so conversion matters more than the fee; Apple/Google are merchant of record and file EU VAT for us, Stripe direct would make the eenmanszaak do VAT OSS, invoices and refunds; one payment path is the lowest App Review risk for the first 1.0. Cost cut instead: **Apple Small Business Program** (30% → 15%); Google already charges 15% on subscriptions.
  - **State it rests on (2026-10-09):** the web route is built but not live — `web/pro.html` calls `POST /billing/web/checkout-session` (`server/app/routes/billing_router.py:533`), the EC2 `.env` has `STRIPE_SECRET_KEY=sk_test…`, and `web/` is not deployed. Re-check: `ssh collectai 'grep -oE "^STRIPE_SECRET_KEY=sk_(live|test)" /opt/collectors/.env'`.
  - **Re-open when** there is revenue (~€1–2k/month) AND a channel that lands people on the website. Then prefer a merchant of record (Paddle / Lemon Squeezy, ~5%, they file VAT) over plain Stripe, and look at Apple's US external-purchase links. Plan: `docs/HYBRID_WEB_SUBSCRIPTION_PLAN.md` (its "no links/prices in the iOS app" rule still applies while this stands).
  - **Same day — RevenueCat moved to the `ccollect.ai@gmail.com` account, project "Sparrow Collect" (`e94defd0`).** The login holding the May project could not be found. New: App Store app (`.p8` key `3LX4HL24FM`, valid), Play app (2 of 3 credential checks pass; the purchases check needs a first AAB in Play), products `sparrow_pro_monthly`/`sparrow_pro_yearly` → entitlement `pro`, offering `default` `$rc_monthly`→monthly, `$rc_annual`→yearly. EAS `production` keys `EXPO_PUBLIC_REVENUECAT_IOS_KEY` (replaced) + `_ANDROID_KEY` (new). Webhook → `/billing/revenuecat-webhook` answered RevenueCat's test event 200. ASC App Store Server Notifications (prod + sandbox) → RevenueCat. **The 1.0 iOS binary must be built after 2026-10-09** (old key = old project). Re-check: `curl -H "Authorization: Bearer <EAS key>" -H "X-Platform: ios" https://api.revenuecat.com/v1/subscribers/probe/offerings` → `default` with both products.

- **2026-09-29 — Explore banners: every tile has a correct image (`8103218e`, client; needs a JS build).** Chosen with Merle at tile size over five rounds; walked on the emulator. See class AR in `docs/CLASS_SWEEPS.md` for sources and the `bannerFocusY` crop field.
- **2026-09-29 — Telegram "Overdue Workers" spam: FIXED (`d878e84c`, DEPLOYED).** A probe yielding to heavy workers gets 6x its interval before it is overdue; see `docs/WATCHDOG.md`.

- **2026-09-28 — #17 an item priced from anything with its name in the title: FIXED (`f7540cd4`, DEPLOYED 22:08 CEST; trigger applied on prod).** Two holes, both closed at the chokepoint: (1) `trg_items_canonical_ref` gave ANY key a ref (`charizard` → `pokemon:charizard`, which matched title-filed junk predictions) — a key the catalogue does not know now gets no ref (`server/migrations/20260928_canonical_ref_catalogue_only.sql`; rolled-back dry run first: 1 of 17 items changed, 56/56 category sample keys still resolve); (2) the catalogue matcher's LIMIT 5 hid AH's tie — "Charizard" returned one Celebrations row at 1.0; exact titles now rank first, so it comes back ambiguous at 0.5 (Base Set with set+number still resolves at 1.0). The test account's item re-linked to `base1-base1-4`. Verified live: its evidence reads EUR 825 from TCGplayer/Cardmarket sales (was EUR 10 from plushies); a new item POSTed with key `charizard` gets `canonical_ref` NULL (probe deleted).

- **2026-09-28 — #13 junk Mercari rows: DONE on prod** (Merle: yes). One transaction: 9,241 `market_hits` rows deleted (`provider='crawl4ai'`, photo URL, title echoing our query — all 9,241 had both), and 2,061 `market_hits_daily` rows removed whose day had ONLY those rows (6,667 item-days touched). Re-check: `select count(*) from market_hits where url like '%mercdn%'` → 0. **Not reachable:** daily rows before 2026-09-01 — `market_hits` keeps one month, so older days that included such rows cannot be recomputed; they age out of the 180-day window by March 2027. New junk stops only when the parse fix is DEPLOYED.
- **2026-09-28 — #14 daily rollup: SALES FIRST, listings as fallback — DONE on prod** (Merle: "preferably sales only but not if we lose all data"). Measured first: pure sales-only would have emptied the daily price of **24,525 of 97,111** items (25 %, the eBay-fed categories have listings only). So on an item-day with sales only sales count; a day with none keeps its listings' median. Cron job 39 changed via `supabase/migrations/20260928_market_hits_daily_sales_first.sql`; 2026-09-01…09-28 recomputed day by day. Verified: daily rows 1,599,970 → 1,650,919 (−2,061 junk-only days, + today's 53,047 not yet rolled) — nothing lost; on 09-27 all 83 mixed item-days now equal the sales-only median (82 had differed). Re-check: `select position('day_has_sales' in command) > 0 from cron.job where jobid = 39` → true.
- **2026-09-28 — #15 scraper "sold" rows: no longer stored — `eb90da8a`, DEPLOYED 21:31 CEST** (Merle: yes). Tests re-run on the box against the deployed modules: 89/89. `persist_comps_to_db` skips a row flagged sold with no `sold_at` from the markdown scrapers (`_UNDATED_SOLD_SCRAPERS`: crawl4ai, firecrawl, scrapedo, grailed, comc, reverb, abebooks); eBay, TCGplayer and the other API sources are untouched. Tests in `test_marketplace_agent_persist.py`, incl. one that derives the scraper set from the adapters' source (mutation-proven).

- **2026-09-28 — outbound links and affiliate tagging, from the recommendations — `eb90da8a`, server DEPLOYED 21:31 CEST (10 files, hashes 10/10, nine gates PASS); client needs a JS build.** Verified on prod: EU member (saved region, no region sent) gets no Yahoo JP / Mercari, a US request keeps both, Chrono24 carries `dosearch=true`; deployed `affiliate.py` passes 7/7 format checks with test values in-process; on the emulator (JS swap) Shop → TCGPlayer on an item wrote an `affiliate_click` row (probe deleted). Classes AV–AY in `docs/CLASS_SWEEPS.md`.
  - **Yahoo Auctions JP hidden for `europe`** — Yahoo! JAPAN blocks the EEA and UK (seen in a browser). When the app sends no region (`useItemMarketplace`, barcode scan), the member's saved region is used; all 4 saved regions on prod are `europe`. Tests: `test_yahoo_auctions_jp_hidden_in_europe`, `test_saved_region_used_when_caller_sends_none` (both mutation-proven).
  - **Mercari hidden for `europe`** — its own search shows "No results found" from NL and from Stockholm. For EU members the EU view IS the test; a US check matters only for `americas`, who keep it. Test `test_mercari_hidden_in_europe`.
  - **Scraper parse fixed** (`crawl4ai_caller.py`, shared by 6 adapters): an image is never the link (a Mercari photo is rebuilt to `/us/item/<id>/`, checked in a browser); image alt text that echoes our query is never a title; everything after "Items related to" is dropped; no adapter falls back to the SEARCH page as a listing (9 sites). 6 tests, each mutation-proven, incl. a guard against the fallback returning.
  - **Chrono24 search** needed `dosearch=true` — fixed in the link builder and in the scraper's template.
  - **Affiliate tagging** now follows each network's real link format and picks the network from the URL's host (`server/app/lib/affiliate.py`); every shop tap is recorded (`check:affiliate-open`).

- **2026-09-27 — #10 offline banner: DONE (9713dfcc).** A pill just above the bottom bar (offset from the bars' own height constant), translated, with the queue count. Seen on the emulator in airplane mode on Portfolio (tab bar) and Settings (QuickNavBar): header fully visible. Test `offlineBanner.test.tsx` (anchoring it to the top fails it).
- **2026-09-27 — #12 one price per catalogue item: DONE (69432053 server DEPLOYED, 4d55239d app).** `server/app/lib/catalogue_value.py` is the one rule for the scan, the catalogue page and (already) the saved item: the model's latest q50, else the daily median / latest comp; plus the latest day's source spread, `sources_disagree` when > 1.5x AND >= EUR 5 apart. Base Set Charizard now reads EUR 825 on the scan, the catalogue page and the item — and the scan and catalogue page show "EUR 825 – EUR 1.531 · Markets disagree on this one" (seen on the emulator). A EUR 0.56 common spanning 0.47-4.20 is not flagged (the EUR 5 floor). Not done: why this card's prices stopped on 09-05 (a pipeline question, left open in the note below).
- **2026-09-27 — #11 QuickScan server latency: DONE (a6712bbd, DEPLOYED).** Profiled stage by stage on EC2: social proof's "recent sold" was a 3.2M-row `ILIKE '%key%'` scan (2.2-4.5 s per scan, and it matched OTHER cards' sales); the same shape sat in barcode pricing (9.6-14.1 s for 0 rows) and dossier comps — class AS, all now exact `item_ref`. The same scan: 10.3-12.5 s -> 6.0-8.6 s (median 7.1). What remains is the OpenAI vision call (4.3-4.8 s, ~80 %): shortening its output (chain-of-thought, defect notes) could save seconds but needs an accuracy check first — one knob at a time. The 20 s client cap stays as a safety net.
- **2026-09-27 — walk of the screens the sweep skips (emulator):** signed-out Login / Register / Reset (routes.json now expects no signed-in chrome), 2FA challenge (wrong code → toast, right code → in), reset-password via a real recovery link (mismatch caught, new password works, restored), Register with creator code `seednova` → `profiles.referred_by_code = SEEDNOVA` → Check your email → real confirmation mail → confirmed and signed in → Delete account (gone from auth + profiles), chat thread (read-only: it is with Merle's real account) + new chat request to simseller, Create / Edit / Announce / Cancel event, QuickScan (gallery + live camera) and barcode scan (camera, 3 generated codes). **Fixed:** watchlist error toast for a signed-out member (every new member saw it after the confirm link); event Manage sheet's dismiss row misaligned and a second "Cancel" (Merle); Create Event ignored a typed detail; QuickScan dropped the scan photo on save; an old draft overwrote a fresh scan hand-off; a 0 %-confidence category pre-filled; "Identified via: manual" / "We don't recognize" under found results; camera QuickScan capped at 8 s against an 11 s server; "You said EUR X" for a scan's own estimate. Test data removed (account, inbox, DM request, event cancelled, projects, items).
- **2026-09-26 — walk items 1–7 (Pro, emulator):** all seen working except as noted. Found and FIXED on the way: Portfolio 90D read +EUR 0 over a EUR 35 fall (`market_change` counted only items held on day 1 — server DEPLOYED) and then "(0,00%)" (percent against the chart's EUR 0 start); switching a project's Complete OFF always failed (NULL into NOT NULL `progress_pct`). Noted, not bugs: Sets to complete is empty for simcheck because none of its items is linked to a catalogue set (server `/sets/auto-progress` → `[]`); a hand-typed `sparrow://catalog-set/<code>` without `name` titles the page "Set" (in-app navigation passes it); one "Deal found" row opens "Deal not found" — its deal was in the probe data deleted earlier today. simcheck back to Free.
- **2026-09-26 — #7 Market filter placement: FIXED.** The filter & sort button sat alone at the left edge of the action row, reading as neither search nor action. It now sits in the search row beside Favourites (same 40pt box); the action row holds only Open bids + Sell, and "Clear" moved to the end of the applied-filter chips it clears. `app/listings.tsx`. Verified on the emulator: layout + the button still opens Filters & Sort.
- **2026-09-26 — #9 simcheck reverted: DONE.** `subscriptions.plan` pro → free (the row had no Stripe ids — a hand grant) and settings EUR / europe / de-DE. Falsifier: `GET /catalog/pokemon/items/base1-base1-4/price-range` as simcheck → 403.
- **2026-09-26 — item page "renders partially on first open": NOT reproduced.** Fresh install, first open of an item: complete at 1.5 s and identical at 7.5 s. Re-open only with a screenshot.
- **2026-09-26 — found on the device check, FIXED: settings were never read back from the server.** A reinstall showed EUR to a member saved as USD: the client only ever PUT `/settings`. `GET /settings` now returns `saved` (a row exists) and `src/components/SettingsServerSync.tsx` applies the saved, valid values once per signed-in user after the local settings load (`__tests__/lib/settingsFromServer.test.ts`; mutation of the `saved` guard fails it). Server DEPLOYED; client needs the next build. Rider, same root: onboarding shows again after a reinstall and its Skip / Get Started wrote the DETECTED region to the server unconditionally — that, not a choice, is what had turned simcheck back to EUR. Now only a region the member PICKS is written; a detected one only when nothing is saved (`detectedRegionWrite`, same test, mutation-proven). **Verified on the emulator:** reinstall → sign in → Skip → server still USD (GETs only, no PUT), Portfolio shows $1,400.

- **2026-09-26 — #8 throwaway accounts: CLOSED** (Merle: close the open items). Deleted the unconfirmed `sparrowtest72uyt7m3@uberip.com` (auth user via the admin API — it could not sign in, so `DELETE /account` was not available; its profile cascaded, it owned no items) and its mail.tm inbox. **Kept as test fixtures**, with their probe data already deleted: `zz-lifecycle` — the only account with a verified factor, needed to re-prove server-side 2FA (`docs/AUTH_AND_WEB_DEPLOY.md`); `simseller` — the free-plan counterpart for P2P and paywall checks.

- **2026-09-26 — #2 catalogue price range & trend: DONE** — Pro endpoint + `CatalogPriceRangeBlock`; teaser for free. See `docs/MONETIZATION.md`.
- **2026-09-26 — #3 one name per category: DONE.** `src/constants/categories.ts` is canonical; the registry (13 names) and the Explore data (18) now match it, plus two stray labels. Gate: `__tests__/lib/categoryNameParity.test.ts` (all four lists incl. the server scan map; mutation-proven).
- **2026-09-26 — #4 single-sale prices: KEEP as they are** until there is more
  data or a better eBay replacement (Merle). No change. Evidence to weigh when
  revisited: LEGO 75192 UCS Falcon prices at EUR 124.78 from 32 comps whose
  daily medians are 74 / 175 (latest 20.77) — parts/minifigs matched as the set.
- **2026-09-26 — #5 server-side 2FA: DONE** — API 403 + restrictive RLS policy on 314 tables + guard in 16 DEFINER RPCs + watchdog check; verified as zz-lifecycle. See `docs/AUTH_AND_WEB_DEPLOY.md` → MFA.
- **2026-09-26 — #6 concerts shown as conventions: DONE** — `concert` kind from the providers' own classification, admission tickets skipped, 498 rows backfilled; see `docs/EVENT_QUALITY_PLAN.md`.
- **2026-09-26 — #1 barcode: no paid source** (Merle) → free options 1 (learn from members' saves) and 3 (photo fallback) BUILT and verified on prod; see `docs/BARCODE.md`. Option 2 (Brickset LEGO EANs, free key) not taken up.

## As opened (2026-09-28)

### Yahoo Auctions JP, Mercari and the scraper parse (decided the same day)
- Yahoo Auctions JP offered for every JP category in every region; it blocks the EEA/UK.
- Mercari US in the floor set for every category and region; "No results found" from NL.
- `_extract_url_from_listing` took the first URL (a photo on Mercari); titles came from image alt text echoing the query; the search page stood in for a missing link.
- Recommended then: hide Yahoo JP in Europe; check Mercari from a US connection first; fix the parse before deciding on scraper sold rows. The Mercari advice changed on the evidence — see Decided.

### 13–15, 17. (as opened 2026-09-28, decided the same day)

#### 17. A free-text item priced from anything with its name in the title — **found 2026-09-28, not triaged**
- **State:** simcheck's "Charizard (Base Set 004)" is `canonical_ref = pokemon:charizard` (not linked to `pokemon:base1-base1-4`). Its card reads "Our comps say €10" from a 2026-09-06 prediction (q50 €9.90, confidence 0.33) over 8 eBay rows filed under the generic key — plushies, a 25th-anniversary set. The catalogue card itself holds EUR 812–1,531 sales. Not caused by the 09-28 changes (prediction predates them).
- **Re-check:** `GET /predict/evidence/60be9f51-7c1c-4e6a-8866-d2691453b88c` as simcheck.


#### 13. Delete the 9,234 Mercari rows that are not the items they are filed under — **recommend: yes**
- **State:** in 30 days, 9,234 `market_hits` rows at `u-mercari-images.mercdn.net`: 6,327 titled with OUR query (`"Goodfellas (4K UHD) sold" search result`) and 2,907 from Mercari's "Items related to …" section. Each carries a catalogue `item_ref` (6,660 items) and a price of some OTHER item. The parse is fixed (Decided, below), so no new ones arrive — but the old ones sit in the nightly `rollup-market-hits-daily`, which medians every priced row: **6,660 items had them in their daily price; on at least one day 2,107 items had ONLY them.** That table feeds the catalogue price fallback (#12) and the Pro price range (#2).
- **Do:** `DELETE FROM market_hits WHERE url LIKE '%mercdn.net%' AND provider = 'crawl4ai'`, then recompute `market_hits_daily` for the touched `(item_ref, day)` pairs (delete the days that had only these rows). A prod data write — waiting for your yes.
- **Re-check:** `select count(*) from market_hits where seen_at > now()-interval '30 days' and url like '%mercdn%'` → 9,234 today; 0 after.

#### 14. Should the daily price rollup count asking prices? — **recommend: no (sold only)**
- **State:** `rollup-market-hits-daily` has no `is_listing` filter. 30 d of priced rows: 2,942,932 sold vs 357,508 listings (eBay 337,086 · crawl4ai 17,908 · discogs 2,498) — about 11 % asking prices in a table read as "what it sells for". Valuation and training already exclude listings (`is_listing IS NOT TRUE`).
- **Do:** add `AND is_listing IS NOT TRUE` to the cron command and rebuild the 180 days kept. Changes the number members see on thin items, which is why it is yours.
- **Re-check:** `select command from cron.job where jobname = 'rollup-market-hits-daily'`.

#### 15. Scraper "sold" rows are stored as buyable listings — **recommend: stop persisting them until one source is audited**
- **State:** `crawl4ai_caller` and `firecrawl_caller` always write `sold_at: None`; persist sets `is_listing = (sold_at IS NULL)`. So a `sold_comps()` row (`is_sold: True`) lands as an asking-price LISTING: never used by valuation, but eligible for the Target Hit snipe (`deal_discovery_worker.py:167`, url + `is_listing`, no provider filter). 0 of 120 fired alerts used one so far.
- **Options:** (a) don't persist scraper rows flagged sold (recommended — they are neither valid listings nor trusted comps); (b) set `sold_at` and let them into valuation — only after a per-site title/price audit; (c) leave as is.
- **Re-check:** `select count(*) from market_hits where provider in ('crawl4ai','firecrawl') and is_listing and title ~* 'sold'`.


## As opened (2026-09-26)

### 1. Barcode scanning resolves books only
- **State:** `category_items.barcode` is empty in every category; the lookup
  cascade after the catalogue is Open Library + Google Books (ISBN only). LEGO
  75192's EAN `5702015869935` → nothing.
- **Option:** UPCitemdb resolved that EAN to "Lego 75192 Millennium Falcon"
  from EC2, but its keyless tier is a 100/day trial — production means a paid
  plan (or another EAN source) and a third-party dependency.
- **Detail:** `docs/BARCODE.md` (status block at the top).
- **Re-check:** `POST /intake/barcode-only {"barcode":"5702015869935"}` as a member.

### 2. Catalogue "full price range & 90-day trend" as a Pro feature
- **State:** the teaser was removed (a Pro member saw neither; the trend is
  SHELVED in `docs/MONETIZATION.md`). `market_hits_daily` already holds a daily
  median per `item_ref`, so p10/p90 over 90 d + a weekly series is one query
  behind `require_plan("pro")`.
- **Detail:** `docs/MONETIZATION.md` → "Catalogue detail teaser removed".

### 3. One name per category
- **State:** 21 categories are named differently across four sources — pills
  and pickers (`src/constants/categories.ts`), the taxonomy registry, the
  Explore page (`src/data/categories.ts`) and the server's scan map. E.g.
  Pokémon / Pokémon TCG / Pokémon Cards; Funko Pop / Funko Pop! / Funko Pops.
  Keycaps was unified to "Custom Keycaps" (0b4c6093).
- **Question:** which name per slug; is a longer Explore page title allowed
  ("Comic Books & Graphic Novels") beside a short pill name?
- **Re-check:** `node /tmp/names.mjs`-style comparison — list every slug whose
  names differ across the four files.

### 4. Catalogue prices resting on a single sale
- **State (2026-09-26):** of priced `item_ref`s in the 180-day
  `market_hits_daily` window — **268,621 rest on ONE comp** (266,810 of them
  older than 60 days), 8,847 on two, 127,594 on three or more. Example: the
  PSA 10 1st Edition Charizard read ~EUR 367 from one comp dated 2026-07-04.
- **Question:** hide, flag ("based on 1 sale, 3 months ago") or keep? Hiding
  un-prices roughly two thirds of the catalogue.
- **Note:** base1-base1-4 is one row for BOTH printings, so its median mixes
  1st Edition and unlimited sales.
- **Re-check:** the count query is in the 2026-09-26 session notes; group
  `market_hits_daily` by `item_ref`, `SUM(comps_count)` over 180 d.

### 5. Server-side 2FA enforcement
- **State:** 2FA is enforced in the app only. The EC2 API and Supabase RLS
  accept an `aal1` token for a member with a verified factor.
- **Scope measured:** member-facing RLS covers **272 tables / 456 policies**.
  One restrictive policy per table calling a single `mfa_satisfied()` function
  (evaluated once per statement), generated mechanically, plus an `aal` check
  in `server/app/auth.py`.
- **Detail:** `docs/AUTH_AND_WEB_DEPLOY.md` → MFA section.

### 6. Concerts labelled "Convention" in Events
- **State:** Ticketmaster queries (kpop_merch / taylor_swift) bring in
  concerts and tribute acts, shown to all members as conventions.

### 7. Market tab filter-chip placement
- Walk note: placement reads ambiguously; a design call.

### 8. Throwaway test accounts
- `simseller@sparrowcollect.test`, `zz-lifecycle@sparrowcollect.test` (2FA
  enrolled), `sparrowtest72uyt7m3@uberip.com` (unconfirmed, mail.tm inbox).
  Deleting users is irreversible; they are also useful for future walks.
  Their probe DATA was deleted 2026-09-26.

### 9. simcheck back to Free + EUR
- simcheck (the walk account) is Pro and on **USD**, left so for the class AO
  device check. Revert after the verification build?

### 11. (as opened 2026-09-27) QuickScan is slow on the server (p50 11 s)
- **Measured 2026-09-27** (bake.log, `/intake/image-only`, 9 calls): p50 11 s,
  max 16.9 s; vision itself ~4 s of that. The camera path's 8 s client cap made
  most live scans fall back to manual — the cap is now 20 s (f4631354), which
  hides the symptom, not the cause. Next: profile the other ~7 s (CLIP,
  catalogue match, pricing) before changing anything. Re-check:
  `grep '"path": "/intake/image-only"' bake.log | grep -o '"duration_ms": [0-9.]*'`.

### 10. (as opened 2026-09-27) The offline banner covers the screen header
- **Seen:** device walk 2026-09-26, airplane mode, Portfolio. `OfflineBanner`
  (`src/components/OfflineBanner.tsx`, mounted in `app/_layout.tsx`) is an
  absolute overlay: while offline it hides the screen title and the
  bell / chat / settings icons (taps pass through — `pointerEvents: 'none'`).
- **Why a decision, not a fix:** making it push content down changes the layout
  of every screen; alternatives are a slimmer status-bar-only strip or a pill
  above the tab bar. Re-check: airplane mode on, cold start, look at the header.
- **Recommendation (2026-09-27): a small pill just above the tab bar** (or the
  bottom safe area on screens without one), same colour, same text and queue
  count, still non-interactive. It hides no controls (the header holds back,
  bell, inbox, settings — the tab bar is already out of reach offline for
  most destinations), needs no layout change on any screen, and keeps clear
  of toasts, which enter from the top. Not a status-bar strip: on iPhones
  with a Dynamic Island the middle of that strip is taken.

### 12. (as opened 2026-09-27) A scan and its item page quote different prices
- **Seen 2026-09-27:** Base Set Charizard (`base1-base1-4`) scanned at EUR
  1.159 (QuickScan: `market_hits_daily` median); the saved item's page says
  "Our comps say EUR 825 · based on 2 market prices". Same catalogue key, two
  sources, two numbers. Needs a call on which is the item's value (and the
  AP note already says this key mixes 1st Edition and unlimited sales).
- **Measured 2026-09-27:** each day this card has exactly TWO prices —
  TCGplayer holofoil EUR 825 and Cardmarket EUR 1,531 (the same 1,531 every
  day: a guide figure, not sales). The scan takes the median of daily medians
  = the MIDPOINT of the two (EUR 1,159); the item page reads the catalogue
  model's q50 = the TCGplayer number (EUR 825). Neither source has moved since
  2026-09-05.
- **Recommendation:** one number per catalogue item — the scan should SHOW the
  value chain's number (the one the item page and portfolio will use) instead
  of computing its own from `market_hits_daily`, so saving never changes the
  price under the member. And when the sources disagree by more than ~1.5×
  (here 1.9×), show the RANGE with "sources disagree" rather than any single
  figure: a midpoint of a US price and an EU guide price is nobody's price.
  Separately worth a look: why this card's prices stopped on 09-05.

