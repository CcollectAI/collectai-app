# Class sweeps — the register

A **screen walk** finds an instance. A **class sweep** finds every other place the
same mistake was made. Five device rounds (`npm run walk`, `docs/ANDROID_LAUNCH.md`
"Screen sweep") missed that every money figure was wrong for non-EUR members,
because the walk account is EUR — where the two formatters agree. One class sweep
found 60 sites in an afternoon.

This file is the register: which classes have been swept, what each found, what
landed, and what is still open. It exists because sweep results kept living only
in a chat session, so the open half was re-discovered instead of fixed.

## The method

1. **Real evidence first.** Walk as a real production account and check the screen
   against the production DB, not against the screen.
2. **Turn each finding into a CLASS** — the sentence form is "X, and nobody
   noticed because Y".
3. **Run the classes in parallel, read-only**, one agent per class, with a brief
   that demands `file:line` + the user-visible consequence, and that ends with
   *"list the false positives you discarded"*. An agent that reports no false
   positives usually did not look.
4. **Verify the agents — do not trust them.** Every sweep so far has contained at
   least one confident finding that did not survive reading the file. Two invented
   API paths were reported as 404s in the 09-16 run and retracted before they
   reached Merle; a fourth bare-date site the agent *missed* was found only by the
   gate written afterwards.
5. **Fix by class, not by instance**: one shared rule, then every call site, then a
   test.
6. **Prove the test** by re-breaking the defect. A guard that asserts the *shape*
   of a fix passes while the effect is broken.
7. **Gates → commit per batch → memory file.**

Two rules the tooling learned the hard way:

- **Resolve per block, not per file** — a marker at the top of a file silences
  every later site in it.
- **Strip comments before matching**, and **make allowlists fail when an entry
  goes stale**, or the allowlist outlives the reason for it.

## Register

| | Class | Swept | Status |
|---|---|---|---|
| A | The client calls an endpoint the server does not serve (or that fails for a real member) | 2026-09-16 | 1 open (server-side) |
| B | A number on screen that its own source of truth disagrees with | 2026-09-16 | ✅ landed `02ee84b` |
| C | The screen shows nothing useful for many seconds although the data is fast | 2026-09-16 | ✅ landed `02ee84b` |
| D | One business rule, implemented twice, drifting | 2026-09-16 | ⚠️ report not retained — re-run |
| E | What the member typed is not what we stored | 2026-09-16 | ✅ closed — gate rule was wrong, 13 sites + validators fixed |
| F | The write succeeded and the screen still shows the old value | 2026-09-16 | ✅ closed 2026-09-17 (item-change chokepoint + both profile caches, tested) |
| G | A paid feature a free member can reach, or a free feature a paying member is denied | 2026-09-16 | 4 decisions for Merle |
| H | The date on screen is not the date that was meant | 2026-09-16 | partly landed; locale half open |
| I | One tap, two writes (unguarded async handlers) | launched 09-16 | ⛔ agents died on a session rate limit — not run |
| J | A member can see data that is not theirs (RLS / IDOR / public views) | 2026-09-17 | ✅ prod verified clean; repo drift fixed + gated |
| M | The database fails, and the app reads the failure as "no" | 2026-09-17 | app half fixed + gated; `20260917b` **applied**; `20260917c` (block→dm_requests + block checks) written, NOT applied |
| N | The client compares a status the database never writes | 2026-09-17 | `getDmStatus` fixed + tested; a per-column enumeration still owed |
| K | The save half-happened (multi-step writes without a transaction) | 2026-09-17 | billing webhook fixed `8439f97` (**not deployed**); item edit, calendar, template fixed; P2P listing insert open |
| L | The control is there but a person cannot use it (touch targets, labels, contrast) | partly, 2026-09-17 | contrast half: 43 icon sites + gate `19a8fdc`, accent 2.02:1 is a brand decision; touch targets + labels ⛔ not run |

I–L were launched as four parallel read-only agents on 2026-09-16 and all four
died within seconds of each other on the account's session limit. The briefs are
worth re-running verbatim; K got far enough to confirm one sharper variant of the
partial-write class before it died (see K below).

## M — blocking is broken in production (2026-09-17)

**Found by walk round 5** (live API, 09-16 20:48, never logged until now):
Settings → Blocked users logged Postgres `42P01`. Read back on production
(read-only), `rpc_list_blocked_v1` and `rpc_is_blocked_v1` both fail with
`relation "user_blocks" does not exist`, and `plpgsql_check` reports the same
for `rpc_block_user_v1` (`user_blocks`, `chat_threads`). So: **a member cannot
block anyone, cannot see who they blocked, and the pre-message block check
fails.**

**Root cause — one character class.** `20260424_security_advisor_bulk_C_and_A.sql`
pinned `search_path` with `format('… SET search_path = %L', 'public, pg_temp')`.
`%L` quotes the whole list as ONE literal, so Postgres stored
`search_path="public, pg_temp"`: a single schema whose name contains a comma.
Inside those functions nothing but `pg_catalog` resolves. Fully qualified
functions (`public.x`) kept working, which is why nothing looked broken; every
bare name fails. **203 functions in `public`** carry it (124 plpgsql, 55 SQL,
24 trigger). Three later migrations copied the quoted spelling by hand. The
security advisor stayed green, because a pinned path of any value satisfies it.

**And the app hid it.** `isBlocked()` logged a `warn` (stripped in release) and
returned `false`. `app/chat/new.tsx` already sets a FAILED state when the check
rejects — its comment says a failed block check must never read as "you may
message this collector" — but the provider never rejected, so that branch could
not run. The 09-15 rule-F fix was defeated one layer down.

**Why rule F missed it:** it only reads `catch` blocks, and supabase-js does not
throw — it returns `{ error }`. The `if (error) { log; return false }` spelling
was invisible, and `false` was not counted as an empty value at all
(ui-playbook "A failed read is not 'none'" listed booleans as not covered).

| landed | |
|---|---|
| `isBlocked` | throws; `chat/new`'s failed state can now run |
| `getPublicUserProfile` | throws on a failed read; `null` only for "no row". `users/[userId]` now says "Couldn't load this profile" + Try again vs "Collector not found" (7 locales). A failed read had also been CACHED as null by swr for the TTL |
| `getMyProfile` | no longer caches `null` for the session on an auth miss (open since 09-15); an auth ERROR rejects |
| announcements | host check + "You"/"Host" label from the session id, not a profile fetch that hid the compose button from the host on failure |
| `searchItems`, `collectionStore` | throw (no callers today) |
| rule F3/F4 in `check-silent-failures` | provider `if (error) … return []/null/0/false`, braced or not; `.catch(() => setX(null))`; `.catch(() => false)`. Each empty return is judged by the reason above IT — the first version let one nested `empty-ok:` exempt the whole block (caught by mutation). 5 mutations red |
| `check:date-locale` | `toLocaleDateString(undefined, …)` is the device locale too; the gate matched only `()`. 2 sites fixed |
| `check:sql-search-path` (new, prebuild) | quoted multi-schema path, literal or via `%L`; 4 historical files allowlisted with a stale-entry check. Proven 4 ways |
| `__tests__/data/userProviderFailures.test.ts` (prebuild) | 7 tests, 3 mutations proven |

**✅ APPLIED 2026-09-17 19:32** — `20260917b` ran on production: 203 → 0 quoted
paths, `rpc_is_blocked_v1` now `search_path=public, pg_temp`. Verified as the
member in a rolled-back transaction: `rpc_list_blocked_v1()` returns 0 rows and
`rpc_is_blocked_v1()` returns false where both used to raise 42P01.
`preflight_rpc_lock` and `preflight_schema_lock` both PASS afterwards (the rpc
lock holds names + params, which an ALTER … SET does not touch), so **no bake
restart was needed** and no restart-time bomb was left.

**…and the search_path bug was hiding a second one.** With the path fixed, a
rolled-back `rpc_block_user_v1` call failed with `relation "chat_threads" does
not exist`: the function still auto-declines pending DMs in the PRE-REWRITE
chat table. Pending requests live in `chat_dm_requests_v1`. So blocking was
broken twice over, and fixing only the path would have looked like a fix while
`Block` still threw. **After a mechanical fix, re-run the user action end to
end — the first error can hide the next one.**

`20260917c_blocking_uses_dm_requests.sql` (written, **NOT APPLIED** — needs
Merle) fixes three things, bodies taken from the live definitions:
1. `rpc_block_user_v1` declines pending `chat_dm_requests_v1` rows in both
   directions (`status='denied'`, `decided_at`, `decided_by`);
2. `rpc_request_dm_v1` refuses when either party has blocked the other — it
   never looked at `user_blocks`, and the app was the only check, so a blocked
   member could still request through the API;
3. `rpc_decide_dm_request_v1` refuses to APPROVE across a block (declining
   stays allowed).
Server-side enforcement elsewhere is fine: `server/app/lib/blocks.py` queries
`user_blocks` directly, so EC2's send-message route and the P2P surfaces have
been honouring blocks all along.
Still open after it: a blocked member with an EXISTING thread can insert into
`chat_messages_v1` straight through PostgREST — the RLS insert policy checks
thread membership, not blocks. EC2's route checks; the direct path does not.

**The original note (superseded):** apply `20260917b_fix_quoted_search_path.sql`.
It re-pins the path UNQUOTED on exactly the functions carrying the broken value
(metadata only; a no-op for qualified functions) and refuses to commit if a
quoted multi-schema path survives in `public`. Before applying, know that it
makes previously FAILING functions start working — for blocking that is the
point, but any worker function that has been silently failing will run.
Could not be verified in a rolled-back transaction here: that DDL (and then
further prod reads) was denied by the session's permission classifier, correctly.
After applying: `select * from rpc_list_blocked_v1()` as a member returns rows
not an error, and the Blocked users screen loads on a device.

Not fixed by it: `rpc_enqueue_push_v1` calls `digest()`, which lives in the
`extensions` schema — still unresolvable on `public, pg_temp`. Other
`plpgsql_check` errors in the same run were NOT this class (e.g. `public.alerts_outbox`
is fully qualified and simply gone; `rpc_anonymize_my_account_v1/v2` update a
column of a view — but nothing in `src`/`app`/`server` calls either; account
deletion is `account_router._do_account_delete`) — dead, not urgent.

## N — the client compares a status the database never writes (2026-09-17)

`getDmStatus` mapped `'accepted'` / `'declined'`. `rpc_decide_dm_request_v1`
writes **`'approved'` / `'denied'`**. Production, read 2026-09-17:
**41 requests `approved`, 5 `pending`, zero `accepted`.**

So for every connected pair the status read as `'none'`, and `'none'` is the
composer: "Message" asked them to send a request they had already had approved,
and each send filed ANOTHER pending row. A decline read as `'none'` too, so it
could be re-requested forever — the decline meant nothing. `chat/new`'s
`'declined'` branch has never been reachable.

Fixed at the mapper (both spellings accepted, so an old row or a rename cannot
reopen it), with 6 tests, 3 mutation-proven. The same function did
`if (error || !data) return 'none'` — a failed read opened the composer, which
is exactly what that screen's failed state exists to prevent. Rule F3 now counts
a sentinel STRING from an error branch; proven by re-breaking this line.

**Not gated, worth a sweep:** every other place the client compares a status
literal to one the DB writes. A regex gate would have to know each column's
vocabulary; the honest move is to enumerate the pairs (client literal ↔ writer)
once, per column, rather than pretend a checker can.

## What landed

All in `02ee84b` "Money: convert it, parse it, and total it from the right source",
on top of `b1f3828` (the `empty-on-failure` class).

- **B / currency** — 60 sites rendered a EUR amount with the member's currency
  symbol and no conversion. `fmtCurrency(amountEUR, settings)` converts;
  `formatPrice(amount, currency)` formats as given. A USD member read "$1.348" for
  €1.347,68; a JPY member was off by ~160×. Write side got
  `memberAmountToEUR(amount, settings)`. Gate: `scripts/check-currency-conversion.mjs`.
- **B / the Items tab total** — the header summed the *loaded pages* (20 at a time)
  under Home's label, so over 20 items the same fact read smaller on Items than on
  Home, and grew while scrolling. `src/lib/portfolioTotalLabel.ts`: the server total
  wins; otherwise the loaded sum, marked `+`.
- **C / first paint** — `AuthProvider` awaited the profile read before rendering,
  costing up to 6s on a cold start. Now `void loadProfile(...)`, with in-flight
  dedupe keyed on the entry (the first version stored the promise and compared the
  wrong object, so it never cleared), and a failed read no longer wipes the profile.
- **E / parsing** — `parseFloat` on a typed amount breaks on "12,50" and
  "1.250,00". `parseMoney` (last separator is the decimal point) at the 4 HIGH
  sites; a local shadow in `useItemDetail` removed. Gate
  `scripts/check-locale-number-parsing.mjs` was fixed — its regex was word-boundary
  anchored and matched no camelCase identifier at all, i.e. it had been passing
  vacuously — and `__tests__/lib/parseMoney.test.ts` was wired into `verify:prebuild`,
  which it was not (a test file is not a gate).
- **H / bare dates** — `new Date('2026-09-16')` is UTC midnight, so an event is
  "past" from 02:00 CEST on its own day. 4 sponsor sites + the week view now use
  `src/lib/calendar.ts`. Gate: `scripts/check-bare-date-parse.mjs`, which found the
  4th site the sweep had missed.

Three of those gates were mutation-proven (break the code → the gate goes red).

## What is open

Verified in the working tree on 2026-09-16; each line names the file so it can be
re-checked rather than re-believed.

**A — endpoints**
- `/collections/user/progress` returns 500 for a real member. Server-side fix,
  needs a deploy.

**J — what was actually true (2026-09-17)**

The sweep reported, at HIGH, that `v_chat_inbox_v1` leaks every DM thread
including `last_message_body`. **It does not, and the report was retracted.**
Production was read back before anyone acted on it:

- the live view ends in `WHERE p.user_id = auth.uid()`;
- `chat_threads_v1` and `chat_messages_v1` both have RLS enabled with
  member-scoped SELECT policies (`chat_*_select_member`, via
  `chat_thread_members_v1`);
- of **231 live views**, exactly **2** are reachable by `authenticated`/`anon`,
  touch per-member columns, and have neither `security_invoker` nor `auth.uid()`
  — and both are deliberate (see below).

What IS real is the drift underneath it: the repo's
`20260430_fix_chat_inbox_view_typing.sql` DROPs and re-creates that view with no
filter and no `security_invoker`. The database was fixed and the repo never was,
so **replaying the repo would have created the leak the sweep described.** Fixed
by `20260917_chat_inbox_view_auth_filter.sql`, whose body is `pg_get_viewdef()`
of the live view — applying it is a no-op against production.

Gated by `npm run check:view-rls`: every view the client reads whose latest
definition touches per-member data must filter by `auth.uid()`, set
`security_invoker = true`, or carry `-- rls-ok: <reason>`. It is mutation-proven
both ways (strip the filter → red; remove the reason → red).
`server/scripts/audit_rls_coverage.py` could never have caught this — it scans
`relkind IN ('r','p')`, tables only, so **every view is invisible to it**.

Decisions, not bugs:
- `user_public_profile_v1` is definer by design and readable by `anon`. Its
  per-member columns are each wrapped in a CASE on that member's own toggle
  (`show_item_count`, `show_collection_value`), verified present in the live
  body — so opting out removes the value rather than hiding it client-side.
  Worth confirming you intend logged-out readability.
- `v_item_best_comp_full` is also `anon`-readable and exposes `market_hits.user_id`
  alongside title/url/price (5 rows today). The client never reads it, so the gate
  does not flag it; revoking `anon` SELECT costs nothing if it is not intended.

**F — stale cache: CLOSED 2026-09-17** (`src/data/CachedDataProvider.ts`)
- The five item mutations each cleared items + portfolio and nothing else, so
  `categories:summaries` (TTL **15 min**) kept the old per-category counts and
  values after an add or delete — and `analytics:metrics` the old totals, while
  `createBuildPaintProject` DID clear analytics. All five now call one
  `invalidateForItemChange()`; five copies of a key list is how one stays wrong.
- A profile lives in **two** caches: userProvider's in-process Map and the SQLite
  `profile:<id>` entry. Privacy settings cleared only the first (so "Show
  collection value" off still showed the number on your own public profile), and
  Edit profile cleared **neither** — `refreshProfile()` fixes AuthProvider's copy,
  not the entry the public profile screen reads, so a new username was invisible
  exactly where other members see it, for the TTL. One `clearProfileCaches()`
  clears both, called from both settings sections.
- Pinned by `__tests__/data/cacheInvalidation.test.ts` (6 tests, both mutations
  proven: dropping the three new keys → 5 red; dropping the SQLite clear → 1 red).
  The key list is written out again in the test ON PURPOSE — importing it from the
  source would make the test follow a removal instead of catching it.

**H — the locale half: CLOSED 2026-09-17.** All twelve hard-coded date sites now
go through `dateLocale()`, kept on the resolved UI language by SettingsProvider
via `i18n.on('languageChanged')`. `npm run check:date-locale` gates it and found
a tenth site the sweep had missed plus five number leaks; `formatNumber`'s
`'de-DE'` default was the same defect one function along. Write-up:
`docs/ui-playbook.md` "A translated screen with an English date". Still open from
H: the server defines "today" twice (Python CEST vs Postgres UTC).

<details><summary>The original list, kept for the record</summary>
- 9 sites hard-code `'en-US'` for a date a member reads:
  `src/components/PriceExplanationSheet.tsx:205`, `src/components/projects/ProjectCard.tsx:30`,
  `src/components/sponsor/AnnouncementsListSection.tsx:22`,
  `src/components/events/WeekViewCalendar.tsx:66` (×2), `app/inbox.tsx:56`,
  `app/chat/[threadId].tsx:116` and `:631`, `app/sponsor/dashboard.tsx:98`.
  A Dutch member reads "Sep 16" where the rest of the app says "16 sep".
  (The `'en-US'` values in `src/lib/format.ts` and `src/lib/settings.tsx` are the
  currency-locale table and are correct — do not sweep those.)
- 2 charts hard-code `"en-GB"`: `src/components/PriceTrendChart.tsx:51`,
  `src/components/PortfolioLineChart.tsx:62`.
- `src/app/(admin)/review.tsx:60` renders a bare `toLocaleString()` — device
  locale, not app locale. (`CategoryLeaderboardSection.tsx:105` has the same bug
  but sits behind `GAMIFICATION_UI_ENABLED`, which is off; its header documents it.)
- Server "today" is defined twice: Python computes it in CEST, Postgres in UTC.

</details>

**E — closed 2026-09-16 (second pass)**
The "~14 MED idiom sites" were not a MED backlog: the idiom is shape 5, wrong on
any amount with a thousands separator, and the gate was recommending it in its
own header. 13 sites fixed onto `parseMoney`, plus `parseMoney`'s own
lone-three-digit-group bug, plus `numeric()`/`positiveNumber()`, which rejected
"12,50" outright and so blocked listing, Add Item and mandates for comma-decimal
members. Full write-up: `docs/ui-playbook.md` "The gate taught the bug".

**Listings count** needs the `+` treatment the Items total got (it prints the
loaded count as if it were the total).

**Suites that are red and gate nothing** — `npx jest` runs 126 suites; **10 still
fail (12 tests)** and none of them is named in `verify:prebuild`. Remaining: four
snapshot suites, `ItemCard` a11y, `analytics`, `marketplace-extracted`,
`usePortfolioInsights`, `settings` (snapshots stale since May), and
`marketMoversTitle` (missing `react-native-purchases` mock). Triage each, then
either fix it or name it in the gate — an unnamed suite is not a gate
(`learning_a_test_file_is_not_a_gate`).

`__tests__/hooks/useItemDetail.test.ts` was the eleventh and is now green and
gated. Its 5 failures were **not** an app defect, and it took a captured stack to
know that rather than a reading: 4 tested `forSaleLoading` / `handleListForSale` /
`handleUnlist`, deleted with the toggle-for-sale chain in `dabfc32` and never
removed from the suite; the 5th omitted `initialPurchasePrice`, which the hook
requires, so `editablePurchasePrice` was `undefined` and `.trim()` threw. The
screen always passes `''`, so the app was never exposed.

**I — one confirmed instance** (the class was never swept; the agent died first)
- `app/purchase/deal/[dealId].tsx:120` `handleDecline` has no in-flight guard and
  its control no `disabled`, while its sibling `handleConfirm` uses `setConfirming`.
  The server's decline is `UPDATE … WHERE status = ANY(_DECLINABLE_STATUSES)`
  (`server/app/agents/purchase_router.py:818`), so the second tap updates 0 rows
  and returns 404 — the member sees "Failed to dismiss" on a deal that was
  dismissed. Discarded as guarded while checking this: `favorites.onUnsave`
  (optimistic removal takes the row away), `users/[userId].handleBlockToggle`
  (closes the menu, then confirms through an Alert), `OfferAmountSheet.handleSubmit`
  (`busy` guard), the three `AppearanceSection` setters (idempotent settings writes).

**K — swept 2026-09-17. The one to fix first is a paying member left on `free`.**

`billing_router.py` claims the webhook in `processed_webhook_events` BEFORE doing
any work (`:1201`), then writes `subscription_events` (`:1226`) and upserts
`subscriptions` (`:1253`). The claim is `INSERT … ON CONFLICT DO NOTHING
RETURNING` and **nothing ever deletes it** — there is no `DELETE FROM
processed_webhook_events` anywhere in the repo. So if the `subscriptions` upsert
fails, the 500-to-force-a-retry at `:1245` is unreachable: RevenueCat's
redelivery short-circuits at `:1202`. The member is **charged, recorded in the
revenue ledger, and stays on `free`** — every paid feature locked, permanently,
with no reconciliation (nothing else reads `subscription_events`). The Stripe
handler at `:640` has the same claim-before-write ordering. Fix: claim after the
writes succeed, or release the claim when a write fails. Server-side, needs a
deploy — your call.

Also open from K, in order: `p2p_listing_router.py:789` creates an `items` row
then a `marketplace_listings` row with **no transaction** (`pool.acquire()`), so
a failed listing insert leaves an item the member never added sitting in their
collection badged "Listed"; ✅ `create-event.tsx` save-as-template — **fixed 2026-09-17.** The template save
was wrapped in its own try/catch that logged and continued, so a member who
ticked "save as template" navigated back believing they had one. The event is
deliberately NOT rolled back — it is what they came to do and it succeeded — but
the toast now says the template was not saved. The copy does not offer to "save
it as a template later": this screen is the only caller of `createEventTemplate`
in the app, so there is no later, and promising one would be the second bug.

**A gap worth gating:** `check-silent-failures --strict` passes that code both
before and after the fix, because the catch *logged*. Rule B asks "was it
logged?" — the same wrong question that let the 74 empty-on-failure sites
through until rule F was written. The shape to catch: a catch inside a
user-initiated action that logs and continues, while the action's PRIMARY write
already succeeded. Nobody has written that rule yet.

✅ `calendar.ts` add/remove — **fixed 2026-09-17.** Adding wrote the OS event
then the mapping; a failed mapping left an event this app could not see, behind
the words "Failed to add", offering itself again — a second tap duplicated it.
It now rolls the OS event back, and says plainly when the rollback ALSO fails
(that is the case where the event really is in their calendar). Removing had the
mirror bug: an event the member had already deleted in their own calendar app
made `deleteEventAsync` throw, the mapping stayed, so the app kept saying "on
your calendar" and every later attempt threw the same way — it now prunes the
mapping when the event is genuinely gone and keeps it when the delete failed for
any other reason. Four tests, two mutations proven.

✅ `useItemDetail` `estimated_value` — **fixed 2026-09-17**, and it was worse
than the sweep reported. Besides being parsed after the first write and dropped
silently, it was written on EVERY save from a field seeded with the DISPLAYED
value — which can come from the model chain — so an unrelated rename filed the
catalogue's number as the member's own estimate. And because only `> 0` was ever
patched, an estimate could not be withdrawn: `NULL` means "we do not know" and
hands the value back to the model. Three mutation-proven tests.

The pattern to copy is `account_router._do_account_delete` — transactional, with
a per-statement SAVEPOINT and a comment explaining why.

**The instance already FIXED (2026-09-17)**
- `useItemDetail.onSaveEdits` writes name/category, then a PostgREST patch, then
  the purchase row — and the cost-basis parse threw *after* the first two landed,
  so an unreadable price saved the name and then said "Failed to save changes",
  with no way to tell which half happened. Every amount is now read BEFORE the
  first write, and the toast names the field instead of the whole save.
  Mutation-proven: restoring the old order turns the new test red. What this
  cannot fix is a network failure between two writes — that needs the server to
  take both in one transaction, which is the rest of class K.

## Decisions for Merle (class G)

Not bugs with an obvious fix — each is a product call.

1. **Pro analytics endpoints are open to free accounts.** Either gate them or stop
   calling them Pro.
2. **`max_daily_deal_alerts` is enforced nowhere.** It is declared in
   `server/app/routes/billing_router.py:170/183/213` and the e2e file
   `server/tests/e2e/e2e_plan_caps.py` asserts the *worker* reads it — check that
   assertion still holds, because the cap does not appear on the serving path.
3. **Sell-timing requires `premium`** (`server/app/features/sell_timing_router.py:53`,
   ranks in `server/app/subscription.py:29` are free 0 / pro 1 / premium 2). The
   client maps a `premium` entitlement (`src/lib/purchases.ts:24`), but per project
   memory only **Free and Pro** are configured in RevenueCat — so no in-app
   subscriber can reach it; only a web Stripe premium price can. Verify in the
   RevenueCat dashboard, then either publish a premium product or lower the gate.
4. **The `internal` EAS profile ships with `EXPO_PUBLIC_BETA_UNLOCK_ALL=true`**
   (`eas.json:75`), which reports every user as `pro` and skips RevenueCat
   entirely. It is deliberate and documented, and `store`/`apk` pin it `false` —
   but `submit.production` points at the same `ascAppId` as `store`, so an
   `eas submit -p production` on the wrong artefact would ship a paywall-less
   build. Worth a submit-time assertion rather than a comment.

## Re-running a sweep

Give the agent: the class in one sentence, a **worked instance** from this repo,
the scope (and what is out of scope), "verify both ends before reporting",
"`file:line` + the user-visible consequence", "rank by money > privacy > social >
cosmetic", and "list the false positives you discarded and why". Read-only, no
edits, no prod writes.

Then write the gate before the fix, and prove the gate fails.
