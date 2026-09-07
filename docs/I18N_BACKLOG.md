# i18n backlog — hardcoded English in the code

`npm run i18n:parity` polices the locale **files**; `npm run i18n:check`
polices the **code**. The second is the one with a backlog, and the two catch
different failures — CLAUDE.md §gates spells that out. A string that never
reaches a locale file cannot be missing from one, so parity is green while six
locales render English.

**Backlog: 629 strings across 178 files** (was 653 before the offers.tsx slice).
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

## Done

| file | strings | notes |
|---|---|---|
| `app/offers.tsx` | 24 | largest live screen; `/offers` is pushed from `listings.tsx` and `offer/[offerId].tsx` |

## Next, in order (live screens only)

| file | strings |
|---|---|
| `src/components/CategorySpecificSection.tsx` | 21 |
| `app/create-event.tsx` | 17 |
| `app/listings.tsx` | 14 |
| `app/chat/new.tsx` | 14 |
| `app/sell/new.tsx` | 13 |
| `app/offer/[offerId].tsx` | 13 |
| `app/purchase/deal/[dealId].tsx` | 13 |

Skip until reachable: `app/sell/dashboard.tsx` (10), `app/franchise/[id].tsx`,
`app/twitch.tsx` (a stub — see `project_twitch_is_stub`).

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
6. Audit with a checker, not a reread. The one used for `offers.tsx` verifies:
   every key exists; **every `defaultValue` matches `en.json` exactly** (this is
   what catches an off-by-one in parallel translation arrays, and nothing else
   will); `t()` appears only inside the declaring component; and no non-English
   locale is a copy of the English.
7. Finish with `npm run i18n:parity`, `audit_fe_i18n_drift.py`, `tsc --noEmit`.
