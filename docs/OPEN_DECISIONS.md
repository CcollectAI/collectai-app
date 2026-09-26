# Open decisions

Product calls queued for Merle. Each entry carries the measurement it rests on
and how to re-check it — a decision taken on a stale number is a new bug.
When one is decided, move it to **Decided** with the date and the commit that
carried it out; do not delete it.

_Opened 2026-09-26 from the Android walk rounds._

## Open

_None. All nine from the 2026-09-26 walk are decided; each entry as it was opened is kept under **As opened** at the end._

## Decided

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
