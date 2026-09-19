# i18n backlog — hardcoded English in the code

`npm run i18n:parity` polices the locale **files**; `npm run i18n:check`
polices the **code**. The second is the one with a backlog, and the two catch
different failures — CLAUDE.md §gates spells that out. A string that never
reaches a locale file cannot be missing from one, so parity is green while six
locales render English.

**Backlog: 159 strings across 94 files** (measured 2026-09-19; 653 at the start.
Every number in this file goes stale within a session or two — `npm run i18n:check`
prints the live one, so re-run it before quoting one.)

**2026-09-19: the mechanical `accessibilityLabel` slice is DONE.** Of 149
hardcoded a11y labels, 47 had an English string that already existed verbatim in
`en.json` — those needed no translator and were wired in two batches (33, then
the 14 whose component had no `t` in scope and needed `useTranslation()` added).
That count is now **0** — re-measure by grepping `accessibility(Label|Hint)="..."`
across `app/` and `src/` and testing each literal against the flattened values of
`en.json`; nothing comes back. The **102** that
remain each need a NEW key in all seven locales, i.e. real translations — they
are not grindable without a translator and must not be filled with English
copies (step 5).

**2026-09-17: the lint now says which findings are FREE.** It reads the locale
files and marks any finding whose exact English text is already a value in
`en.json` with a different value in another locale — those need `t('<key>')` and
nothing else: no translator, no new key, no review. The Dutch screen sweep is
what made the distinction obvious: it showed English buttons on Dutch screens
(**"Try again"** on the watchlist's failed state, "Save to Collection",
"Look Up", "Go Back", "Send Announcement", "All categories",
"View full details") and every one of them already had a Dutch translation
sitting in the file. All 9 were wired the same day, so that count is **0** now;
`node scripts/check-i18n-strings.mjs --wiring` lists them if it ever isn't.

⚠️ Do not trust the per-screen table below without re-measuring. It claimed the
five `(tabs)` screens were at **0** while `(tabs)/wishlist.tsx` had three
findings, one of them a visible English button.
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

**A new string must reuse the locale's existing NOUN for a feature, not a fresh
translation of the English verb (2026-09-13).** "…so it can't be watched from
here" went into nl/de/fr/es as *volgen / beobachten / suivi / seguir*, while the
button beside it in each locale says *volglijst / Beobachtungsliste / liste de
suivi / lista de seguimiento*. Grammatical, translated, and inconsistent with
the screen it appears on — and `check:i18n-defaults` and `i18n:parity` both pass,
because they check the English and the key set, never the vocabulary. Before
writing a translation, read the same locale's nearest existing key for that
feature (here `catalog.add_to_watchlist`) and reuse its term.

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

## The ACCESSIBILITY half of the backlog — 153 hard-coded labels (measured 2026-09-16)

A Dutch sweep round (`npm run walk -- --locale nl`, which sets the app's own
Language and verifies it) showed English on a screen otherwise fully Dutch:
`favorites` read **"Go back"** while `archived` read "Terug". A screen reader in
Dutch was hearing English on almost every screen.

```bash
grep -rnE 'accessibility(Label|Hint)="[^"]+"' app src | grep -v '{t('   # 153
```

✅ **Fixed: the shared chrome**, which is where the leverage was — the same four
strings appeared on 45–59 screens each (the sweep collapses a flag on ≥40% of
screens into one finding, which is how they stood out):

| component | was | now |
|---|---|---|
| `ScreenHeader`, `TabBackButton` | `accessibilityLabel="Go back"` | `t('common.go_back_a11y')` |
| `HeaderActions` | `"Notifications, 3 unread"`, `"Settings"` | `t('screen_titles.notifications')` + `t('common.unread_count_a11y')`, `t('nav.settings')` |
| `InboxHeaderButton` | `"Inbox, 2 unread"` | `t('common.inbox_a11y')` + the same count key |
| `QuickNavBar` | `"Main navigation"` | `t('common.main_navigation_a11y')` |
| `(tabs)/_layout` | `tabBarLabel: "Events"` — the ONE English literal in a bar whose other four labels were `t('nav.*')` | `t('nav.events')` (new key) |
| `quickscan/PermissionScreen` (2026-09-18) | `accessibilityLabel="Go back"` while the VISIBLE label beside it was already `t('common.go_back')` | `t('common.go_back_a11y')` |

⚠️ None of those five components imported `useTranslation`; the first pass
called `t()` without it and only `tsc` caught it. Check the hook exists before
using `t` in a component that never needed it.

The PermissionScreen row was found by a red test, not by the sweep: a stale
assertion on the visible copy sent someone to read the control, and the a11y
label one line above it was still an English literal — on the one screen whose
whole job is to get a blocked member unstuck. It already imported
`useTranslation`, so the ⚠️ below did not bite.

**~144 remain**, one to a few per file — same ranking rule as below: reachable
screens first. `QuickNavBar`'s five TAB LABELS stay English literals by
deliberate decision (ui-playbook 2026-08-19); the real tab bar translates them,
so the two bars disagree in Dutch — Merle's call, not a bug to fix silently.

## ⛔ Plural keys use the wrong suffix (found 2026-09-14, not fixed)

`src/i18n/index.ts` sets `compatibilityJSON: 'v4'`, which resolves plurals with
CLDR suffixes (`key_one` / `key_other`). The locales ship the old v3 form,
`home.sets_in_progress` + `home.sets_in_progress_plural` — the only `_plural`
key in en.json. Under v4 `_plural` is never looked up, so
`t('home.sets_in_progress', { count: 3 })` falls back to the singular: **"3 set
in progress"** on the Home tab (`AutoSetProgressList`, rendered by
`(tabs)/index.tsx`). Not seen on a device — the walk account has no sets.

Why it is not a one-line rename: ja/ko have only an `_other` form in CLDR, so
`_one` keys would be missing there and `i18n:parity` (which wants every en key in
every locale) would fail. Fix the parity checker to understand plural suffixes
in the same change. Until then, new strings with a count pick the singular or
plural key explicitly in code — see `category.set_item_count_one/_many`.

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
   to 162. It verifies exactly two things, and no more:
   every key exists in `en.json`; and **every `defaultValue` matches `en.json`
   exactly** (this is what catches an off-by-one in parallel translation arrays,
   and nothing else will).
   ⚠️ **Corrected 2026-09-19.** This step used to claim the gate also checks that
   `t()` appears only inside the declaring component, and that no non-English
   locale is a copy of the English. It checks **neither** — read the script: it
   matches one regex for `t('key', { defaultValue: ... })` and compares strings.
   Nothing in the repo enforces hook scope (`react-hooks/rules-of-hooks` is not
   in `eslint.config.js` either), so step 2 is verified by reading the insertion
   site, not by a gate. A doc that credits a gate with a check it does not make
   is worse than no doc: it is why step 2 is easy to skip.
7. Finish with `npm run i18n:parity`, `audit_fe_i18n_drift.py`, `tsc --noEmit`.
