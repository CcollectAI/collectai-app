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
| K | The save half-happened (multi-step writes without a transaction) | 2026-09-17 | ✅ all fixed: billing webhook `8439f97`, item edit, calendar, template, P2P listing transaction — **two server fixes not deployed** |
| L | The control is there but a person cannot use it (touch targets, labels, contrast) | 2026-09-17 | ✅ all three halves: contrast `19a8fdc` (accent 2.02:1 = brand decision), 6 unlabelled icon-only controls, 20 touch targets + `check:touch-target`. ~145 untranslated labels remain (I18N_BACKLOG) |
| S | The server answered `ok` and wrote nothing | 2026-09-17/18 **deployed** | ✅ **all 34 read**: 6 `ok`-without-a-write fixed, the announcement DM dead five months fixed, 4 money handlers made atomic + row-locked (a trade could complete twice or never; a sale banked twice; a mandate past its cap), 22 of the 34 sites cleared with the reason written down. 8 tests that PINNED the lie rewritten. One decision left: `reports_count` is written, read nowhere |
| T | The server sends it and the app never reads it | 2026-09-18 | measured: **74 of 461** fields declared in `src/api` are referenced nowhere else. Three confirmed: subscription dates ✅ **fixed** (the copy was already translated in 7 locales and rendered by nothing), realised P/L unreachable and the demand differentiator unshown — both product calls. The rest is mostly request params and deliberately-removed UI |

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
**NOT DEPLOYED** — server change, Merle's call.
Also open from K: ✅ `create-event.tsx` save-as-template — **fixed 2026-09-17.** The template save
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

### Found on the way: `marketplace_listings.reports_count` is written and read nowhere

`report_listing` increments it, carefully and only on a genuinely new report,
with a comment explaining that unconditional increments "would poison moderation
triage". **Nothing reads the column** — not `server/app`, not the app, not the
ops queue (which orders by age). It appears only in the schema dumps.

Two honest ends, and it is a decision rather than a bug: surface it in
`GET /ops/listing-reports` so triage can use it, or drop the column and the
increment with it. Until then the increment is a write that costs a statement
and buys nothing — the "capture ≠ consume" shape.


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

**So the gap is the WRITER, not the screen** — building the realised-P/L view
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
