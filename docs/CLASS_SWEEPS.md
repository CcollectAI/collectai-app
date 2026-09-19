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
| A | The client calls an endpoint the server does not serve (or that fails for a real member) | 2026-09-16 | ✅ closed 2026-09-18 — the last one open (`/collections/user/progress`) was a **response model**, not a query: a required `collection_key` against an `external_id` that is NULL on every production set, so it 500'd for every member, always |
| B | A number on screen that its own source of truth disagrees with | 2026-09-16 | ✅ landed `02ee84b` |
| C | The screen shows nothing useful for many seconds although the data is fast | 2026-09-16 | ✅ landed `02ee84b` |
| D | One business rule, implemented twice, drifting | re-run 2026-09-17 | platform fee unified (6 copies → 1 per side) + parity test; other rules still to enumerate |
| E | What the member typed is not what we stored | 2026-09-16 | ✅ closed — gate rule was wrong, 13 sites + validators fixed |
| F | The write succeeded and the screen still shows the old value | 2026-09-16 | ✅ closed 2026-09-17 (item-change chokepoint + both profile caches, tested) |
| G | A paid feature a free member can reach, or a free feature a paying member is denied | 2026-09-16 | 4 decisions for Merle |
| H | The date on screen is not the date that was meant | 2026-09-16 | partly landed; locale half open |
| I | One tap, two writes (unguarded async handlers) | 2026-09-17 | ✅ swept by checker, 6 fixed + 5 reasoned, `check:double-submit` in prebuild |
| J | A member can see data that is not theirs (RLS / IDOR / public views) | 2026-09-17 | ✅ prod verified clean; repo drift fixed + gated |
| M | The database fails, and the app reads the failure as "no" | 2026-09-17 | ✅ closed 2026-09-18: app half fixed + gated; `20260917b` **and** `20260917c` applied; blocking verified working on prod as a member (block written, pending DM denied, a blocked member's request refused) |
| R | Which endpoints answer without a token | 2026-09-17 | ✅ 21 enumerated, all deliberate; documented in API.md; the one real leak fixed in Q |
| Q | The server's error text is member copy | 2026-09-17 | ✅ 13 fixed to sentences, 10 reasoned + `check_error_copy.py`; one PUBLIC endpoint was leaking DB text |
| P | The SERVER answers a failure with an empty 200 | 2026-09-17 | ✅ 10 handlers raise 503 + `check_empty_on_failure.py`; client type can say "unknown" |
| O | A number rounded into a different fact | 2026-09-17 | ✅ sub-euro prices + sign; found by reviewing a screenshot, not by a checker |
| N | The client compares a status the database never writes | 2026-09-17 | ✅ `getDmStatus` fixed + tested; all 8 status columns enumerated; NO gate (measured: 83 findings, nearly all homonyms) |
| K | The save half-happened (multi-step writes without a transaction) | 2026-09-17 | ✅ all fixed and **deployed 2026-09-18**: billing webhook `8439f97` **+ the three paths it missed** (ledger insert, user lookup, Stripe payload shape) now on one chokepoint per handler, item edit, calendar, template, P2P listing transaction |
| L | The control is there but a person cannot use it (touch targets, labels, contrast) | 2026-09-17 | ✅ all three halves: contrast `19a8fdc` (accent 2.02:1 = brand decision), 6 unlabelled icon-only controls, 20 touch targets + `check:touch-target`. ~145 untranslated labels remain (I18N_BACKLOG) |
| S | The server answered `ok` and wrote nothing | 2026-09-17/18 **deployed** | ✅ **all 34 read**: 6 `ok`-without-a-write fixed, the announcement DM dead five months fixed, 4 money handlers made atomic + row-locked (a trade could complete twice or never; a sale banked twice; a mandate past its cap), 22 of the 34 sites cleared with the reason written down. 8 tests that PINNED the lie rewritten. One decision left: `reports_count` is written, read nowhere |
| T | The server sends it and the app never reads it | 2026-09-18 | measured: **74 of 461** fields declared in `src/api` are referenced nowhere else. Three confirmed: subscription dates ✅ **fixed** (the copy was already translated in 7 locales and rendered by nothing), realised P/L unreachable and the demand differentiator unshown — both product calls. The rest is mostly request params and deliberately-removed UI |
| U | A provider CASTS a snake_case payload to a camelCase type | 2026-09-18 | ✅ all 4 found and mapped (sales, fee schedules, listings, accounts). **All behind `SELLING_ENABLED=false`** — I first called two of them live and the device disproved it. Real, and they ship the day selling is switched on. `tsc` cannot see this class |
| V | The app SENDS a field the server drops on the floor | run 2, 2026-09-19 | ✅ **closed: 57 endpoints proven, 3 unreadable, 0 findings.** One LIVE finding fixed (every verified sale lost its date and venue); 3 dead fields removed; the 3 unreadable are 2 hand-verified clean + 1 behind `SELLING_ENABLED`. The probe was wrong 9 times |
| W | A column the schema carries that no code mentions | 2026-09-18 | measured: **524 across 177 base tables**. Sampled `items` (19 of them): **18 hold no data at all** and the 19th is only its default — schema DEBT, not silent data loss. A cleanup decision, not a bug |
| X | Committed to `web/` and never deployed | 2026-09-19 | ✅ swept and **FIXED**: 1 real drift (`terms.html`, two sentences — one the App Store 4.8 claim), deployed and verified live; 18 of 19 now byte-identical |
| Y | A gate that has never seen its own bug | 2026-09-19 | ✅ swept: **40 of 42 fire** on their own pre-fix commit, **0 blind**. 1 needs `.env` to run, 1 was silent on a clean parent but fires under mutation. The sweep itself was wrong 3 times first |

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

`20260917c_blocking_uses_dm_requests.sql` — ✅ **APPLIED** (verified on
production 2026-09-19: all three RPCs consult `user_blocks` and
`chat_dm_requests_v1`, and none still references the pre-rewrite `chat_threads`).
The "NOT APPLIED — needs Merle" this line used to carry was stale. It fixes
three things, bodies taken from the live definitions:
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
✅ **CLOSED 2026-09-19 by `20260919a_chat_insert_respects_blocks.sql`
(applied).** A blocked member with an EXISTING thread could insert into
`chat_messages_v1` straight through PostgREST — the policy asked only "are you a
member of this thread?". EC2's route checked; the direct path did not.

**Two traps, and the rolled-back test on production caught both:**

1. **The duplicate policy.** `chat_messages_v1` carried TWO INSERT policies —
   `..._insert_member` and `..._insert_member_self` — with byte-identical WITH
   CHECK. Policies for one command are **OR'd**, so adding the block condition
   to one of them would have changed nothing. The duplicate is dropped; there is
   one place to be wrong now instead of two.
2. **The first fix let the blocked party through — the exact person the rule is
   for.** It joined `user_blocks` inline, and `user_blocks` has its own RLS:
   `blocks_select USING (blocker_id = auth.uid())`. A policy subquery runs as
   the INSERTING user, so the blocked party cannot see the row, `NOT EXISTS` is
   trivially true, and the insert is allowed. Measured, not reasoned: the
   blocker was REFUSED and the blocked party was INSERTED. **A check that reads
   a table the caller cannot see is not a check.**

It now calls `rpc_is_blocked_v1` — SECURITY DEFINER, STABLE, already symmetric
and already `search_path`-pinned by 20260917b. Proven in a rolled-back
transaction on production: allowed with no block, REFUSED afterwards in **both**
directions. `preflight_rls_check`, `schema_lock`, `rpc_lock` and `models` all
PASS after applying, so no restart-time bomb; `service_role` bypasses RLS so the
app's own send path is untouched.

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

## I — one tap, two writes: swept by a checker, not by reading (2026-09-17)

The class had never been swept (the agents died on a rate limit on 09-16); the
register carried ONE confirmed instance. A 120-line checker
(`scripts/check-double-submit.mjs`) found **13** after its own false positives
were removed, out of ~40 writing tap handlers.

**Fixed — a second run does real damage:**

| site | what the second tap did |
|---|---|
| `events/[eventId]` RSVP × 3 | **money**: Going on a PAID event opens a Stripe ticket checkout, so two taps started two checkouts for the same ticket. The other two write the same `event_attendees` row while optimistic counters move. One shared `rsvpWritingRef` |
| `sponsor/dashboard.handleConfirmTier` | **money**: a second sponsor SUBSCRIPTION checkout, and both `track()` events fired again, so the funnel counted taps as intents |
| `purchase/deal/[dealId].handleDecline` | the known instance: the server declines `WHERE status = ANY(_DECLINABLE_STATUSES)`, so tap 2 updated 0 rows → 404 → **"Failed to dismiss" about a deal that was dismissed**. Its sibling `handleConfirm` had been guarded all along |
| `categories/[categoryId].handleToggleFollow` | a follow and an unfollow for the same row, ordered by the server, so the pill could disagree with what was written |
| `useItemGallery.handleGalleryDelete` | the row only leaves after the call returns, so the same photo could be deleted twice → 404 → "Failed to remove photo" about a photo that is gone. Latch is per IMAGE ID: deleting two photos at once is legitimate |

**Reasoned, not fixed** (`// double-tap-ok:` with a checkable sentence): chat's
Retry (the control is rendered only for an id in `failedMessageIds`, and the
first line removes it), Favourites' unsave (optimistic removal takes the control
away), `ListForSaleModal` (the guard is `useListForSale.submit`'s own
`if (!canSubmit || submitting)`), and AppearanceSection ×3 (an idempotent
`PUT /settings` of the value just picked, picker closed before the await).

**The checker was wrong four times before it was right, and each way matters:**

| wrong | fix |
|---|---|
| a fixed VERB list for latch names missed `setCreating`, `setMarkingAllRead`, `togglingComplete` — 3 false positives, which is how a gate becomes ignorable | judge the flag's NAME (a regex over `ing`, `busy`, `pending`, `loading`, …), not a list I thought of |
| testing the END of the name re-flagged `if (restoringId) return` | CONTAINS, plus "a single bare identifier guarding a writing handler is a latch by position" |
| `[^)]*` for the condition stopped at the first `)`, so `if (ref.current.has(id)) return` could not see its own guard | balanced-paren scan |
| a ONE-LINE lookback for `double-tap-ok:` ignored every reason I had written (they are 3 lines) — the same bug `check-view-rls` had with a 4-line window | read the whole contiguous comment block |

And one real weakness the mutations exposed: `ref.current = true` was accepted
on its own. **An assignment nothing reads stops nothing** — a ref latch now
counts only when some `if (…ref.current…)` reads it. Five mutations red,
including "drop only the READ and leave the assignment".

## L — the control is there but a person cannot use it (2026-09-17)

The contrast half landed in `19a8fdc`. The other two halves had never been run.
Both were measured before anything was touched, and the FIRST measurement was
useless — it reported 53 unlabelled pressables and 295 "small" sizes, which is a
list nobody can act on. Neither number was a defect count:

- a button with a `Text` child is announced by its text, so a missing
  `accessibilityLabel` is only a defect when the control is **icon-only**;
- most "small" numbers were progress-bar heights, dots and spacers, not touch
  targets — a size is only a touch target if it is the pressable's OWN style.

Re-measured on those two shapes: **6** and **20**.

**6 icon-only controls announced nothing** — five close buttons (region picker,
two category pickers, the condition sheet, the suggestion modal) and the search
field's clear button. All now carry `accessibilityRole="button"` and
`t('common.close')` / a new `common.clear_search_a11y`, in 7 locales.
`AuthTextInput`'s wrapper got the opposite treatment: it is a `Pressable` that
only forwards a tap to the `TextInput` it wraps, so it is now
`accessible={false}` — announcing it would have put a second, nameless control
in front of every field on the auth screens.

**20 controls under 44pt** (Apple asks 44, Android 48) now carry `hitSlop`,
which grows the touchable area without re-laying out the row —
`app/chat`'s 36pt send arrow, two 28pt quickscan buttons, the calendar arrows,
the campaign row's ⋯, the 28pt quick-buy. **The slop is directional, and that is
the whole subtlety**: neighbouring hit rects overlap and the topmost one wins, so
a pair 6pt apart with 8pt of slop each makes the boundary between them
ambiguous — a worse bug than the small target. Free sides get 8; a shared side
gets at most half the measured gap (`heroActions` gap 8 → 4, the quickscan row
gap 6 → 3). Gated by `npm run check:touch-target`.

Two things the gate got wrong, both found by proving it rather than running it:
- a scripted edit put `hitSlop` INSIDE a multi-line `style={[…]}` array in
  `app/chat/[threadId].tsx` — a syntax error, caught by reading the diff (and
  tsc would have caught it too). 19 of 20 edits were right; the 20th is why you
  read the diff of a scripted change.
- the reason marker could not be written where it was needed: in JSX child
  position a `//` comment is a syntax error, and the scanner only accepted
  `//`, `*`, `/*`. **A gate must accept the spelling its own error message
  demands** — `{/* touch-ok: … */}` now counts. Proven: drop the slop → red; a
  reason inside the style object → still red; the JSX comment → green.

Still open in this class: ~145 hard-coded (English) `accessibilityLabel`s ranked
in `docs/I18N_BACKLOG.md`, and the 28pt controls reach 44 vertically but only
~36 horizontally — closing that needs a layout change, which is a design call.

## D — the platform fee was written six times (re-run 2026-09-17)

The 09-16 report was lost with a crashed session, so the class was re-run from
scratch. The first rule enumerated: **the 5% ticket fee, in six places.**

| where | what it was |
|---|---|
| `events_core.py` ticket checkout | `int(ticket_price * 0.05)` — what we CHARGE |
| `billing_router.py` webhook | `int(amount * 0.05)` — what we RECORD as charged |
| `EventTicketingSection` | "A 5% platform fee applies to paid tickets." — what the organiser is promised |
| `app/legal/terms.tsx` ×2 | "A platform fee of 5% is applied to ticket sales", "include a 5% platform fee" — what a member can hold us to |

All six said 5%, which is what this class looks like right up to the day someone
changes one of them. Two of the six are legal copy and one is the actual charge;
a rate that drifts between those is not cosmetic.

Now one constant per side — `app.lib.money.PLATFORM_FEE_PCT` with a
`platform_fee_cents()` helper (truncating, as both call sites did: the fee never
rounds up against the organiser) and `PLATFORM_FEE_PCT` in
`src/constants/fees.ts`, interpolated into the hint (new key
`events.ticket_fee_hint`, 7 locales) and both Terms sentences.

`server/tests/test_platform_fee_parity.py` reads the TypeScript file so neither
side can move alone — the same arrangement as `test_currency_symbol_parity.py` —
and fails on a SEVENTH copy appearing. CI's `pytest tests/` collects the whole
directory, so unlike a jest suite it needed no wiring to be a gate.

Mutation-proven four ways: client rate → 7% red; `int()` → `round()` red; a bare
`int(x * 0.05)` back in the checkout red; a hard-coded fee sentence red. **The
last one only went red after a fix**: the copy scan matched "5% … fee" but not
"fee of 5%", so re-hard-coding the Terms sentence — the exact line this sweep
started from — passed. Both orders now.

**The second rule enumerated: the MARKETPLACE fee, and here the two copies did
not agree.** `CreateListingModal` computes a preview and shows NOTHING until the
server's fee schedule arrives; `useListForSale.calculateFee` falls back to
`MARKETPLACE_OPTIONS.defaultFeePct` — a client guess — and the breakdown rows
printed `-€12,90 / €87,10` with nothing to say the rate was assumed. The picker
chip beside them already said "~12.9% fee". eBay's real fee is not one flat
number, so that figure can be wrong by euros on a real listing, in the sheet
where a member decides what to charge.

`FeeBreakdown` now carries `estimated`, the rows read "Fees (estimated)" with a
`~`, and three tests pin it (both mutations red: the fallback claiming to be
exact, and a server schedule marked as a guess). The formulas themselves agree,
so they were left where they are — the defect was the CONFIDENCE, not the maths.

**Still owed for this class:** plan limits (already parity-gated by
`check:billing-limits-parity`) and "today", which the server defines twice —
Python in CEST, Postgres in UTC (class H's leftover).

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

### The enumeration, and why this class gets NO gate (2026-09-17)

Done properly rather than left as a to-do: 40 status literals the client
compares, against the live vocabulary of all 8 client-read tables that have a
`status` column (CHECK constraints where they exist — the constraint is the
vocabulary; the observed rows are a sample, and a 1-row table tells you nothing).

| checked | verdict |
|---|---|
| `catalog_suggestions` `mapped` | ✅ in the CHECK |
| `marketplace_listings` `draft` (what the sell dashboard creates) | ✅ in the CHECK |
| `marketplace_sales` `pending`/`shipped`/`completed` | ✅ in the CHECK |
| `subscriptions` allows `canceled` (one L) while the client says `cancelled` | **not a bug** — every `'cancelled'` in the client is the EVENT status (`EventStatus = draft \| published \| cancelled`), a different column. Checked before reporting |
| `events` has 558 `rejected` rows and the client's `EventStatus` has no such value | **not reachable** — the server filters rejected events out of every read (`9fa8336`), which is why the client never needed the word |
| `chat_dm_requests_v1` `approved`/`denied` | ❌ the real bug, fixed above |
| `build_paint_projects` | latent drift, below |

**A gate for this was measured and rejected.** `schema.lock.json` already
carries each CHECK's literal set, so the read-side mirror of
`check:constraint-drift` looks easy: flag a comparison literal no CHECK allows.
It produces **83 findings, almost all false** — `.status === 'fulfilled'` is
`Promise.allSettled`, `.type === 'header'` is a list row, `.kind === 'meetup'` is
an app-level union. Keying on a column NAME keys on a homonym
(`feedback_same_name_is_not_the_same_thing`), and a checker that cries wolf
stops being read. The enumeration above is the deliverable; the gate is not
worth having until something can tell which table an object came from.

**`build_paint_projects`: a migration that never reached production.**
`20260322_build_paint_status_pipeline.sql` migrates `Active → in_progress`,
`Backlog → wishlist`, `Completed → finished`, adds a 25-value CHECK and rewrites
three RPCs. On prod today: the column DEFAULT is still `'Active'`, there is **no
status CHECK**, `rpc_create_build_paint_project_v1` does not mention
`in_progress`, and the single existing project reads `active`. The client has
spoken the new vocabulary since March.

**No member sees a defect today, and that is a finding, not luck**: the screen's
groups are "completed", "wishlist", and *everything else* → in progress, and
`isCompleted` lowercases before comparing, so a legacy `Active` row lands in the
right group. What is actually missing is the GUARD — nothing stops a bad value
being written, and the RPC and the client now write two different vocabularies
into one column. Applying that migration is Merle's call (it rewrites RPCs and
migrates data); it is not urgent, and it should not be replayed blind.

## R — which endpoints answer without a token (2026-09-17)

Prompted by finding `/pipeline/status` public while annotating it as
"operator-facing". If one endpoint's audience was an assumption, the rest were
too, so the whole surface was enumerated: **21 handlers** with no auth in the
signature or decorator, no router-level dependency and no in-body key check.

**Outcome: no hole.** All 21 are deliberate — catalogue and taxonomy reference
data, set data, fee schedules (the handler's docstring says "public, no auth
required"), a sponsor's public profile, the two provider webhooks (each verifies
its own signature), the beta-signup form, the CSV template, health endpoints, and
the photo capability URL whose boundary is `_PHOTO_KEY_RE` and whose docstring
says so. The one real defect — the public endpoint returning `str(e)` — is fixed
in class Q. The full list now lives in `docs/API.md` so "public by design" can be
told apart from "public by accident" without re-deriving it.

**The sweep took three iterations, and each wrong version was wrong the same
way.** A hand-written list of dependency names missed
`require_seller_age_verified` (it returns the user id). Reading only the
signature missed `dependencies=[Depends(get_current_user_id)]` in the DECORATOR
(`/vision-predict/classify`). Ignoring `APIRouter(dependencies=…)` would miss a
whole file at once. **44 → 24 → 21**, and the first number would have been
reported as 44 unauthenticated endpoints including `PUT …/accounts/defaults/ebay`
— a false alarm about writing another member's eBay settings.

No gate written: the honest check is "documented Auth matches the code", which
needs path resolution through router prefixes and mounts (`main.py` mounts each
router twice, bare and under `_v1`). The enumeration is in API.md and cheap to
re-run — `/tmp` probe in the commit, three ways of being wrong written down.

## Q — the server's error text is member copy (2026-09-17)

`src/lib/userErrorMessage.ts` shows **the server's own sentence** when the server
wrote one. That is deliberate — and it makes `detail` a UI string, so a handler
answering with `str(e)` ships a library's wording, and sometimes internals, to a
member. The client's `check:raw-error-copy` polices its own side; this is the
half it cannot see.

Swept `server/app/**` for route handlers that put a caught exception into the
response: **24**. Triaged by AUDIENCE, which is the only way to tell a leak from
a deliberate message — and that meant reading each endpoint's auth:

| fixed to a sentence | what it used to ship |
|---|---|
| `marketplace_listing_router.publish_listing` | `f"eBay publish failed: {e!s}"` — eBay's or httpx's wording, on a money path |
| `mfa_router.mfa_unenroll` | `f"Failed to remove MFA factor: {exc}"` — GoTrue internals, in security UX |
| `data_moat` health + prediction-accuracy | `f"db_error: {e}"` — asyncpg names tables and columns |
| `uploads_router` presign + signed-get | botocore's text |
| `warm_tier_router` query + count | asyncpg's text — and this router takes `Depends(get_current_user_id)`, so **any signed-in member** could reach it |
| `attribute_autocomplete_router` | an ImportError carrying a module path |
| `notification_feedback_router` ×3 | `{"ok": false, "error": str(e)[:120]}` to a client that fires `.catch(noop)` and never reads the body |
| `image_optimizer` (a lib, not a handler) | `ValueError(f"Cannot decode image: {exc}")` → "cannot identify image file <_io.BytesIO object at 0x…>", passed straight through by `photo_upload_router` into a 400 the member reads |

**Kept, with a written reason** (`# raw-error-ok:`): the three validator
pass-throughs whose text is OURS and written for a person — `app/ssrf`'s "URL
points to a private/internal IP address", `s3_storage`'s "content_type not
allowed: image/tiff", `warm_tier`'s "limit too high — split into chunks" — and
seven ops endpoints, each verified to be behind an ops key (`require_ops_key`, or
`_check_ops_key` in the body — two different styles, both real).

**The correction worth keeping.** I annotated `/pipeline/status` as
"operator-facing, the exception text is the useful half". Then I read the code:
that router declares no auth dependency and `main.py` mounts it bare, so it
answers **anyone**. The text is gone from the response and the annotation now
says why. An audience is a fact about the code, not an impression about the name.

Gated by `server/scripts/check_error_copy.py` (in `verify:prebuild`),
mutation-proven: eBay's text back → red; the DB text back in a member-reachable
handler → red; a written reason removed → red; and a reworded sentence with no
exception in it stays green.

## P — the SERVER answers a failure with an empty 200 (2026-09-17)

Rule F has policed "a failed read is not 'none'" on the client since 09-15. It
can only see code it can read. A handler that catches its own exception and
answers **200 with an empty payload** is invisible to it — the client receives a
well-formed answer and renders it as fact.

Swept `server/app/**` mechanically. 270 `except: return <empty>` sites is not a
finding list (most are helpers where `None` legitimately means "no value"), so
the scan was narrowed to **route handlers**: 19, of which these mattered.

| handler | what it told the app |
|---|---|
| `portfolio_overview` ×2 paths | `{"total_value": 0, "item_count": 0, "items": []}` — the sentence Home puts in its hero, on a DB failure |
| `portfolio_timeseries` ×2 | `{"points": []}` — "your portfolio has never moved" |
| `portfolio_items` ×2 | `{"items": []}` — "you own nothing" |
| `category-stats` / `category-health` / `category-correlation` | empty lists |
| `alerts/trigger-history` | `{"triggers": [], "unread_count": 0}` — **and that zero clears the badge** |

All now `raise error_response(503, …, code="DB_UNAVAILABLE"/"DB_ERROR")` when the
query AND the Signals proxy fallback both fail. Documented in `docs/API.md`.

**The client half was already built and unreachable.** Home's `valueUnknown`
renders "—" and hides the estimate line when `seriesFailed` is set — and
`seriesFailed` is only set when the fetch THROWS. A 200 with `{"points": []}`
therefore drove Home straight past its own failure state, which is why the
2026-09-15 work could not fix this from the client side.

**And the client's fallback made the same claim one layer up:**
`getPortfolioSummary`'s catch returned `{ total: 0, …, itemCount: <real count> }`
— "your 8 items are worth €0" — because `PortfolioSummary.total` was typed
`number`, so the provider could not say "unknown" even though
`PortfolioValueHeader` has rendered "—" for `null` since 09-15. The type is
`number | null` now.

Gated by `server/scripts/check_empty_on_failure.py` (in `verify:prebuild`),
mutation-proven four ways: zeros back in the overview → red; `{"health": []}`
back → red; a written reason removed → red; and a payload that SAYS it failed
(`{"status": "error", …}`, the pipeline diagnostics) stays **green**, which is
the distinction the gate exists to make.

Two things the sweep got wrong first, both fixed in the gate: it reported
`import_router`'s nested `_num()` helper (a blank spreadsheet cell legitimately
has no number — `continue` inside `ast.walk` skips one node, never its subtree),
and `False in (None, 0)` is True in Python, so booleans folded in silently.

Also removed here: `data_moat`'s failure payload carried `str(e)` — the raw DB
exception text — to any caller holding a token. The client never read it.

## O — a number rounded into a different fact (2026-09-17)

**Measured properly for the docs:** the screen reads `mv_catalog_item_price`, and
**89,314 of its 184,220 rows (48%)** are between €0 and €1 — so nearly half the
browsable catalogue rendered as €0. Verified fixed on the device: an MTG card
priced €0.07 now shows "~€0,07 · Median of 100 recent market prices" where it
used to show "~€0".


Not found by any checker: by opening a screenshot from the round the machine had
called `ok`. The catalogue item read **"~€1"** under "Median of 213 recent market
prices", which sent me to `money()` — `maximumFractionDigits: 0` for every
amount, so **anything under €1 printed as `€0`**, the app's own string for "we do
not know what this is worth".

**885,445** production catalogue prices are between 0 and 1. The rounding rule
was displaying the majority of the cheap catalogue as worthless. Fixed at the
chokepoint (cents below one unit, `<€0,01` below half a cent, `<¥1` where there
is no minor unit) with the sign moved outside the symbol, 7 tests, 4 mutations
proven. Write-up: `docs/ui-playbook.md` "A 30-cent card is not worthless".

**Why no gate:** the defect is in ONE function, and the tests pin its table of
cases. A checker would have to know which numbers a member reads as money, which
is the homonym problem from class N.

**The transferable part** — the machine checks cannot see a number that is
merely WRONG, only one that is missing or raw. Reviewing screenshots is not
optional decoration after a walk: rounds 1-11 all passed this screen.

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

**A — endpoints: CLOSED 2026-09-18**

`/collections/user/progress` returned 500 for every member, always — and the
cause was not the query, which runs fine against production. It was the response
model. `UserCollectionProgress.collection_key` was a required `str` mapped from
`sets.external_id`, which is **NULL on every set on production** (3 of 3,
checked 2026-09-18). Pydantic rejected every row, the handler's
`except Exception` (`collections_router.py:224`) turned the ValidationError into
`500 Failed to get collection progress`, and the log line said "Failed to get
user progress" with no hint that the shape was the problem — which is why a
sweep that reads the SQL cannot find this one.

The fix is the type, not the data: `collection_key: Optional[str] = None`. These
sets are NOT omitted instead, because `docs/HELP_AND_GUIDES.md` reserves omission
for a set whose **size** is unknown ("omitted rather than given an invented
total"), and all three have real sizes (15, 25, 15) and real names. Only the
external key is missing, so the honest answer returns the progress and says the
key is absent; a caller needing a stable key uses `collection_id`, which is what
`FeaturedCollectionsSection` already does.

Three tests in `server/tests/test_collections_progress.py`, mutation-proven:
restoring the required `str` turns two of them red with a ValidationError. The
two sibling models in that file (`CollectionSummary`, `CollectionDetail`) still
declare a required `collection_key: str` and that is fine — neither is ever
constructed from production data (`list_collections` returns empty and the detail
handler 404s, per the 2026-04-30 module note), so there is no second instance
hiding behind the same field name.

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
`docs/ui-playbook.md` "A translated screen with an English date".

**H's server half — ✅ CLOSED 2026-09-18, and it was measured rather than
assumed.** The EC2 box is **Europe/Paris (CEST, +0200)**; Postgres reports
**UTC**. So `date.today()` and `CURRENT_DATE` are different dates between
**00:00 and 02:00 CEST — two hours every night.**

Two places used both definitions for the SAME predicate:

* **Events.** `build_event_conditions` and `list_events` bound `date.today()`
  into `date >= $N`, while `list_nearby_events` wrote `date >= CURRENT_DATE` —
  and `docs/EVENT_QUALITY_PLAN.md:215` states the canonical gate as
  `(p_include_past OR e.date >= CURRENT_DATE)` and names *both* as places that
  must match it. In that window an event happening today was still upcoming on
  one screen and already gone from the other.
* **Challenges.** `start_date <= $2 AND end_date >= $2` against a host-clock
  date, so a challenge ending today dropped out of its own window early.

All now compare the database's date columns against the database's clock, which
also removes a bound parameter from each (and shifts every later `$N` down one —
the five `test_events_helpers` assertions that pinned the numbering were updated
with it, and the caller threads the returned `param_idx` so nothing else moved).

**Enumerating first is what kept this small: 12 host-clock sites, and only 3
were wrong.** Reading each one mattered more than sweeping them:

* the **streak** dates (`gamification_router`) are written to AND compared
  against `last_activity_date` — `$3` on both sides, never `CURRENT_DATE` — so
  they cannot disagree with the database. Converting them would have shifted
  every member's streak boundary by two hours and disagreed with every row
  already stored, and neither UTC nor CEST is the member's own midnight. A
  blanket "make it all UTC" would have broken working behaviour to fix nothing.
* a draft's default date, an admin dashboard's 7-day window, an ML year read at
  import, and a lead-time score are all fine on the host clock.
* `pricecharting_caller` was wrong and not obvious: it STORES `sold_at` on
  `market_hits`, so every scraped sale in that window was filed a day ahead —
  the exact trap `docs/ARCHITECTURE.md` already names.

**Verified live at 00:01 CEST on 2026-09-19 — inside the window, which is the
only time it is observable.** On production, with the deploy in place:

```
host date.today()     : 2026-09-19   (Europe/Paris)
postgres CURRENT_DATE : 2026-09-18   (UTC)   ← they disagree right now
gated upcoming, CURRENT_DATE : 247   ← what GET /events answered
gated upcoming, host date    : 239   ← what it would have answered before
gated events dated exactly CURRENT_DATE : 8
```

So **8 real events dated today vanished from the events list for two hours every
night**, while `GET /events/nearby` — which has always used `CURRENT_DATE` —
still listed them. The API now returns the `CURRENT_DATE` number, which is how
the fix is known to be live rather than merely deployed.

Gated by `npm run check:server-today`: a bare `date.today()` / `datetime.now()`
under `server/app` or `server/workers` needs `CURRENT_DATE`, `utc_today()`, or a
`# tz-ok:` reason. Mutation-proven — reverting the events fix exits 1, removing
a reason exits 1, a clean tree exits 0.

**The gate was wrong twice first, both times about its own text.** It reported a
`-- CURRENT_DATE, not a bound date.today()` note inside a triple-quoted SQL
string, because it stripped only `#` comments and not `--`; and its 4-line
look-back was shorter than the seven-line streak reason, so the marker could not
be written where it was needed. Same two failure modes as
`check:cast-not-mapped` and the `partial-ok:` marker earlier the same day.

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

**Listings count — ✅ FIXED 2026-09-18, and it was 3 sites, not 1.**
`app/listings.tsx` pages at 24, so its header printed "24 listings" for a
result set of 200 and the number grew while the member scrolled. There is no
server total to prefer — `GET /marketplace/listings` returns
`ListingListResponse { listings }` and no count — so rule 2 of
`portfolioTotalLabel` applies: mark the partial number.

**Enumerating the class instead of fixing the reported site found two more, in
the file that had already been fixed.** Of the six screens using
`usePaginatedList`, `app/(tabs)/events.tsx` writes the `+` inline four times and
had got two: `Past Events (N)` and `Events on <date> (N)` are client-side splits
of the SAME paginated list as `Upcoming (N+)` and `All Events (N+)` directly
beside them, so they were partial in exactly the same way. All four now go
through one `partialCount(loaded, hasMore)` (`src/lib/partialCount.ts`), which
`listingsCountLabel` also uses — the marking is one decision, which is what the
four inline copies were not.

Discarded as a false positive: `app/(tabs)/items.tsx:802` passes
`totalCount={providerItems.length}` to `BulkActionsToolbar`, which never renders
it — only `isAllSelected` reads it. "Select all" selecting the loaded rows is a
behaviour question, not a number on screen that lies. (`totalCount` being an
unread prop is class T, not this.)

8 tests across the three helpers. The plural follows what exists rather than the
digits: with more pages waiting there is certainly more than one listing, so
"1+ listings" and never "1+ listing".

**The fix was one edit away from being undone, and the tests could not see it
(gated 2026-09-18).** Both helpers take the flag as an ARGUMENT, so passing
`false` puts the bug straight back. Mutating all three call sites to `false`
was caught by **nothing**: 137 suites green, `tsc` 0. The helper tests pin the
helpers, not the wiring, and no test renders a 1,300-line screen.

`npm run check:partial-count` (in `verify:prebuild`) rejects a boolean LITERAL
in the flag position unless a `partial-ok:` reason sits within three lines
above. Mutation-proven both ways: the three-site mutation exits 1 (4 findings,
including a `true`), a marker pushed out of the window still exits 1, and a
clean tree exits 0.

Two details it was designed around:

* **The marker had to be writable where it is needed.** The one legitimate
  literal is the footer's "That's all N listings", inside `!hasMore` — and it is
  in JSX children position, where `//` is not a comment but rendered TEXT. The
  checker accepts `{/* partial-ok: … */}`, and the marker was written at that
  exact site and re-verified (`tsc` 0) rather than assumed writable
  (`learning_four_ways_a_new_gate_is_wrong`, failure mode 2).
* **What it does not catch, said out loud:** a NEW screen that renders
  `list.length` and never adopts either helper. That shape was swept by hand
  across all six `usePaginatedList` screens; making it decidable means telling a
  count apart from a `=== 0` guard, and the attempt produced more noise than
  findings. The checker's header says so, so nobody trusts it further than it
  goes.

**Suites that are red and gate nothing — ✅ CLOSED 2026-09-18. 137/137 green,
1173 tests, and the gate no longer keeps a list.**

It was **13** red suites (17 tests), not 10, and **not one was an app defect** —
they were stale pins, which is the same finding as the server suite's 31→7 triage
(CLAUDE.md, 2026-08-19). The doc decided each one, not the test:

| suite | pinned | the truth |
|---|---|---|
| `PermissionScreen` | `getByText('Go Back')` | the copy moved to `t('common.go_back')` → "Go back". Red over a capital B while the escape hatch was present all along. Now queried by accessibility LABEL, which is the guarantee worth asserting |
| `ItemCard` | `category: 'Yu-Gi-Oh'` → itself | a value in NEITHER vocabulary (slug `yugioh`, curated `Yu-Gi-Oh!`), so `categoryDisplayName` correctly title-cased it. The fixture was one the app never stores |
| `ItemCard.a11y` | `getByText('lego')` | the RAW slug — pinning the defect `formatCategoryName` exists to prevent. The curated name is `LEGO` |
| `analytics` | imported `WinnersLosersSection` | deleted as an orphan in `65ea3ee`; the import stopped the whole file running, so the two components that DO exist were untested behind a file that looked like it covered three. Revealed 3 more stale pins underneath |
| `marketplace-extracted` | imported `DemandHeatBanner` | went with the market hub in `b15d936`; same shape — `RegionalInsightsSection` is on screen and was untested |
| `usePortfolioInsights` | the hook | removed with `<InsightsCard/>` on 2026-08-27, deliberately. Suite deleted |
| `useListForSale` | `toggleMarketplace('collectai')` | renamed to `sparrow` everywhere in `5e7e7af`, so the key was absent and the hook threw on `prev[mpId].selected` |
| `marketplaceListingsEnvelope` | rows come back **untouched** | "untouched" WAS the bug: class U replaced four casts with real mappings. The test was pinning the cast |
| `marketMoversTitle` | imported from the component | which now loads the RevenueCat SDK through the Pro gate; jest cannot parse its ESM. `marketMovers.test.ts` already carried the fix (import the pure `moverFormat`) and this one was never migrated |
| 4 snapshot suites | `pokemon`, `lego`, `Items`, `Search` | the category vocabulary (`Pokémon`, `LEGO`), the Explore/Market rename (`f51d1a7`, 2026-08-19), `hitSlop` from the touch-target sweep, and a "View public profile" control added in `64a598d`. Every delta dated and deliberate before any `-u` |

Two things the triage found that the report had not:

1. **`QuickNavBar` has no Items tab.** A case named "matches snapshot with Items
   tab active" set `/items/123`, which highlights nothing — a duplicate of the
   "no tab active" case, named for a tab that does not exist. Renamed to what it
   actually asserts (the bar overlays item detail and must not claim a tab).
2. **A test that could not fail.** The analytics fixture `hot_toys` title-cases
   to "Hot Toys", which is *also* its curated name, so it passed whether the
   vocabulary was consulted or not. Proven by mutation — with the
   `CATEGORY_SLUG_TO_NAME` lookup disabled it stayed green. Now `lorcana` →
   "Disney Lorcana", which can only come from the table.

**The gate was the bigger finding: it named 67 suites and `jest` collects 137, so
70 suites — more than half, most of them green — gated nothing.** The reported
"10 red and ungated" was a symptom of a hand-maintained list, which is the
`learning_a_test_file_is_not_a_gate` shape one level up: every test file added
since has been ungated by default, silently. `verify:prebuild` now runs `jest`
with no list. The whole suite takes ~19s, so there was never a cost reason for
the list.

Mutation-proven: disabling the category-name lookup exits **1** (8 suites red,
**6 of them previously ungated**), and a clean tree exits **0**. The trade,
stated deliberately: a snapshot suite in the gate means an intentional UI change
now fails prebuild until someone regenerates and reads the diff — which is
exactly what did not happen while four of them sat stale since May.

`__tests__/hooks/useItemDetail.test.ts` was the eleventh and is now green and
gated. Its 5 failures were **not** an app defect, and it took a captured stack to
know that rather than a reading: 4 tested `forSaleLoading` / `handleListForSale` /
`handleUnlist`, deleted with the toggle-for-sale chain in `dabfc32` and never
removed from the suite; the 5th omitted `initialPurchasePrice`, which the hook
requires, so `editablePurchasePrice` was `undefined` and `.trim()` threw. The
screen always passes `''`, so the app was never exposed.

**I — a SECOND instance, and the gate was blind to it for two independent
reasons (2026-09-19).**

`app/listing/[id].tsx` `handleDelist` awaited `delistListing(id, "sold")` with no
in-flight guard and no `disabled` on its control — the same shape as the
purchase-deal decline, so a second tap hits a listing the server has already
sold and the member is told their sale failed when it succeeded. It also only
logged on failure, so a failed sale and a successful one looked identical. Both
halves fixed against the sibling `handleSavePrice` in the same file.

**`npm run check:double-submit` passed it clean**, and there were two separate
causes — fixing the obvious one left the checker green:

1. **The write-verb list had `unlist` but not `delist`**, and `\b` cannot match
   `list` inside `delistListing`. The checker's own header says a guard is
   recognised by the flag's NAME rather than a list of verbs someone thought of
   — but the WRITE side is still exactly such a list.
2. **A null check read as a latch.** `isFlag` matches the substring `ing`, so
   `if (!listing) return` looked like an in-flight guard because the noun
   `listing` ends in -ing. Any -ing noun does it: rating, setting, drawing,
   posting. The fix treats a whole condition of `!thing` as a presence check,
   except for affirmative permission names — `!canSubmit` really is the latch
   where `canSubmit` folds in `saveState !== 'sending'`.

The first attempt at (2) skipped every `!thing` and reported
`compose-announcement.tsx` as unguarded, which is genuinely guarded that way —
a false positive caught by running the checker over the tree before keeping the
change. Proven both ways: at `HEAD~1` the fixed checker reports
`handleDelist`; on the current tree it is clean, 138 suites green, `tsc` 0.

This is `learning_four_ways_a_new_gate_is_wrong` failure mode "a name-keyed rule
matching homonyms", recurring — and the reason to distrust a checker that
reports nothing about a class you have just found an instance of by reading.

**The 2026-09-17 instance — ✅ fixed by the checker sweep; the text below
is the original finding, kept for the record.** Re-verified 2026-09-18:
`handleDecline` opens with `if (!deal || declining) return;` and sets
`setDeclining(true)`, its `AnimatedPressable` carries `disabled={declining}`,
and `npm run check:double-submit` passes clean. The bullet had stayed open in
this list after the fix landed.
- `app/purchase/deal/[dealId].tsx:120` `handleDecline` has no in-flight guard and
  its control no `disabled`, while its sibling `handleConfirm` uses `setConfirming`.
  The server's decline is `UPDATE … WHERE status = ANY(_DECLINABLE_STATUSES)`
  (`server/app/agents/purchase_router.py:818`), so the second tap updates 0 rows
  and returns 404 — the member sees "Failed to dismiss" on a deal that was
  dismissed. Discarded as guarded while checking this: `favorites.onUnsave`
  (optimistic removal takes the row away), `users/[userId].handleBlockToggle`
  (closes the menu, then confirms through an Alert), `OfferAmountSheet.handleSubmit`
  (`busy` guard), the three `AppearanceSection` setters (idempotent settings writes).

**K — the webhook claim: ✅ FIXED `8439f97`, completed and DEPLOYED 2026-09-18.**

Two sentences in this section were stale and are corrected here rather than
above: "nothing ever deletes it — there is no `DELETE FROM
processed_webhook_events` anywhere in the repo" stopped being true on 2026-09-17
(`_release_webhook_claim`, `8439f97`), and "two server fixes not deployed" in the
register was stale too — a repo-vs-EC2 hash diff of all 263 files under
`server/{app,workers}` on 2026-09-18 found them identical.

The original finding: `billing_router.py` claims the webhook id BEFORE any work
with `INSERT … ON CONFLICT DO NOTHING RETURNING`, so a failure after the claim
made the provider's redelivery short-circuit and the work never happen. For
RevenueCat that left a member **charged, recorded in the revenue ledger, and on
`free`** — `get_user_plan` reads `subscriptions`, and nothing reconciles it from
`subscription_events`.

**`8439f97` fixed two of five paths, and the miss is the interesting part.** It
released the claim on the `subscriptions` upsert (RevenueCat) and around the
handler dispatch (Stripe), and `docs/API.md` wrote the rule down as "**any**
failure after the claim must release it". Three failures after the claim did not:

1. **The `subscription_events` insert** — the FIRST write, whose own comment says
   *"500 so RevenueCat retries — losing a revenue event loses a payout"*. The
   retry could not run: the claim was held, so the redelivery answered
   `{"ok": true, "duplicate": true}`. The payout row was lost for good **and**
   `subscriptions`, written after it, never happened either. Strictly worse than
   the case that was fixed, on the write the file calls the source of truth.
2. **`_rc_resolve_user_id`** — queries the database between the claim and the
   first write, caught by nothing.
3. **`event["data"]["object"]` (Stripe)** — sat one line above the `try`, so a
   signed event with an unexpected shape raised KeyError with the claim held.

Found beside them: the Stripe handler answered **200 `{"received": true}`** when
there was no database pool, with the claim taken and nothing written. 200 is
Stripe's signal to stop retrying, so a paid sponsorship, ticket or plan change
arriving during an outage was acknowledged and dropped — the same endpoint class
as the seven fixed under "No database means no success". It now 503s, as the
RevenueCat handler already did.

**Measured on prod 2026-09-18, and the path was not theoretical: 5 of the 10
rows in `processed_webhook_events` hold a claim with NO ledger row.** The ledger
insert is unconditional and has been in that handler since 2026-07-20, so each of
those five is the unretryable path firing — claim taken, nothing written,
redelivery swallowed. All five are `revenuecat.TEST` events from 2026-08-30
(11:28–12:26), the day `099ef92` was being worked on; the two at 12:34 have
ledger rows. **No member was stranded:** 0 paid ledger rows lack a `subscriptions`
row, so the 2026-09-17 finding in `docs/API.md` still holds. The five stale
claims are left in place — those event ids will never be redelivered.

**The fix is one chokepoint per handler, not five release calls.** Both handlers
now wrap everything after the claim in `try: … except Exception: await
_release_webhook_claim(...); raise`. Five call sites would leave the next write
added to either handler uncovered — which is exactly how these three were
missed. Five tests: the three gaps (red before, green after), plus one asserting
a SUCCESSFUL event **keeps** its claim, because a chokepoint that over-releases
would silently undo the dedup and nothing would look broken.

✅ **`p2p_listing_router.create_listing` — fixed 2026-09-17.** It created an
`items` row (with `for_sale = TRUE`) and then the `marketplace_listings` row on
a bare `pool.acquire()`, so a failure on the second write left a phantom in the
member's collection badged "Listed" with no listing behind it. Both writes now
share one `conn.transaction()` — the pattern
`account_router._do_account_delete` already uses — and the 404/409 raises roll
back with it, which is correct: nothing was meant to exist yet. Audited: the only
awaits inside the transaction are `conn.*` (no HTTP call holds it open) and both
`spawn_bg` hooks stay outside. Two tests in
`server/tests/test_p2p_listing_router.py` assert the ORDER (the transaction opens
before BOTH inserts — presence alone would pass a transaction that wraps
nothing) and that the supply hook stays outside; the same assertions were run
locally against the source and go red when the transaction line is removed.
✅ **DEPLOYED** — verified 2026-09-19, not assumed: `p2p_listing_router.py`
hashes identically in the repo and at `/opt/collectors/server/`, and the live
file contains `conn.transaction()` three times. This line said **NOT DEPLOYED**
for a day after it had shipped; see the note at the top of class K about the
register drifting toward a list of things that *were* true.
Also open from K: ✅ `create-event.tsx` save-as-template — **fixed 2026-09-17.** The template save
was wrapped in its own try/catch that logged and continued, so a member who
ticked "save as template" navigated back believing they had one. The event is
deliberately NOT rolled back — it is what they came to do and it succeeded — but
the toast now says the template was not saved. The copy does not offer to "save
it as a template later": this screen is the only caller of `createEventTemplate`
in the app, so there is no later, and promising one would be the second bug.

**A gap worth gating — ✅ WRITTEN 2026-09-18: `npm run check:half-done-silence`.**

`check-silent-failures --strict` passed that code both before and after the fix,
because the catch *logged*. Rule B asks "was it logged?" — the same wrong
question that let the 74 empty-on-failure sites through until rule F was
written. Logging is what the DEVELOPER finds out. The new rule asks what the
MEMBER finds out.

**The rule:** a catch whose body does NOTHING BUT LOG, inside a function that
already awaited a WRITE before the try. "Nothing but log" is the discriminator,
and it is exactly what separates the two versions of the worked instance:

    catch (tplErr) { logger.error(…); }                          ← reported
    catch (tplErr) { templateSaved = false; logger.error(…); }    ← not

The second is the fix — the flag is read after the try and drives a toast that
names what did not happen. Any statement other than a log means something
downstream can still tell, so rule B keeps it.

**It was wrong twice before it was right, and both are worth knowing:**

1. **It reported nothing on the very instance it was written for.** The walk out
   to the enclosing function accepted any head ending in `)`, so
   `if (saveAsTemplate && templateName.trim())` was read as a function opener:
   the walk stopped at the `if` and never saw the `createEvent` above it. Found
   by running it against `b40e256~1` — the pre-fix file — rather than trusting
   that a green checker meant a clean tree.
2. **"A prior await" is not "the primary write succeeded".** The first version
   reported 19 sites; reading them showed three shapes that were not the class
   at all — a prior READ that degrades on purpose (`item/[id].tsx`), ENRICHMENT
   before the write (`add-manual.tsx` matches the catalog, *then* inserts), and
   a read whose catch already carried an `empty-ok:` reason. Requiring a prior
   **write** took 19 → 4. A rule reporting 19 where 4 are real is the "wrong
   about two thirds of what it reported" shape from class S.

Proven on the fixture pair: the pre-fix `create-event.tsx` is caught, the fixed
one is clean.

**What the 4 were.** One real defect, three reasons written:

✅ **A failed RSVP was invisible — fixed.** RSVP is a primary action on the
Events tab, and a failure reached the member as nothing at all:
`useOptimisticMutation` catches its own error and does **not** rethrow, so
`handleAttend`'s `catch` never ran; neither screen reads the hook's `error`; and
`onRollback` logged with **`logger.warn`, which is stripped in release builds**
— so in production there was not even a log. The card flipped to "attending" and
flipped back when the reload landed, which a member reads as a mis-tap. Both
variants (list and detail) now toast and log with `logger.error`, plus the
handler's own last-resort catch. Four tests, mutation-proven three ways
(drop the toast → 2 red; revert `error` to `warn` → 3 red; clean → green).

`common.error` rather than a new string: a specific message needs writing in
seven locales, and `docs/I18N_BACKLOG.md` is explicit that a new string must
reuse the locale's existing vocabulary rather than be a fresh translation of the
English. Worth upgrading to "Your RSVP didn't save" when that backlog is worked.

Reasons written, not fixes:
* `events.tsx` calendar add — the member asked to attend, not for a calendar
  entry; it is offered silently, and `calendar.ts` writes its mapping only on
  success, so nothing later claims an event is "on your calendar" that is not.
* `sell/new.tsx` per-photo upload — the member IS told: the loop counts
  successes and the toast names how many of how many uploaded. The rule reports
  it because the counting happens outside the catch; the reason is written
  rather than the rule widened to guess at it.
* `DevForcePlanSection` — `__DEV__`-only plan override, no member reaches it.

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

## S — the server answered `ok` and wrote nothing (2026-09-17/18)

The mirror of class P. P was "a failed READ answered 200 with an empty payload";
this is **a failed WRITE answering 200 with `{"ok": true}`**. The client cannot
question either one, and a write is worse: every one of these sits behind an
OPTIMISTIC screen, so the app shows the member what they asked for and the
truth only reappears on the next fetch — minutes later, with nothing anywhere
saying why.

**Enumerated mechanically** (`ast`, route handlers only): 34 handlers `await
conn.execute("UPDATE …"/"DELETE …")` as a bare statement, discarding asyncpg's
status string. A discarded row count is not by itself the finding — several are
fine because a preceding SELECT already proved the row exists and is the
caller's (`chat_router.delete_message`). The finding is **an `ok` that no write
stands behind**, and these are the ones triaged so far:

| site | what it claimed |
|---|---|
| `items_router.update_item_attributes` | `if pool is None: return {"ok": True}` — and the UPDATE's row count discarded, so patching an id that is not yours answered `ok`. The app closes edit mode and toasts success on `ok` |
| `items_router.update_item_purchase` | same no-pool claim, on the **cost basis** (the row count here was already checked with `RETURNING`) |
| `alerts_feature_router.mark_trigger_read` | THREE exits all answering `{"ok": true}`: no database, a swallowed `PostgresError`, and a row count nobody read |
| `social_router.block_user` / `unblock_user` | `success: true, "User blocked (offline mode)"` with no pool. Blocking is the one action that must never be optimistic |
| `social_router.get_blocked` | `blocked: []` with no pool — "you have blocked nobody", on the screen where a member checks a safety decision |

**Three bugs stacked on one action.** Mark-as-read was the worst case, and no
single fix would have been visible:

1. the server lied on failure (above);
2. `useAlertsFeed` hardcoded `isRead: false` while the server had been
   returning `read` all along — so even a SUCCESSFUL write was invisible, the
   alert came back as new, and `unreadOnly` could never filter anything;
3. the feed is cached `TTL_MEDIUM` and nothing cleared it after the write.

And the optimistic flip had no rollback, so (1) looked like success until the
cache expired. `AlertFeedItem.read` is now REQUIRED so a future mapping cannot
leave it out, `markAsRead`/`markAllAsRead` roll back per row, and a derived
alert (`derived-drop-<itemId>`, no trigger-history row, not a uuid — the
endpoint answered 400 for every one) is never posted at all. Seven tests, four
mutations.

### The one that had been dead for five months

`_send_announcement_dms` — "DM every attendee when the host posts an
announcement" — found or created a thread in **`dm_threads`** and then inserted
the message into `chat_messages_v1`, whose `thread_id` FK was repointed to
`chat_threads_v1` on **2026-04-30** ("every sendMessage and markThreadRead 409'd
with FK violation"). Read back on production: `dm_threads` holds **0 rows**. So
every announcement created a fresh legacy row and every message insert violated
the FK. The per-attendee `except` logged a warning and moved on; the summary
line said `sent=0` at INFO; the host was told nothing.

It now upserts `chat_threads_v1` on `ux_chat_threads_v1_dm_pair` (pair
canonicalised least/greatest), inserts both `chat_thread_members_v1` rows, and
sends through `rpc_send_message_v1` — **the same writer `chat_router.send_message`
uses**, so a schema change cannot fix chat and leave announcements behind again,
which is this bug's whole shape. Plus three things the old code could not do:
it honours `user_blocks` through `app/lib/blocks.py`, it respects a `denied` DM
request (the successor to the `dm_threads.status='declined'` check it used to
make), and it skips attendees whose account no longer exists — 3 of production's
distinct attendee ids, and `event_attendees` has no FK to `auth.users` while
`chat_threads_v1.dm_user_a/b` do, so each would otherwise count as a failure.

**A total failure now logs at ERROR.** `sent=0, failed=N` reported at INFO is
how this survived five months of log-reading.

Verified by running the new statements against production inside a transaction
that ROLLED BACK: thread upsert → 2 members → message → bump, then 0 messages
after rollback. Eight tests, seven mutations.

**`social_router.block_user` had the same bug** — it declined pending DMs in
`dm_threads` too, so blocking never declined anything. Now
`chat_dm_requests_v1` (`status='denied'`, `decided_at`, `decided_by`), both
directions, and both statements in ONE transaction: a block that landed while
the decline failed used to leave the member blocked AND told "Failed to block
user". Same fix as `20260917c` for the RPC the app actually calls.

### Eight tests asserted the lie

This class had TEST COVERAGE — of the bug. `test_block_user_offline_mode`
("Block succeeds in offline mode"), `test_mark_trigger_read_offline`,
`test_update_attributes_offline_noop`, `test_list_blocked_offline_mode`,
`test_unblock_user_offline_mode`, `test_overview_no_db_falls_back`,
`test_items_no_db` and `test_timeseries_no_db_no_signals_returns_empty`. Each
one named the behaviour it pinned and asserted it, so the class was not just
unnoticed — it was **protected**. All eight now assert the honest answer and say
in the docstring what they used to require and why that was wrong. (Three more
came from the class-Q/P work earlier in the session: one required `str(e)` in a
PUBLIC endpoint's response body, two required PIL's "cannot identify image
file <_io.BytesIO object at 0x…>" as the message a member reads.)

Two of them were hiding a second defect behind the first:
`test_block_same_user_twice_offline` claimed to prove idempotency but ran with
NO pool, so it never reached `ON CONFLICT (blocker_id, blocked_id) DO NOTHING`
— the actual guarantee. It runs against a mock pool now.
`test_a_quarantined_event_is_not_found_by_link` passed only when the caller's
dev identity happened not to match the row it had just created, because
`_hidden_from_detail` deliberately exempts the CREATOR; it now sets
`created_by = None` (556 quarantined rows on prod, 0 with a creator) and has a
mirror test for the creator's own view, so neither half can drift alone.

### The two money handlers, and what the row count was hiding

`p2p_offers_router` was the first of the 34 to be read properly, and the
discarded row count turned out to be the *symptom*. Both handlers read a row,
decided in Python, and wrote — **with no transaction and no row lock**:

**`respond_to_offer`.** `accept` writes `p2p_offers` and THEN
`marketplace_listings`; a failure between them left an accepted offer whose
listing was never reserved, and `withdraw` had the mirror — the offer cancelled
while the listing stayed reserved to it, invisible to the seller and unreachable
by any other buyer's accept. Concurrently, two responses both read `pending` and
both wrote: a `decline` racing an `accept` left the listing reserved for a
declined offer, and `counter_count` could pass `MAX_COUNTERS` because the cap
was checked against a stale read. Now one transaction with `FOR UPDATE OF o` —
**not** a bare `FOR UPDATE`, which Postgres rejects on this query ("cannot be
applied to the nullable side of an outer join"; reproduced on prod before the
comment claiming it was written). The notification stays outside, so the row
lock is not held across a notification write.

**`confirm_exchange` — the completion path, and the worse one.** "Both sides
confirmed" was decided by reading the row back after an unlocked write, so two
confirms in flight each saw only their own: `both` was false for both callers,
**completion never fired**, and the trade sat at `accepted` with two
confirmation timestamps and no way forward, because `ALREADY_CONFIRMED` blocks
the retry that would fix it. No settlement, no sold comp, no DAC7 accrual. The
mirror interleaving ran the completion body TWICE, and `_dac7_accrue` reports
consideration **for tax**.

Now: `FOR UPDATE` on the offer, the confirm write, the re-read, the completion
writes and `_settle_completed_trade` (which takes the same `conn`) all inside
one transaction, with a `completed_now` flag. The four external hooks
(`_stale_supply_hook`, `_sold_comp_hook`, `_ground_truth_hook`, `_dac7_accrue`)
run **after the commit and only for the caller that completed the trade** —
each opens its OWN pool connection, and `_sold_comp_hook` SELECTs
`marketplace_listings`, so inside the transaction it would read the pre-commit
status and skip.

13 tests, and the mutations are the point: **two of them passed against a
broken build until the tests were strengthened.** Moving `_settle_completed_trade`
past the commit stayed green because the test only counted the call, and
indenting the hooks INTO the transaction stayed green because the hook fakes
recorded into a different list from the `COMMIT`. A fake has to observe ORDER in
one stream, or "inside the transaction" is not what is being tested.

### The other two money handlers

**`marketplace_listing_router.record_sale`** INSERTs a `marketplace_sales` row
carrying `net_proceeds` and THEN marks the listing sold. A failure between them
left a banked sale for a listing still advertised as available — and the
"already recorded" guard reads `status = 'sold'`, so the retry did not catch it
and wrote a **second** sale row. Two taps did the same thing with no failure
involved. Now one transaction, guard row `FOR UPDATE`.

**`purchase_router.confirm_deal`** was half right already, and the half that was
right is worth copying: the deal's own write is a compare-and-set
(`WHERE status = ANY(...)` + `if result == "UPDATE 0": 409`). But the mandate
counters ran afterwards as separate statements, so a failure between them marked
the deal **purchased** while `spent_total` never moved — and `max_total_budget`
is checked against `spent_total`, so the agent could keep spending past the cap
the member set. The counter's row count is now read too (a `mandate_id` that is
not the member's matched nothing and the spend vanished silently), and a miss
rolls the whole confirm back with 409 `MANDATE_MISMATCH` rather than leaving the
two halves disagreeing.

Its tests needed fixing before they could pass, and the reason generalises: on a
bare `AsyncMock`, `conn.transaction()` returns a **coroutine**, and `async with`
on a coroutine raises *"'coroutine' object does not support the asynchronous
context manager protocol"* — which arrives as a 500 and reads like a router bug.
Three of them also stubbed `conn.execute` as returning `None`; asyncpg always
returns a status string, so those stubs described a database that does not
exist. `_attach_transaction()` in `server/tests/test_purchase_router.py` is the
one place to fix it.

### All 34 read — and 22 of them were fine for a reason worth writing down

The enumeration is closed. The 34 are SITES, not handlers: `respond_to_offer`
alone holds 6 and `catalog_learning_router` 7. Twelve of the 34 belong to the
five handlers fixed above (`respond_to_offer` 6, `confirm_exchange` 2,
`confirm_deal` 2, `record_sale` 1, `block_user` 1). The other **22 discard their
row count correctly**, and the reasons fall into four shapes — which is the
useful output, because it is what a gate would have to understand:

| shape | sites | why 0 rows cannot be a lie |
|---|---|---|
| **Existence and ownership proven by a preceding SELECT** | `chat_router.delete_message`, `item_images_router.delete_item_image`, `sponsor_company_router.delete_company`, `p2p_offers_router.set_tracking`, `catalog_learning_router` ×7 (ops key), `p2p_listing_router.report_listing` | the row was read in the same handler under the same `WHERE`. A 0 here is a concurrent delete, and the answer ("it is gone") is still true |
| **Idempotent by intent** | `favorites_router.remove_favorite` ×2, `events_core.unfollow_category`, `notification_router.unregister_push_token` | the member asked for an END STATE, and it holds whether or not a row moved. Contrast `block_user`, where the end state was NOT reached — that one was a real finding |
| **The row is guaranteed by the statement above it** | `gamification_router.award_xp` — an upsert `RETURNING` the row, then the level write | |
| **Already correct** | `item_images_router.reorder_item_images`, `p2p_listing_router.action_listing_reports` and `withdraw_my_catalogue_photos` (already transactional), `p2p_offers_router.set_payment_handle` (one statement per branch, and it answers with a RE-READ rather than a claim) | |

Count: 12 + 4 + 1 + 4 sites, plus `create_event_checkout` below = 22.
`marketplace_listing_router.delete_listing` is **not** one of the 34 — it already
assigns and reads its status string, which is why the scan never saw it. Nor is
`respond_to_offer`'s conditional reservation clear
(`WHERE reserved_offer_id = $2`, where 0 rows is the normal case): it is one of
that handler's six, counted as fixed.

`sponsor_company_router.create_event_checkout`'s bare `DELETE FROM events WHERE
id = $1` looks alarming and is not: it is the rollback of a draft event the same
handler created two statements earlier, so the id is its own.

### The gate, and the four findings it added (`check:unwritten-ok`)

`server/scripts/check_unwritten_ok.py`, in `verify:prebuild`. Not "discarded row
count" — that would have produced 34 findings of which 22 are correct, and a
checker wrong about two thirds of what it reports stops being read (the
measurement that killed the class N gate). The narrow rule instead:

> inside a **write** route (`post`/`patch`/`put`/`delete` — GETs belong to
> `check_empty_on_failure.py`), a `return` of a payload claiming success
> (`ok`/`success`/`succeeded` truthy, or `status: "ok"`), lexically inside a
> branch testing **database availability**, whose body **does no work at all**.

It found **four more, in files the manual pass never opened** — because these
are not row-count sites, they are handlers that never reach a query:

| handler | what the member was told |
|---|---|
| `feedback_router.submit_feedback` | "Feedback recorded (offline mode)" — the screen says *Feedback submitted*; the correction never reached the model that asked for it |
| `feedback_router.submit_verified_sale` | "Verified sale recorded (offline mode)" — **the one price in this app a human has confirmed with money**, feeding `verified_sales` and model calibration, unreconstructable once the screen moves on |
| `feedback_router.submit_correction` | "Correction recorded (offline mode)" |
| `user_settings_router.update_user_settings` | `success: true` **with the submitted values echoed back as if stored** — Settings showed the new currency, region and locale, and the next load showed the old ones. Currency is every money figure in the app |

All four now raise 503 with a sentence a member can act on, and log at ERROR
with what was discarded.

**Seventeen more tests asserted these** — three whole classes named for it:
`TestFeedbackSubmitOffline` (6), `TestCorrectionSubmitOffline` (5),
`TestPutSettingsOffline` (2), plus `TestVerifiedSaleEndpoint` (2) and two
"response shape" tests that pinned the shape of the offline SUCCESS body. The
six submit tests differed only in the `feedback_type` they sent while the
message was a constant, so they were six copies of one assertion; they are two
now. The shape tests were repointed at the FAILURE body, which is the more
load-bearing contract (`src/lib/userErrorMessage.ts` renders `detail.message`).

**Seven mutations.** The five original findings restored one at a time (the gate
caught 3 of 5 on its first version — `touches_database()` walked the `return`
statement, so `BlockResponse(success=True, …)` counted as "maybe it does the
work elsewhere" and the two `social_router` lies, the whole reason for the gate,
were skipped); the `notification_feedback_router` payload that answers
`{"ok": True, "stored": False}`, which is a report and not a claim (the gate
accepts an explicit falsey `stored`/`saved`/`persisted`); and — the one that
matters for trust — **removing the work from `delete_alert`'s in-memory
fallback**, to prove that branch is exempt because it PERFORMS the delete, not
because the gate never looked.

Left alone deliberately: the settings CALL SITES
(`AppearanceSection.handleRegionChange` / `handleSkillChange`) swallow the new
503, and that is consistent — they are local-first by design, the local store is
what the screen renders, and it persists. What the 503 buys there is a real
error in the log instead of a silent divergence between the device and the
server's copy of the member's currency.

### `marketplace_listings.reports_count` — DROPPED 2026-09-18

`report_listing` incremented it, carefully and only on a genuinely new report,
with a comment explaining that unconditional increments "would poison moderation
triage". **Nothing read the column** — not `server/app`, not the app, not the
ops queue. It appeared only in the schema dumps.

Reading it properly turned "unused" into "unusable": **nothing ever decremented
it.** So it counted reports EVER FILED while every consumer that matters counts
reports still OPEN — and both of those consumers already derive the honest
number from `listing_reports`, the table the DSA obligations attach to:

* the ops alert: `count(*) FROM listing_reports WHERE status = 'open'`;
* `GET /ops/listing-reports`: reads `listing_reports` directly, oldest first.

A denormalised copy that disagrees with its source **by construction** is worse
than no copy: the next person to reach for it reads "3" on a listing whose
reports were all resolved. Dropped rather than fixed, because fixing it means
maintaining a counter that duplicates a `count(*)` over an indexed table.

Migration `20260918b`, applied to production. The report data is untouched —
`listing_reports` is the artifact; only the tally beside it is gone. **The
schema lock was regenerated and DIFFED** (one line: `column_meta.
marketplace_listings.reports_count`, nothing else blessed) before the restart,
because `preflight_schema_lock` is a blocking `ExecStartPre` and a stale lock
means the bake cannot come back up.


## T — the server sends it and the app never reads it (2026-09-18)

`AlertFeedItem.read` (class S) was an instance: the server had always returned
the flag, the mapping dropped it, and the hook hardcoded `isRead: false`, so
marking an alert read was invisible. **A write whose result the reader ignores
cannot be told from a write that failed** — so the class is worth enumerating.

**The probe** (`scratchpad/probe_dropped_fields.mjs`): every field declared in a
type inside `src/api/*.ts`, then grep for that identifier across `src/` and
`app/` excluding `src/api`. Zero hits outside = the server sends it and nobody
looks. **74 of 461 distinct fields.**

Most of the 74 are not defects, and the taxonomy matters more than the count:

- **request parameters** (`unread_only`, `notify_before_hours`, `source_hint`) —
  the app SENDS them, so "nothing reads them" is expected;
- **deliberately removed UI**, with the removal written down at the site: the
  seven `/settings/alert-preferences` fields went when the AlertSettings panel
  did, because it "hit GET/PATCH on every Settings open to populate a UI whose
  values nothing consumed" (`src/screens/Settings.tsx`);
- **flag-off features** — the gamification block (`weekly_xp`, `xp_to_next`,
  `longest_streak`, …) behind `GAMIFICATION_UI_ENABLED = false`;
- **redundant siblings** — `seller_total_grades` / `seller_positive_grades` sit
  next to `seller_positive_pct`, which IS rendered.

### The three that are real, and all three are decisions

**1. Realised profit is computed twice and shown nowhere — and the missing piece
is not a screen.** `getRealisedPL()` → `GET /portfolio/realised-pl` (per-sale
fees, cost basis, `total_profit`, `total_net_proceeds`,
`sales_without_cost_basis`) has **zero callers**. Separately, `/portfolio/items`
returns per-item `realized_pl`, which `portfolioAnalyticsStore` maps to
`realizedPL` — and `app/analytics.tsx` renders only `unrealizedPL`, which the
store's own comment says is **model drift, not profit**, for every item without
a purchase price (~93% of production).

**Measured on production before building anything (2026-09-18), which changed
the answer:**

| | |
|---|---|
| `marketplace_sales` rows | **0** — unchanged since the 2026-08-31 measurement in `docs/COLLECTOR_DEMAND.md` §5 |
| listings at `status='sold'` | 3 |
| completed P2P offers | 1 |
| items with `purchase_price_eur` | 7 of 17 |
| items with `acquisition_fees_eur` | **0** |

`marketplace_sales` has exactly one writer — `POST /marketplace/listings/sales/
{listing_id}/record` — and its client wrapper `recordMarketplaceSale()` **has no
caller anywhere in the app**. The P2P completion path does not write one either:
`_settle_completed_trade` retires the seller's item, mints the buyer's, clears
the reservation and declines rival offers, and records no SALE.

And a surface already exists: `app/sell/dashboard.tsx` has a **Sales tab** with a
revenue summary (gross, fees, net, count) and an empty state. It has always read
an empty table.

✅ **The writer landed 2026-09-18.** `_record_p2p_sale`, inside the completion
transaction beside `_settle_completed_trade`, so a trade cannot complete without
recording the seller's sale. Option 3 of the three below, minus the form (which
is the follow-up): the row is written with **postage NULL**, and every reader
now treats that as unknown rather than zero.

| written | why it is honest |
|---|---|
| `platform_fee` / `payment_processing_fee` = 0 | Sparrow charges nothing on the marketplace and never touches funds (P2P spec §5b). The 5% in `terms.tsx:159` is EVENT TICKETS |
| `shipping_cost_actual` = **NULL, explicitly** | the column DEFAULTS to 0, and defaulting would state "postage cost nothing" — a number we do not have |
| `net_proceeds` = the agreed amount | exactly `sale_price − 0 − 0 − (unknown postage)` given what is known: a net BEFORE postage, and `shipping_known: false` is what says so |
| `buyer_name` = NULL | the trade already links the parties; copying the buyer's name into the seller's ledger is a disclosure nobody asked for. `buyer_marketplace_id = 'sparrow'` records WHERE, not WHO |
| `WHERE NOT EXISTS` | there is no unique key on `listing_id` (checked on prod), so a retry would otherwise double a member's realised proceeds |

§5b lists "record a payment **claim the seller asserts**" under *We may*, and
"issue a receipt in Sparrow's name" under *We may not*. This is the first.

**The read side had to change with it**, or the first row would have shipped the
sell-side version of §5's own error: `summarise_realised_sales` treated
`shipping_cost_actual` as `or 0`, i.e. "postage cost nothing". Now
`shipping_known` per row, `profit` null without it, `sales_without_shipping`
counted beside `sales_without_cost_basis`, and `fees.shipping` is `None` rather
than `0` when unrecorded. `app/sell/dashboard.tsx` labels its total **"Net
before postage"** and says on how many sales it is unknown.

### Two casts found while wiring it, one of them costing money

Writing the first row into a table that had always been empty exposed what the
emptiness was hiding — `src/data/providers/dealsProvider.ts` **cast** two
snake_case server payloads to camelCase types instead of mapping them:

1. **`listMarketplaceSales`** — every `salePrice` and `netProceeds` was
   `undefined` at runtime, and the Sales tab's Revenue Summary SUMS them, so it
   would have rendered **NaN** for gross and net the moment a sale existed. The
   new writer was about to create that row.
2. **`getMarketplaceFeeSchedules`** — `s.marketplaceId` was `undefined`, so
   `useListForSale.calculateFee`'s `find()` never matched and the fee estimate
   always fell back to the client's own `defaultFeePct` with `estimated: true`.
   That honesty flag was added on 2026-09-17 by class sweep D, which spotted the
   symptom and not the cause. Against the real schedules on prod: the app quoted
   **5% on Sparrow's own marketplace, which takes 0%**, and under-quoted eBay
   (12.9% vs 12.9 + 2.9% + €0.30) and StockX (9.5% vs 9.5 + 3.0%).

**A cast is not a mapping, and TypeScript cannot tell you** — `unwrap<T>()`
asserts the shape rather than checking it, so both compiled cleanly and both were
wrong. Worth a gate: a provider that returns a camelCase type from a payload
whose keys are snake_case.

**So the gap WAS the WRITER, not the screen** — building the realised-P/L view
today would add a second window onto a table nothing fills. Fixing that is a
money-semantics decision, which is why it is written down rather than guessed:

1. **P2P completion writes the sale.** Everything is known at
   `confirm_exchange` — amount, currency, listing, buyer, seller. But Sparrow
   charges no fee and never learns the seller's postage, so `net_proceeds` would
   equal the sale price, which **overstates what they actually made** — the
   $900-not-$956.25 error of `COLLECTOR_DEMAND.md` §5, moved to the sell side.
2. **Wire `recordMarketplaceSale`** — a "record a sale" form covering sales made
   anywhere, eBay included. The numbers are true because the member enters them;
   the cost is entry friction, which §5 names as exactly why people give up.
3. **Both, in that order**: completion PREFILLS the form (amount, date, item)
   and the member confirms or corrects the postage. The prefill is the answer to
   the friction objection, and nothing is invented — an unconfirmed postage
   stays null and its row carries no profit, the same way
   `cost_basis_known: false` already works on the read side.

**2. The demand differentiator is fetched and not shown.** The listing detail
renders `watchers` ("3 other members watching this item") and never
`watchers_above_price` — which the spec calls *"the number that actually
predicts a sale"*, and its own example line is
`4 members are watching this · highest target €40`. `top_target` is unread too.
**Not obviously a bug:** `/p2p/demand/{item_id}` is ownership-enforced precisely
because "demand is competitive information", and the listing detail is readable
by any member, so showing a buyer how many rivals would be alerted at this price
is a product call, not an oversight to fix quietly.

**3. A member cannot see when their subscription ends.** ✅ **FIXED 2026-09-18**,
and it was not a product decision after all — it was three pieces of one feature
that never met:

* `GET /billing/status` has always returned `status`, `current_period_end` and
  `cancel_at_period_end`;
* `subscription.past_due` ("Payment past due. Update your payment method…") and
  `subscription.downgrade_pending` were already written and translated into
  **all seven locales**;
* `useBillingLimits` kept `plan` and `limits` and dropped the other three at the
  setter, and **nothing in the app rendered either string**.

So the copy had been reviewed, translated and shipped, and no member could ever
see it. The fix is wiring plus one new key pair (`renews_on` / `access_until`):
the hook keeps what it fetches, and the screen renders one line under the plan
cards. The branching lives in `src/lib/billingStatusLine.ts` rather than in the
screen, because the first version of its test copied the decision table — which
is exactly how a screen and its test drift apart while both stay green.

Four rules it encodes, each with a test and a mutation:
1. **A payment problem outranks everything** — it can END the plan.
2. **A cancelling plan says how long access lasts, never "renews on".**
3. **A null `current_period_end` falls back to the dateless sentence.** The
   column is nullable, and "Invalid Date" is not a thing to show someone paying.
4. **An active plan with no date says NOTHING** rather than rendering an empty
   line, and a FAILED fetch leaves all three `null` — unknown, not "nothing to
   say" (rule F).

Not shown under a dev `FORCE_PLAN` override or in beta-unlock mode: neither has
a real subscription behind it, so any date there would be invented.

### What this class teaches about the probe

A grep for the identifier cannot tell a dropped field from a request parameter,
and it cannot see a field consumed under a different name (`total_profit` →
`totalProfit`). So this enumeration is a **starting list, not a finding list** —
which is the same shape as class N: the measurement is the deliverable, and the
gate is not worth writing until something narrows it. The narrowing that would
work here: only fields on a type that a `get<…>` RESPONSE uses, and only where
the mapping function for that type exists and omits the key.

## U — a provider casts a snake_case payload to a camelCase type (2026-09-18)

Found by writing the first `marketplace_sales` row into a table that had always
been empty: the emptiness was hiding a cast, and looking for its siblings found
three more in the same file.

`src/data/providers/dealsProvider.ts` had four functions shaped like

```ts
return unwrap<MarketplaceSale>(await collectorsApi.get('/marketplace/listings/sales'), 'sales');
```

`unwrap<T>()` **asserts** the shape; it does not check it. The server answers
snake_case (`listing_title`, `marketplace_id`, `base_fee_pct`) and the types are
camelCase, so every mapped field was `undefined` at runtime while `tsc` stayed
silent. **TypeScript cannot catch this class** — that is the whole point of it.

⚠️ **CORRECTED, same day.** I first wrote that two of these were "live right
now". They are not: **all four sit behind `SELLING_ENABLED = false`** —
`app/sell/dashboard.tsx` returns `<SellingUnavailable/>`, and the only control
that opens the List-for-sale modal (`ItemQuickActionsRow`) is inside
`{!SELLING_ENABLED ? null : …}`. Caught by installing the build and deep-linking
to `sell/dashboard`, which answered **"Selling is coming soon"**. The claim came
from reading the render path and not the flag above it; the device disproved it
in one screen. The live P2P marketplace (7 listings) goes through
`sell/new` → `collectorsApi.createListing` and touches none of these four.

They are still four real defects — they would ship the day that flag flips,
which its own comment says is "once a real eBay account can be connected end to
end" — but **member impact today is zero**.

| cast | what it does, when selling is switched on |
|---|---|
| `listMarketplaceListings` | `listing.listingTitle` undefined → blank row titles, a blank accessibility label, and a `Remove "" from marketplace?` confirm. `marketplaceId` undefined → `MARKETPLACE_CONFIG[undefined] ?? MARKETPLACE_CONFIG.collectai` badges **every** listing as Sparrow P2P whatever marketplace it is on |
| `listMarketplaceAccounts` | same on the Accounts tab: every connected account mislabelled, and "Disconnect Account?" naming the wrong one |
| `getMarketplaceFeeSchedules` | `find(s => s.marketplaceId === mpId)` never matches, so the fee estimate always falls back to the client's `defaultFeePct` with `estimated: true` — quoting **5% on Sparrow's own marketplace, which takes 0%**, and under-quoting eBay (12.9% vs 12.9 + 2.9% + €0.30) and StockX (9.5% vs 9.5 + 3.0%) |
| `listMarketplaceSales` | `salePrice`/`netProceeds` undefined and the Revenue Summary SUMS them → **NaN**. Doubly hidden: behind the flag AND behind an empty table until completion started recording sales |

**Why it survived.** Three layers, and the first is the one that matters:
the whole surface is **flagged off**, so nobody has looked at it since the flag
went up. Under that, `price`, `currency`, `status` and `quantity` are spelled
identically on both sides, so the Listings tab would look broadly right — prices
and status chips correct, titles missing. And the screen sweep walked
`sell/dashboard` and reported `ok`, which is honest: it saw the coming-soon
screen.

**The general lesson, swept 2026-09-18:** four of the 79 walked routes can only
render a placeholder (`sell/dashboard`, `sell/ebay-defaults`, `franchise/[id]`,
`chat-demo`), plus seven surfaces gated inside live screens. The walk reports
them `ok` forever and is right to. **Flipping a flag therefore ships code no
round has ever seen** — sweep it first. Full list: `docs/ANDROID_LAUNCH.md`,
"What the walk is STRUCTURALLY blind to".

**And the lesson for me, not for the code: check the FLAG before calling
something live.** I read the render path, found the bug, and described a member seeing it
— without checking the four lines above that render path. One install and one
deep link settled it.

**And a gate had already seen the symptom.** `estimated: true` was added by
class sweep D on 2026-09-17 precisely because the fee numbers were the client's
guess — the flag was right, and nobody asked why it never turned off.

### Found beside it: `marketplace_id = 'sparrow'` is in nobody's vocabulary

All **7** listings on production carry `marketplace_id = 'sparrow'`, written by
`p2p_listing_router`. That value does not appear in:

* `VALID_MARKETPLACES` in `marketplace_listing_router.py` — `{collectai, ebay,
  mercari, cardmarket, stockx, bricklink, tcgplayer, discogs}`;
* the client's `MarketplaceId` union, which has the same eight;
* `marketplace_fee_schedules`, whose Sparrow row is keyed **`collectai`**.

So the P2P writer uses the post-rename name and every validator and vocabulary
still uses the pre-rename one (CollectAI → Sparrow Collect, 2026-05-04). It is
invisible today only by luck: `MARKETPLACE_CONFIG['sparrow']` is undefined and
the `?? MARKETPLACE_CONFIG.collectai` fallback happens to render "Sparrow P2P",
which is the right label for the wrong reason. A `PATCH` that validated
`marketplace_id` would reject every row the P2P flow has written.

**Left as a decision, not guessed at:** either the stored value becomes
`collectai` (a data migration over 7 rows, and the fee-schedule key already
agrees), or `sparrow` becomes canonical everywhere (additive in three places,
plus a fee-schedule row). Picking one silently is how the two names end up
meaning different things in different files — which is what this already is.

### The gate worth writing

A provider function returning a camelCase-typed value from a `collectorsApi`
call **without a `.map(`** between them. The probe
(`scratchpad/probe_cast_not_mapped.mjs`) found all four with that rule and one
false positive — its own explanatory comment, the first failure mode in
[[learning_four_ways_a_new_gate_is_wrong]]. Worth promoting to
`scripts/check-cast-not-mapped.mjs`; not written yet.

Related: the same shape server-side would be a Pydantic model that does not
match its query's column names, which `check_sql_columns.py` already covers.

## The XP leaderboard — GATED 2026-09-18

Decided: **gate it, do not ship XP.** `GAMIFICATION_UI_ENABLED` stays false, and
`app/leaderboard.tsx` with no `categoryId` now renders a short state pointing at
the category boards instead of an XP/Level ranking. `PortfolioTierBadge` opens
`/leaderboard?categoryId=<the member's biggest category>` — and links nowhere at
all when they hold nothing, rather than opening a board with nothing to rank.

Why this way round: the category board ranks **real collections** (items owned
or value held), and it tells a member *"you are #N of M"*, which the XP board
never did. XP ranked one stranger's row on production — 50 XP, level 1 — because
only one account has any.

Gated at the SCREEN, not by removing the link: nothing in the app opens the XP
board any more, but a deep link still can, and that is exactly the mistake
`SELLING_ENABLED` documents (free-tier purchase mandates were unreachable in the
UI and reachable by Universal Link).

**Not touched, deliberately:** XP accrual on the server, and the XP wording in
`terms.tsx` / `privacy-policy.tsx`, which describe XP as a Service feature and
stay true while the data is still collected. If XP is ever REMOVED rather than
hidden, those are promises that must change with it.

### The original note

## V — the app sends a field the server drops on the floor (2026-09-18)

Class T with the arrow reversed, and worse: **Pydantic ignores unknown keys by
default**, so a client that posts `{"foo": 1}` to a model without `foo` gets a
**200** and no `foo`. The member believes they saved something. Same family as
the `{"ok": true}` class, one layer up.

**The sweep did not settle this, and the honest output is the coverage.**
`scripts/probe_ignored_fields.py` matches `post`/`patch`/`put` calls whose body
is an INLINE object literal and whose path is a template literal, maps the path
to a FastAPI route, and diffs the keys against the bound Pydantic model's
fields. It read **11 of the 87** write calls in `src/api/` — 13% — and found
nothing in those eleven.

**0 findings out of 13% coverage is not "clean".** Recording it as clean would be
the same mistake as a green gate whose matcher never fires
([[learning_a_test_file_is_not_a_gate]]), and this file's own rule is that a
checker which cannot fail is the worst kind.

### Run 2 (2026-09-19) — 57 endpoints proven, 3 unreadable, 0 findings

`scripts/probe_ignored_fields_v2.py` does what run 1 said the next run should —
reads each wrapper's payload **TYPE** from its signature rather than the call
expression — and then three more layers were added as each measurement showed
what it was still blind to:

| measure | run 1 | run 2, final |
|---|---|---|
| write calls fully checked | 11 of 87 (13%) | **53 of 87 (60%)** |
| payloads with proven keys | 11 | **65** |
| unreadable CALL SITES | 76 | 10 |
| **distinct ENDPOINTS proven** | — | **57** |
| **endpoints unreadable at EVERY layer** | — | **3** |
| findings | 0 (meaningless at 13%) | **0** |

**Per-endpoint is the honest denominator.** A thin `src/api` wrapper taking
`Record<string, unknown>` is a pass-through whose body the PROVIDER builds, so
the same `(verb, path)` shows up twice — unreadable at the wrapper, proven at
the provider. Counting call sites double-counts exactly the cases that are
covered.

**The three endpoints unreadable at every layer, and what is known about them:**

| endpoint | why unreadable | verified |
|---|---|---|
| `PATCH /purchase/mandates/{}` | `Record<string, unknown>` | ✅ **clean by hand** — the caller sends 8 keys, `MandateUpdate` declares all 8 |
| `PUT /notifications/preferences` | `Record<string, boolean>`, computed key `{ [key]: value }` | ✅ **clean by hand** — all 7 toggle keys in `NotificationPreferencesSection` are declared by `NotificationPreferencesUpdate`. A mismatch here is a settings toggle that silently does nothing |
| `PATCH /marketplace/listings/{}` | `patch as Record<string, unknown>` erases `Partial<MarketplaceListing>` | behind `SELLING_ENABLED = false` |

**The probe was wrong NINE times**, in three kinds, and only the first kind
could produce a false finding:

**Corrupted the findings (4):**

1. **It matched routes by suffix**, so `POST /marketplace/listings` was
   attributed to `p2p_listing_router.create_listing` — a different router,
   mounted at `/p2p`. Fixed by reading `APIRouter(prefix=…)` and matching the
   FULL path exactly.
2. **It keyed Pydantic models by bare class name.** `ListingCreate` is declared
   in BOTH `marketplace_listing_router.py` and `p2p_listing_router.py`, so the
   second overwrote the first and the probe reported `marketplace_id` and
   `format` as undeclared when the bound model declares both. Now keyed by
   `(file, class)`, resolved in the route's own file first.
3. **A backtick was listed as both an opener and a closer** in the argument
   splitter's `if/elif`, so the opener branch always won and depth never
   returned to zero: **every call with a `/items/${id}` style path was counted
   as having NO BODY.** Fixing it moved coverage 37% → 49% and "no body" from 32
   to 9. A template literal is delimited by the same character at both ends and
   cannot be counted like a bracket.
4. **The payload-type lookup was not scoped to the enclosing wrapper.** It took
   the last matching signature anywhere above the call, and its pattern only
   matched a FIRST parameter — so `updateMandate = (id, payload: Record<…>)`
   was skipped and the call was credited with **`createMandate`'s** object type.
   That alone invented **five** findings, reporting POST keys against PATCH
   routes. Scoped to the enclosing declaration, the count went back to 3.
5. The first regression test for the fix **could not fail**: it asserted the API
   wrapper's behaviour, and TypeScript types are erased at runtime, so renaming
   the wrapper's field back changed nothing a hand-written call passes through.
   Re-pointed at the CALL SITE, where the bug actually lived.

**Overstated the gap (3) — none invented a finding, all inflated the unknown:**

6. **Six "unreadable" calls were not endpoints.** `post(path, body)` inside
   `httpClient`, `storageApi` and `collectorsApi` takes the path as a PARAMETER.
7. **Seven send `{}`.** An empty body cannot lose a field.
8. **Six were single-key shorthand** — `{ status }`, `{ plan }`, `{ price }` —
   and the key pattern required a `:` or `,` where shorthand ends with `}`.

**Under-read the coverage (2):**

9. **It scanned only `src/api`.** For anything routed through `dataProvider` the
   wire payload is built in `src/data/providers` — `eventsProvider.createEvent`
   posts a 19-key snake_case literal while the wrapper it calls takes
   `Record<string, unknown>`. Scanning both layers: 50% → 57%.
10. **It could not read a body built as a LOCAL.** Providers assign
    `body.contact_email = patch.contactEmail` one line at a time. Reading those
    assignments: 57% → 60%.

**The sequence is the lesson.** Fixing defect 3 took the findings from 3 to 8,
and five of those new ones were defect 4 talking. A probe that has just started
reporting MORE is not therefore finding more — re-verify each new finding
against both ends before believing the delta.

**And the method error worth more than any of them:** the first caller analysis
read the keys passed to `dataProvider.*` and flagged `contactEmail` /`logoUrl`
as camelCase going to a snake_case model. `dataProvider` is a DOMAIN interface;
`updateSponsorCompany` maps every one of those to `body.contact_email` /
`body.logo_url` before the wire. **Reading the wrong LAYER produces findings
that are wrong in the most convincing way** — the names really do differ, just
not where it matters.

**✅ LIVE and fixed: every verified sale lost its date and its venue.**
`submitVerifiedSale` declared `sale_date` and `marketplace`; the server's
`VerifiedSaleRequest` declares **`sold_at`** and **`platform`**. Pydantic
dropped both and answered 200, the member read *"Sale price recorded —
thanks!"*, and `tsc` was satisfied because the client's own type declared the
fields. Confirmed on production: the one `verified_sales` row has `sold_at`
NULL. Verified sales are the ground-truth input to the pricing model, so a sale
with no date cannot be weighted against the market at the time it happened.
Fixed in `src/api/miscApi.ts` and `useItemDetail.ts:557`; pinned by a call-site
test, mutation-proven.

**Three more — ✅ removed 2026-09-19, and NONE of them was live.** All three sat
behind `SELLING_ENABLED = false`, and checking the callers downgraded them
further: **no code passed any of them.**

| call | declared | the model declares | who passed it |
|---|---|---|---|
| `POST /marketplace/listings` | `condition_description` | `condition_label`, `condition_notes` | nobody |
| `POST /marketplace/listings/fees/calculate` | `category` | marketplace_id, price, shipping_cost — the fee is a property of the MARKETPLACE | one call site, as `category: undefined`, which `JSON.stringify` drops |
| `POST /marketplace/listings/accounts` | `api_key` | `oauth_token_enc`, `refresh_token_enc`, `token_expires_at`, `scopes` | nobody |

⚠️ **A correction worth keeping.** These were first reported — to Merle — as
live-ish risks, with `api_key` described as "a key typed into the connect form is
discarded while the account reports connected". **No form collects it.** The only
`api_key` occurrences in the app are Sentry redaction. The probe proves a TYPE
mismatch; it says nothing about whether a caller passes the field, and that
second question is what decides whether a member can lose data. Ask it before
ranking a finding.

Removed rather than renamed: `docs/P2P_MARKETPLACE_SPEC.md` is explicit that the
eBay OAuth backend does not exist (which is why `SELLING_ENABLED` is false), so
there is no `api_key` column to map to and inventing one would be worse than the
gap. Deleting the declaration is what stops the next caller sending a credential
into a 201 that stores nothing.

**This class was already known here, and guarded with a COMMENT.** `miscApi.ts`
carries: *"DO NOT call this directly from screens — the server contract
(`WatchlistCreate`) reads `name`, NOT `title`; calling this raw helper with
`{title}` silently stores a junk row title."* Someone hit this exact bug and left
a warning instead of a check, which is why the class was worth a probe at all.
(`connection_requests` exists on the preferences model and no UI exposes it —
class T, benign.)

**✅ `npm run check:dropped-fields` — in `verify:prebuild` since 2026-09-19.**
It fails two ways: a proven payload carrying a key its route's model lacks, and
a NEW endpoint whose payload cannot be proven at any layer and is not in
`ALLOWLIST`. The second matters — without it the gate is dodged by typing a
payload `Record<string, unknown>`, which is exactly what the three grandfathered
endpoints do. Each allowlist entry carries the reason it was cleared by hand.

**It passed while blind, and the mutation is what found that.** Renaming
`category_id` → `categoryId` in a provider body produced **no finding**, because
`POST /events` was never matched to a route at all:

* `app/features/events/_router.py` declares `router = APIRouter(prefix="/events")`
  while the routes live in `events_core.py`, so a per-FILE prefix lookup saw none;
* and those routes decorate **`core_router`**, an ALIAS of that shared router, so
  a `(directory, variable)` lookup missed it too.

**9 of 62 endpoints were read and never compared, while the PASS line claimed all
57 agreed with their model.** (The PASS line was overstating in a second way
too, found by re-reading it afterwards: it counted endpoints whose payload was
READ, including 3 whose route binds no Pydantic model and so has nothing to
disagree with. It now reports **54 compared, 3 modelless, 3 allowlisted**.) Resolution is now file → (directory, variable) →
directory-alone, the last used only where every APIRouter in that package agrees
on one prefix (1 of 4 packages qualifies — `features/events`, which is what it
was written for). Matched 53 → **62**, unmatched **9 → 0**.

The intermediate attempt keyed prefixes by DIRECTORY alone and collapsed 58 of
64 endpoints, because `app/features/` holds dozens of modules that each name
their router `router` — **the models mistake one level up**, made again in the
same file within the same hour.

Mutation-proven both ways: the rename exits **1** and names the route and file;
a clean tree exits **0**; removing an ALLOWLIST entry exits **1**.

**Why the coverage is low, and the better method.** Most wrappers do not inline
their body — they take a TYPED PARAMETER and pass it through:

```ts
export const updateAlertPreferences = (prefs: {
  price_drop_enabled?: boolean; …
}) => patch<…>("/settings/alert-preferences", prefs as Record<string, unknown>);
```

The keys are in the SIGNATURE, not at the call site, and `as Record<string,
unknown>` erases them for good measure. So the real probe should read each
exported wrapper's payload TYPE — the same parse `scripts/probe-dropped-fields.mjs`
already does for response types — rather than the call expression. That is the
next run; it was not written today.

One thing worth stating now, because it bounds the risk: a mismatch here is
**invisible on both sides**. The server returns 200 and the client's own type
says the field exists, so neither `tsc` nor a test that mocks the API can see
it. Only a diff of the two declarations can — which is exactly why the class is
worth a gate rather than a read-through.

## W — a column the schema carries that no code mentions (2026-09-18)

`marketplace_listings.reports_count` was found by accident: written on every
report, read by nothing. This sweep looked for the rest — and the answer is
reassuring in a specific, checkable way.

**The probe** (`scripts/probe_dead_columns.py`): every column in
`scripts/schema.lock.json` whose bare name (and camelCase form) appears NOWHERE
in `server/app`, `server/workers`, `server/pipelines`, `src/` or `app/`. A
membership test, not a parse — a name that collides with a common word looks
"used", so false NEGATIVES are expected and false positives are the finding.

**1164 of 4685 columns**, which drops to **524 across 177 base tables** once
views are excluded — a view's columns are selected by the view's name, so
"absent from code" is meaningless for them. That exclusion is most of the noise.

### The measurement that matters: is anything WRITING them?

A column with no reader and NO DATA is schema debt. A column with no reader and
DATA is the `reports_count` shape — a live write going nowhere. The two need
opposite responses, and only production can tell them apart.

Sampled the app's core table, `items`, which had 19 unreferenced columns:

| | |
|---|---|
| **18 of 19 hold no data at all** — `count(<col>) = 0` across every row | `acquisition_price`, `actual_price_eur`, `ai_estimate_usd`, `authenticity_score`, `build_notes`, `build_state`, `checklist_item_id`, `date_completed`, `date_started`, `fraud_details`, `fraud_flags`, `fts`, `identity_locked_at`, `latest_forecast`, `paint_state`, `prediction_confidence`, `verified_date`, `verified_price` |
| the 19th, `identity_locked`, is non-null on all 17 rows — **and every one is `false`, its column DEFAULT** | so nothing writes it either |

So on this table the class is **dead weight, not data loss**: fossils of
abandoned features (build/paint state, fraud flags, verified price, AI
estimates, checklists). Nothing is being silently discarded.

### ✅ Twelve dropped 2026-09-18 (migration `20260918c`)

`acquisition_price`, `authenticity_score`, `build_notes`, `build_state`,
`checklist_item_id`, `date_completed`, `date_started`, `fraud_details`,
`fraud_flags`, `identity_locked`, `identity_locked_at`, `paint_state` — applied
to production, lock regenerated and diffed (exactly those twelve plus the CHECK
that rode on `build_state`; nothing else blessed), six schema gates PASS,
deliberate restart, `/healthz` `db:up`, 4092 tests green.

**Seven of the nineteen were NOT dropped, and finding out why is the whole
lesson.** The narrow scan said "unreferenced"; four checks said otherwise:

| check | what it caught |
|---|---|
| grep the WHOLE repo, not `server/app` + `src/` | `items.fts` has a writer in `services/collectors_merge/workers/build_fts_index.py` — a path the first scan never looked at |
| `pg_depend` through `pg_rewrite` | seven columns are read by VIEWS: `actual_price_eur` (`items_scored`), `ai_estimate_usd` / `fts` / `latest_forecast` / `verified_date` / `verified_price` (`items_with_latest`), `prediction_confidence` (`api_user_analytics_v1`). Dropping those needs CASCADE and a view rebuild — real risk, no behaviour change |
| `pg_indexes` | `fts` carries a GIN index |
| assert emptiness IN the migration | so it refuses rather than trusts a measurement taken minutes earlier |

The one hit for `authenticity_score` was a mock object in a dev shell script,
not the column — checked rather than assumed.

**The rule: "no code mentions it" is a candidate, never a verdict.** A column is
safe to drop only when the repo (all of it), the views, the indexes and the data
all agree.

### What to do with the rest

**Nothing urgent, and that is the finding.** These cost a little schema noise
and a lot of misdirection — the next person reading `items` sees
`acquisition_price` next to `purchase_price` and has to work out which one is
real (it is `purchase_price`; `acquisition_price` has never held a value).
Dropping them is a migration per cluster and a schema-lock regen each time,
which is real work for no behaviour change.

**The rule worth keeping:** when a column turns up unreferenced, the question is
not "is it used?" but **"does it have DATA?"**. Empty is debt; populated is a
write that goes nowhere, and that one gets fixed the day it is found — as
`reports_count` was.

## Decisions for Merle — the XP leaderboard (2026-09-17)

`GAMIFICATION_UI_ENABLED = false`, and `UserStatsSection` hides XP and level on a
profile with the comment "XP is not a shipped feature" (2026-08-10). But
`app/leaderboard.tsx` with NO `categoryId` renders an **XP/Level board**, behind
no flag — and `PortfolioTierBadge` (analytics) links straight to it. The screen
sweep shows it as one stranger's row ("Merle · 50 XP · Level 1 · 1 day streak")
followed by an empty screen, because only one account in production has any XP.

The two consistent ways out, both yours:

1. **Gate it like the rest of gamification.** Then `/leaderboard` with no param
   needs something to show — the category board requires a `categoryId`, so this
   also means deciding where `PortfolioTierBadge` should point.
2. **Ship XP properly**, and un-gate `UserStatsSection` with it.

What is NOT in question: today one screen presents XP as a feature while another
deliberately hides it, and the same flag file states the rule ("anything here has
to be a feature the app actually ships"). Also note the XP board has no "you are
#N of M" line, which the CATEGORY board does have — so a member outside the top
ranks learns nothing about themselves from it.

## Class G — worked 2026-09-18

Three of the four turned out not to be product calls at all; one was, and it is
sharper than the original note.

**1. Pro analytics were open to free accounts — ✅ FIXED.** Two endpoints took
any authenticated caller while `docs/MONETIZATION.md` lists both as Pro and the
app gates them on `limits.advanced_analytics`:

* `/data-moat/demand-heat` — the data behind "Hot Right Now", Pro-gated in the
  app since 2026-04-18 and sold on the paywall card as "Advanced analytics";
* `/portfolio/realised-pl` — listed as Free: No / Pro: Yes. It has no client
  caller yet, which is the point: the surface that eventually reads it now
  inherits the tier instead of re-deciding it.

Both now `Depends(require_plan("pro"))`. Gated per endpoint, not per router:
the other data-moat endpoints have not been traced to a Pro-only surface, and
gating one that a free screen quietly depends on would break it for everyone.
**A paywall only the client enforces is not a paywall** — same shape as the
free-tier purchase mandates that were unreachable in the UI and reachable by
Universal Link.

**2. `max_daily_deal_alerts` enforced nowhere — ❌ THE NOTE WAS WRONG.** It is
enforced, in `workers/deal_discovery_worker.py:196`, which reads it from
`PLAN_LIMITS` with a comment explaining that the app must not advertise a
number the worker does not enforce. It is not on a serving path because the cap
is on alerts CREATED, which is the worker's job. No action; the register entry
was stale.

**3. Sell timing requires `premium` — ❌ NOT A PAYWALL DECISION.** The feature
is not built: `SellTimingBadge` only ever rendered a "Coming soon · Premium"
teaser and was hidden on 2026-07-22, and nothing in the app calls
`/sell-timing/*`. The gate is on an endpoint no one reaches, for a feature that
does not exist. The tier question becomes real when Sell Timing is built, and
not before.

**4. A paywall-less build could reach the store — ⚠️ WORSE THAN DESCRIBED, and
it needs YOUR call.** The original note said `submit.production` shares an
`ascAppId` with `store`. In fact **all three submit profiles — `production`,
`store` and `internal` — point at the same `ascAppId` (6767359453)**, and
`internal` is exactly the BUILD profile that sets
`EXPO_PUBLIC_BETA_UNLOCK_ALL=true`, which reports every user as `pro` and skips
RevenueCat. So `eas submit -p internal` publishes a paywall-less build to the
real app record.

`npm run check:submit-profiles` reports it. **Deliberately NOT in
`verify:prebuild`**: it fails on a configuration you may want, and a gate that
fails on an intentional state teaches people to ignore gates.

**Corrected 2026-09-18 — "delete `submit.internal`" was a bad suggestion of
mine.** That profile exists *so paid screens can be reviewed on TestFlight*
(its own comment in `eas.json` says so), and TestFlight is attached to the app
record — sharing the `ascAppId` is how TestFlight works, not a misconfiguration.

The real hazard is one step later, and sharper: `store` and `internal` are BOTH
`autoIncrement: true` against one app record, and `cli.appVersionSource` is
`remote`, so **EAS owns the build numbers and both profiles draw from a single
increasing sequence**. "Promote the latest build" can therefore pick the
paywall-less one, and the number itself carries no hint of which profile made
it. The band cannot be set from `eas.json` for the same reason: EAS owns it.

**What shipped instead: the build announces itself.** When
`EXPO_PUBLIC_BETA_UNLOCK_ALL` is true, Settings renders a warning-toned banner —
*"Beta build — every Pro feature is unlocked and billing is skipped. Not for the
store."* Visible in TestFlight, to an App Store reviewer, and to whoever is
about to promote it. Untranslated on purpose: the reader is a developer, a
reviewer or a tester, and it never renders in a store build, where the flag is
pinned false.

**✅ DECIDED AND DONE 2026-09-19 — the default was flipped instead.**

The sharper reading is in `eas.json`'s own comment: the **EAS `production`
environment** held `EXPO_PUBLIC_BETA_UNLOCK_ALL=true`, so the dangerous value was
the DEFAULT and safety depended on every submittable profile remembering to pin
`false`. Three did. A fourth profile added by someone in a hurry would not have.

`EXPO_PUBLIC_BETA_UNLOCK_ALL` is now **`false` on the EAS `production`
environment**, and `build.internal` pins `true` explicitly — so paid-screen
review on TestFlight still works, and **forgetting to pin now yields a LOCKED
build instead of a paywall-less one.** Verified after the change: EAS reports
`false`; `store`/`production`/`android-apk` pin `false`; `internal` pins `true`;
`check:submit-profiles` still names `internal` as the one deliberate unlocked
path.

**A second app record was considered and rejected** (for now): it costs a new
bundle id, provisioning and a separate TestFlight, and means internal testers
stop testing the artefact that actually ships — ongoing friction against a
hazard that requires deliberately promoting an internal build, with a warning
banner on screen (`src/screens/Settings.tsx:79`). Revisit if anyone other than
Merle can promote a build.

Build 160 was built AND submitted with `--profile store`, and the build log
confirms the store profile's `false` overrode the EAS value.

**What could NOT be built, and why it matters.** Class G asked for "a
submit-time assertion" on the artefact. That cannot work, measured on a real
store APK: `assets/index.android.bundle` is Hermes bytecode, and while
`EXPO_PUBLIC_SUPABASE_URL`'s NAME survives in its string table,
`EXPO_PUBLIC_BETA_UNLOCK_ALL` does **not** — Expo's babel plugin replaces that
member expression with a literal, so the name is gone whatever the value was,
and both branches of the flag ship either way. A scan would report "absent" for
good and bad builds alike: a check that cannot fail. The guard therefore
inspects the CONFIG, which is decidable, and says plainly that it cannot catch
a hand-submitted internal artefact.

### The original notes



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

## X — committed to `web/` and never deployed (2026-09-19)

`web/` is a **separate Vercel project**. It does not ship with an EAS build or an
EC2 deploy, and nothing reports the gap — so a corrected legal sentence can sit
in the repo, reviewed and committed, while the public site keeps serving the old
one. `docs/AUTH_AND_WEB_DEPLOY.md` already carried two instances (the AASA
`/l/*` path and the `vercel.json` `/l/:id` rewrite, **twelve days**), but nobody
had swept the directory.

**Method** (read-only, repeatable): for every servable file under `web/`, derive
its public URL — `cleanUrls: true`, so `terms.html` → `/terms`, `index.html` →
`/` — fetch it and compare bytes.

**Result: 17 of 19 identical.** The deploy discipline is mostly good, which is
what makes the exception worth naming rather than a general warning.

**The one drift: `web/terms.html`, last changed `6f833a6` (2026-09-14), never
deployed — and it is TWO sentences, not one.**

| | repo (correct) | live (still served) |
|---|---|---|
| account creation | "You may register using **an email address and password**." | "You may register using **email/password or social login (Google, Apple)**." |
| price estimates | "…aggregated marketplace data from **public marketplace sources**." | "…aggregated marketplace data from **leading marketplace sources across 54 collectible categories**." |

The first is the one that matters: `SOCIAL_LOGIN_ENABLED=false`, the app offers
email only, and **an App Store reviewer checking guideline 4.8 reads the public
Terms.** The in-app copy was fixed and ships in every build — so the artefact a
reviewer is most likely to open is the only one still making the claim.

The second was found only because the sweep compares BYTES. Grepping for
"social login" — the known symptom — would have reported the file as fixed after
one hunk. The live text is also the *stronger* claim: the repo deliberately
softened "leading marketplace sources across 54 collectible categories" to
"public marketplace sources", and that softening is not live either.

**Discarded as a false positive:** `web/vercel.json` returns 404. It is consumed
by Vercel as configuration and is not a servable asset — a 404 there is correct.

**✅ FIXED — deployed and verified 2026-09-19.** `grep -c -i 'social login'` on
the live page returns **0**, `web/terms.html` is byte-identical to production
(22441/22441), and the softened price-estimates sentence went live with it. The
sweep now reports **18 of 19 identical**, the 19th being the `vercel.json` false
positive.

How it was deployed, after four `vercel login` attempts landed on the wrong
account every time: a **project-scoped token** with `npx vercel@latest --prod
--token … ` and **no `--scope`**. Full procedure and the three traps in
`docs/AUTH_AND_WEB_DEPLOY.md`.

## Y — a gate that has never seen its own bug (2026-09-19)

`check:double-submit` passed an unguarded write for two independent reasons and
nobody knew until the instance was found by READING. That raised the obvious
question about the other 49 gates in `verify:prebuild`, and it is answerable
mechanically: **42 of the 50 were added in the same commit as the code they
guard, so that commit's PARENT is a known-positive** — the bug is still there.
Drop today's checker into that tree and it must fire.

`scripts/sweep_gates_against_their_own_bug.py` does it in a detached worktree.

**Result: 40 of 42 fire. Zero blind gates.**

* `verify_items_contract.mjs` — **inconclusive, not silent**: it needs Supabase
  credentials and prints `SKIP — no Supabase URL / anon key in .env`, which a
  fresh worktree does not have.
* `check_i18n_defaults.py` — silent at its parent because that tree was already
  clean for its rule, **not because it is blind**: mutating a `defaultValue` to
  disagree with `en.json` makes it exit 1, and restoring makes it exit 0.

**The nuance that matters more than the score.** `check-double-submit` **FIRES**
on its own parent — it genuinely caught the 2026-09-17 instances — and was
*still* blind to the `delist` case found by hand on 2026-09-19. **Firing on the
bug it was born for does not mean it covers the class.** This sweep can only
retire the question "has it ever failed?"; it cannot answer "what does it miss?"

**The sweep was wrong three times before its own output was trustworthy**, and
every wrong version produced a confident, uniform table:

1. It cleaned the worktree AFTER checkout, so the checker copied in on one
   iteration blocked the next checkout — **every gate after the first reported
   `NO-PARENT`.**
2. Two runs shared one worktree path and fought over it; the loser's table said
   **"42 errored"** while the interim log had shown real results.
3. It ran each checker with no arguments, but `verify:prebuild` passes
   `--strict` to three of them. Those three PRINTED their failure and exited 0,
   so they were scored **silent** — 3 of the 5 apparent misses were this.

Each time the tell was the same: a uniform result. **All-42-identical is not a
finding, it is a broken tool.**

## Re-running a sweep

Give the agent: the class in one sentence, a **worked instance** from this repo,
the scope (and what is out of scope), "verify both ends before reporting",
"`file:line` + the user-visible consequence", "rank by money > privacy > social >
cosmetic", and "list the false positives you discarded and why". Read-only, no
edits, no prod writes.

Then write the gate before the fix, and prove the gate fails.
