# i18n backlog — hardcoded English in the code

`npm run i18n:parity` polices the locale **files**; `npm run i18n:check`
polices the **code**. The second is the one with a backlog, and the two catch
different failures — CLAUDE.md §gates spells that out. A string that never
reaches a locale file cannot be missing from one, so parity is green while six
locales render English.

**Backlog: 410 strings across 159 files** (653 at the start). 234 translated
across 19 files, and 9 more removed by deleting a dead component rather than
localising it.
`i18n:check` is deliberately **not** a blocking gate; making it one would wedge
every deploy until the backlog is zero — same reasoning as `check:reachable`
and `audit_orphan_tables.py`.

## Rank by reachability, not by count

The obvious plan — "start with the biggest files" — is wrong here, twice over.

**The core screens are already done.** Measured, not assumed:

| screen | untranslated |
|---|---|
| all five `(tabs)` screens | **0** |
| `src/screens/Settings.tsx` | **0** |
| `app/add-manual.tsx` | **0** |
| `app/item/[id].tsx` | 2 |

**And the biggest files include screens nobody can open.** Sorting by raw count
puts `app/sell/dashboard.tsx` and `app/franchise/[id].tsx` near the top, and
`npm run check:reachable` lists both as having **no inbound navigation edge**.
Translating those is work with no user on the other end.

So the order is: *live and reachable* first, biggest within that.

⚠️ **`SELLING_ENABLED` does not mean what its name suggests.** It gates the
**external eBay** integration only — `src/screens/Settings.tsx:83` says so
outright — while **P2P trading is live**. So `app/offers.tsx`, `app/listings.tsx`
and `app/sell/new.tsx` are all real user-facing screens. Do not skip them.

## Done — 234 strings, 19 files

`offers.tsx` (24) · `CategorySpecificSection.tsx` (21) · `create-event.tsx` (17)
· `sponsor/register.tsx` (15) · `listings.tsx` (14) · `chat/new.tsx` (14) ·
`sell/new.tsx` (13) · `offer/[offerId].tsx` (13) · `purchase/deal/[dealId].tsx`
(13) · `edit-event.tsx` (12) · `listing/[id].tsx` (10) ·
`catalog-item/[key].tsx` (10) · `chat/[threadId].tsx` (9) ·
`purchase/index.tsx` (9) · `inbox.tsx` (8) · `(auth)/reset-password.tsx` (8) ·
`ItemDetailsCard.tsx` (8) · `tax-reporting.tsx` (8) ·
`events/compose-announcement.tsx` (8)

## Two things learned doing them

**Reuse a key only when the English is IDENTICAL, not merely similar.**
`common.retry` exists but reads "Retry"; pointing a "Try again" button at it
would silently reword the UI. `edit-event.tsx` renders "Go Back" while
`common.go_back` is "Go back" — different casing is still different copy, so
the visible label got its own key while the a11y label (genuinely identical)
reused the shared one. Checking each candidate cost seconds and prevented
several silent copy changes.

**Proper nouns are not translatable strings.** Brand names — CheckCheck,
Legit Check, Discogs, Warhammer Community — are in `ALLOWLIST_STRINGS` in
`check-i18n-strings.mjs` rather than wrapped, because wrapping one invites a
translator to localise a company name. The product name is preserved *inside*
otherwise-translated strings: "Sparrow's Watch", "What Sparrow spotted",
"Sparrow Pro". And `q10`/`q50`/`q90` in the price bands is notation, not words.

## Old done-list (kept for the note on why offers.tsx went first)

| file | strings | notes |
|---|---|---|
| `app/offers.tsx` | 24 | largest live screen; `/offers` is pushed from `listings.tsx` and `offer/[offerId].tsx` |

## Next, in order (live screens only)

| file | strings |
|---|---|
| `src/components/share/ShareToChatSheet.tsx` | 7 |
| `src/components/p2p/SettleUpSheet.tsx` | 7 |
| `src/components/category/YourItemsRail.tsx` | 7 |
| `src/components/category/CategoryOverviewRail.tsx` | 7 |
| `app/analytics.tsx` | 5 |
| `app/barcode-scan.tsx` | 5 |

The long tail is now mostly 1-7 strings per file across ~160 files.

⛔ **Do not translate these.** `app/sell/dashboard.tsx` (10) and
`app/franchise/[id].tsx` have no inbound navigation edge (`check:reachable`),
and `app/twitch.tsx` is a stub.

✅ `src/components/item/SellOnSparrowSection.tsx` **was deleted** (2026-09-08)
rather than translated. It had 8 strings and was imported by nothing — the only
mention anywhere was a comment in `app/sell/pick.tsx` describing what the
screen used to be, and there was no barrel file in its directory (checked,
because a barrel re-export IS a reference and CLAUDE.md records assuming
otherwise as a past mistake). **Checking reachability before translating is
worth doing every time**: it turned 8 units of translation work into a
deletion.

## How to do a slice

1. Check the file is reachable and its feature flag is on **before** translating.
2. Add `useTranslation()` once per component; confirm every string is inside
   the component that declares `t` (a string in a bare helper function has no
   hook in scope).
3. Keep the English as `defaultValue` on every call, so a locale that ever
   loses the key renders the words rather than a raw key string.
4. **Reuse an existing key only if its English is identical.** `common.retry`
   exists but reads "Retry"; using it for a "Try again" button silently
   rewords the UI. `common.try_again` was added instead.
5. Add the key to **all seven** locales with real translations, never English
   copies.
6. Audit with `npm run check:i18n-defaults` (in `verify:prebuild`), not a
   reread. ⚠️ Its first version matched only SINGLE-quoted `defaultValue`, so it
   silently skipped every string containing an apostrophe — exactly the ones
   most likely to be mis-transcribed. Fixing it took the checked count from 77
   to 162. It verifies:
   every key exists; **every `defaultValue` matches `en.json` exactly** (this is
   what catches an off-by-one in parallel translation arrays, and nothing else
   will); `t()` appears only inside the declaring component; and no non-English
   locale is a copy of the English.
7. Finish with `npm run i18n:parity`, `audit_fe_i18n_drift.py`, `tsc --noEmit`.
