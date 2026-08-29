# Sparrow Collect - Project Memory

> Renamed from CollectAI 2026-05-04 · Last refreshed 2026-08-26

## Five screenshots, eleven defects, and three of my own (2026-08-27)

Build 154 went to TestFlight and came back as five photographs. Every defect in
them was a rule this repo already holds, broken one level out from where it was
enforced — the pattern is in `docs/ui-playbook.md`. What belongs here is the
part about **measurement changing the answer**, which happened five times.

### Where I was wrong, and the data said so

1. **"The EUR 8,015 estimate is absurd."** It is a scryfall price for MTG
   Summer Magic *Bayou* — a real four-figure card. The estimate was the one
   correct thing on that screen; the comps beneath it were wrong. Chasing my
   first instinct would have "fixed" the right number.
2. **"Grade-mixing is the credibility gap."** The research says so, loudly. The
   data says only **150 of 71,860 items (0.2%)** have comps spanning multiple
   conditions — because `condition` is 100% populated and **2,926,015 of
   2,927,565 rows are the literal string `NM`**. A constant, not a signal.
3. **"The profile write doesn't land."** It landed. My query ordered by
   `created_at DESC LIMIT 8`, Postgres sorts NULLs FIRST on DESC, and rows with
   a null timestamp pushed the real one past the limit. **A partial answer
   reading as a complete one** — in my own check, on the same day I fixed three
   of them in the product.
4. **"These files are orphaned."** A barrel file re-exported one. `tsc` caught
   it; my grep had not. **A barrel re-export is a reference.**
5. **"diversity_factor just needs the provider fallback."** It does — and that
   doubles the confidence score on **45.7%** of items. Measuring the blast
   radius turned a one-word fix into a decision.

### The reject list I shipped, and audited an hour later

I ported `_TCG_REJECT_TOKENS` to a filter running on EVERY category and kept its
substring matching. `"tin"` is inside S·tin·g, Con·tin·ental, Tin·tin,
Pain·tin·g, Quen·tin, Chris·tin·a: **7 of 9 real titles rejected**, while the
section claimed "no listings matching this item" — worse than the noise it
replaced, because it looks authoritative.

The galling part is that I **quoted**
`learning_keyword_filters_need_per_category_false_positive_audit` in the commit
that introduced it. I applied "read every match" to the relevance rule and not
to the list I pasted in beside it. **Quoting a learning is not applying it.**

### `or 0` erases a NULL, three times over

The 2026-08-12 `[]`-vs-`None` work made the collector honest and left every
consumer alone. `((totals or {}).get("api_5xx") or 0) >= 10` evaluated an
unknown to False, so "API returning 5xx" silently vanished for two days while
the window held 16. **Fixing the number is not fixing the alert built on it.**

Same shape twice more: `h["source"] or "unknown"` labelled 100% of comps
"Unknown" with `provider` populated in the adjacent column, and
`float(change_7d_pct or 0)` would have turned "no measurement" into "0.0%".

### Deleted twice means the writer is missing

"Movers" (08-14) and "Holdings"' percentage (08-26) were both deleted for
reading `change_1d_pct`, which the server has never returned. Both times the fix
was deleting the READER. Nobody asked why the number did not exist — it was
computable throughout, and 66,172 of 71,858 item_refs have the history for it.

**When a feature is deleted twice for reading an empty column, look at the
writer.**

### Render the component

The export bug — an authed URL handed to `Linking.openURL`, so a paying member
got `{"detail":"Authentication required"}` in a browser — was perfectly
type-correct and reached TestFlight. `@testing-library/react-native` was already
a dependency. Three suites now mount the changed components in CI, including one
that presses Export and asserts `Linking.openURL` is never called.

## A nightly job reported success while dropping a fifth of the catalogue (2026-08-29)

The watchdog's "API returning 5xx — 16 in 24h" resolved to **one GitHub Actions
run**: `nightly-ingest`, which logged **107 failed catalog batches** — up to
~21k rows — and exited **0**. Attribution came from the client IP in
`edge_logs`: `4.154.215.8` is Azure (a runner), not EC2 (`51.21.210.195`), not a
laptop. Three unrelated causes hiding behind one green checkmark:

| n | rejection | cause |
|---|---|---|
| 15 | `21000` ON CONFLICT twice | no within-batch dedupe **on the branch that runs** |
| 42 | `PGRST102` all keys must match | `to_row()` adds `image_url`/`barcode`/`attributes_json` conditionally |
| ~50 | client has been closed | a sibling pipeline called the module-global `close_http_client()` mid-run |

**The obvious fix for the middle one is a data-loss bug.** Padding rows to a
common key set makes the batch legal, and `merge-duplicates` then writes
`image_url = NULL` over an image already in the catalogue. Group by key set
instead. *Sending fewer columns is safe; sending NULL is a write.* Same shape as
the `price`/`price_eur` trap in `DATA_SCALING_PLAN.md` §10.

**Fix the shared resource, not the six callers.** Six pipelines import
`close_http_client`; auditing them would have left the seventh to be written.
`SupabaseIngest.client` is now a property resolved per call, so a sibling's
shutdown is harmless.

### The delivery problem was the whole of finding #1

The dedupe had existed since 2026-07-29 and never ran, because GitHub cron runs
the **default branch** and that was `feature/all-enhancements`, last touched
2026-08-12. **PR #4 fixed exactly this and sat open for 8 days.** Repointed the
default to `feat/marketplace-and-target-hit`. Two things worth keeping:

- `gh repo edit` needs the **`CcollectAI`** account; the usual active account
  `SammySamEU` gets a bare `HTTP 404`, which reads as "no such repo".
- **This moves the drift, it does not end it.** The default is now a *working*
  branch, so anything unpushed still does not run — hours of lag instead of 17
  days. Do not let the ✅ read as more than that.

### I wrote the wrong-population aggregate INTO the commit that fixed silent failures

Adding a "wrote N of M rows — K LOST" summary, I reported
`self.stats.catalog_errors` beside this call's row count. That counter is
**shared** — `crawl4ai_enrich.py:404` and `firecrawl_enrich.py:381` both do
`SupabaseIngest(stats=stats)` — so the line would state a whole-run figure as a
fact about one upsert. [[learning_aggregate_over_the_wrong_population]], written
by me, an hour after quoting the doc that contains it.

It was caught only because Merle asked for a recheck. The tests I had already
written were all green: they covered the three bugs I set out to fix and said
nothing about the diagnostic I added while fixing them. **New code written
during a fix is unaudited code — including, especially, the code that reports
the fix worked.** Now pinned by
`test_loss_report_counts_only_this_calls_failed_batches`, mutation-tested.

Same pass: `test_to_row` had been red for a month **pinning the pre-2026-07-25
double-encode bug** — it passed only while the writer was wrong. A red test is
evidence about the doc, not automatically about the code.

## The queue filtered on a column the query did not value on (2026-08-26)

Worked today's watchdog: 2 HIGH, 2 MEDIUM, 1 INFO. **One HIGH was real with the
wrong cause named, one HIGH was false, one MEDIUM carried a wrong remedy and was
hiding a third HIGH, and one MEDIUM was correct.** Details in
`docs/WATCHDOG.md`; the transferable part is here.

`valuation_worker.run_once()` selects `COALESCE(price_eur, price)` and filters
`WHERE price IS NOT NULL`. **The predicate and the projection are different
questions**, and `market_hits` really does hold two different numbers — `price`
in the original currency, `price_eur` normalised, differing on 1,958 recent USD
rows. So a writer that fills only `price_eur` produces rows that are usable by
every line of the worker except the one that fetches them.

`scripts/load_lorcana_direct.py` was that writer. Consequence, measured:

| | |
|---|---|
| lorcast sold comps | 5,420, written in a 2-second window on 2026-08-15 |
| `processed = true` among them | **0**, for 11 days |
| `price_predictions` rows for lorcana, ever | **0** |
| what the watchdog said | "coverage collapsed … a keying or crosswalk fault" |

The crosswalk was intact. **Zero predictions against thousands of comps is not
a matching failure — a matching failure produces predictions that are wrong or
missing for *some* items, not an empty table.** That distinction is what turned
a five-day-old wrong diagnosis around, and it came from asking for the count
rather than reading the finding.

The class was enumerated with the queue's own predicate before anything was
edited: **exactly 5,420 rows, all lorcast, out of 2,796,800 sold rows.** No
judgment triage, and the number bounded the fix.

**Fixed at the writer, not the reader**, on purpose: relaxing the filter to
`COALESCE(...) IS NOT NULL` de-aligns the partial index whose predicate mirrors
it, and that index exists because the seq-scan version hit the pooler's 30s cap
and blew the bake cycle. `DATA_SCALING_PLAN.md` §6 rule 1 refuses new indexes by
default and §10 already prescribes this exact remedy — *"Writer bugs hide in
INSERT column lists … add to the list + backfill"* — for the identical defect on
`category` in the same table. **The doc had the answer before the investigation
did.**

Three defences shipped, because the fix alone repeats in six months:

1. `price` added to the INSERT column list, with the comment saying why the two
   columns are not one column twice.
2. `20260826_backfill_lorcast_price_from_price_eur.sql`, scoped
   `currency = 'EUR'` so it is a restatement not a currency error, and it
   **RAISEs if any row is left behind** — a backfill that no-ops must not
   report success. Applied: 5,420 rows, 0 stragglers, queue now sees lorcana.
3. A daily watchdog check, **"valuation queue visibility"**, that asks the
   queue's predicate of the whole table. The coverage canary measures the
   OUTPUT of pricing; nothing measured the INPUT, so the two disagreed for
   eleven days with nothing to reconcile them. Proved failing on the real
   defect *before* the backfill (`high`, naming lorcana/lorcast/5420/08-15),
   green after.

### A blind sub-query does not remove a number, it removes a FINDING

The `medium` "could not read part of the Supabase logs" told Merle to refresh
the PAT. The PAT was fine — a valid `sbp_` token that `postgres_logs` answered
with **in the same run**. Only `edge_logs` was failing, *intermittently*: 2 of
10 identical requests succeeded inside a minute, and 4 more failed at 25s
spacing after a 60s cooldown, so not rate limiting either.

The teeth: `api_status_codes` is the input to **"API returning 5xx"**. On 08-25
and 08-26 that HIGH silently vanished, while the same window really held **16
5xx**, over the `>= 10` threshold.

The 2026-08-12 `[]`-vs-`None` fix worked exactly as designed — the total read
`None` — and `((totals or {}).get("api_5xx") or 0) >= 10` evaluated it to
False. **`or 0` turns UNKNOWN into "fine".** Fixing the number is not fixing
the alert built on the number; a missing total is visible in the JSON, a
missing *bug* looks like a healthy day. The finding is now three-state (high /
`UNKNOWN this run` medium / silent), and sub-queries retry 3× with backoff.

Both halves were verified live: one run retried into success and the 5xx HIGH
reappeared with `16 in 24h`; a later run had **all 3 attempts fail** and
correctly reported *"API 5xx rate is UNKNOWN this run"* rather than nothing.
The blind finding also now exonerates the credential whenever another query on
the same token answered.

### The false HIGH: a grade that never asked about the writer

"column drift: 1 reader/writer column mismatch" paged daily since 08-22.
`market_hits.seller_rating` and `seller_score` are **both** 0 non-null out of
3,073,177 rows; **no INSERT in `server/` lists either one**. The "reader" is a
key in Firecrawl's extraction JSON schema, the "writer" a field on a Pydantic
*response* model — neither is SQL.

`audit_column_drift.py` graded `HIGH if ro_n == 0` and never looked at `wo_n`,
under a headline asserting the sibling *was* written. Drift needs a live writer
by definition. HIGH now requires `wo_n > 0`; both-dead is a separate
`DEAD_PAIR`. And the alert **never named the columns** — the "a failing worker
must say WHY" rule, unapplied here — so it now reads `--json` and names them.
Both arms mutation-tested against prod: the real pair drops to DEAD_PAIR, and a
synthetic starved-reader/live-writer pair still fires HIGH.

⚠️ **My first arity checker was itself wrong** — its regex stopped at the `)`
inside `now()` and reported a column/value mismatch that did not exist. Second
time this month a checker written during an audit lied. Mutation-test the
checker, not just the code.

⚠️ **The deployed audit is a separate artefact from the deployed watchdog.**
The first patched run still emitted the false HIGH because `watchdog.py`
shells out to `/opt/collectors/server/scripts/audit_column_drift.py`, which was
still the old file. Three-way code split, again.

## A parity gate is blind to the key one side never declared (2026-08-26)

Asked to check whether the subscription page's claims are true. Every NUMBER
was right — 10 mandates, 25 watchlist slots, 1 Target Hit a day, unlimited on
Pro — and the doc, `useBillingLimits.ts` and `PLAN_LIMITS` agreed on **27 of 30
cells**. The three that disagreed were all the same key.

`max_alerts_per_week` (free 1 / pro None / premium None) existed **only on the
server**. It was enforced the whole time — `alerts_feature_router.py:158`,
a 403 — and advertised on the free card as *"1 price alert a week"*, while
being absent from `DEFAULT_LIMITS`, `FORCED_LIMITS` and
`BillingStatus['limits']`.

**The interesting part is why `check:billing-limits-parity` passed.** It has two
arms, and the key fell through both:

| arm | why it missed |
|---|---|
| keys the FE reads as `limits.X` | nothing reads this one |
| numeric caps **both tables declare** | the FE declared nothing to compare |

So the gate compared the INTERSECTION of the two tables' keys, and the failure
mode it needed to catch was one side having a smaller key set. **Declaring the
key is what switched the gate on**: after the fix, setting the FE value to 2
exits 1 with `MISMATCH free.max_alerts_per_week: FE=2 BE=1`. Before it, that
mutation was green. A parity checker has to enumerate the **union**, or it
cannot see an omission — only a disagreement.

Nothing read the key, so nothing was broken today. The shape is the house one:
the first client to read `limits.max_alerts_per_week` would have got
`undefined` on the RevenueCat path, which reads as *no cap* rather than as an
error.

### A rename that reached the docs, the comments and the push — and no screen

`MONETIZATION.md` has said **Target Hit** since 2026-08-06, the code comments
say Target Hit, and `_check_watchlist_snipes` sends `title="Target hit"`. But
**not one user-facing string did**: the paywall sold *"Unlimited deal alerts"*
and Settings offered *"Deal alerts — when the Smart Deal Agent finds a match"*,
naming a different product entirely (the Smart Deal Agent is purchase
mandates). So the push said one thing and the screen that sells it said
another.

Verified before renaming rather than assumed: the cap at
`deal_discovery_worker.py:196` sits **inside `_check_watchlist_snipes`**, so
`max_daily_deal_alerts` really does govern Target Hit — the worker's name is
legacy. Had it gated mandate deals, relabelling it would have been wrong.

**Label only.** `watchlist_snipe`, the `deal_alerts` preference key and
`notify_user` category, and `max_daily_deal_alerts` all keep their names —
renaming a stored identifier orphans live rows. This is the tab
label/route/title rule (2026-08-19, 08-20) in a third place: a rename has a
surface for every audience, and docs + comments + a push title are three
audiences that are not the customer.

⚠️ **The plan-card test's free-card arm fails SILENTLY.** It does
`const line = freeCard.find(pattern); if (!line) continue;` — so a regex left
stale by a rename stops checking that cap and the suite stays green. Both
`/deal alert/i` patterns had to move to `/target hit/i`, and the new
`/price alert/i` row was added while in there. Mutation-tested all three: wrong
daily cap, wrong weekly cap and a reverted Pro line each go red.

### The defect the audit found was in the neighbouring row

The new Settings hint read *"When a watched item drops to your target price"* —
and the row directly above it, `price_alerts`, already said *"When an item hits
your target price or moves sharply"*. **Two toggles claiming one trigger.** The
discriminator is in the worker's own message — `"€X on {provider} (N% below
your target)"` — Target Hit fires on a **marketplace listing**, price alerts on
a valuation move. Corrected to *"When a watched item is listed for sale below
your target price"*.

Found by reading the neighbour, not the diff, which is the third session
running that the neighbouring line was the spec.

### Also settled, by measurement rather than argument

- **`RATE_LIMIT_RPM=600` is live.** `/opt/collectors/.env` reads 600 and the
  bake has been up since **2026-08-23 17:51:46 CEST**, so the restart carrying
  it happened. The memory carrying this as ⛔ STILL OWED was stale and is
  corrected. Still not walked on a device.
- **`dossier_agent.py` is byte-identical to prod**, so the 2026-08-18 dossier
  fixes are deployed and "Dossier PDF export" is a claim the app honours —
  `/dossier/{id}/export` is `require_plan("pro")`, while the JSON endpoints are
  not, which matches copy that sells the *export*.
- **"Community access" overclaimed** with `COMMUNITY_GATED = true` hiding the
  leaderboard and Find Collectors. Now "Community events", the doc's own word.
- ⚠️ A `grep -r --include=*.py` written during this audit was **eaten by zsh
  globbing** and reported 0 enforcement sites for every plan flag. Quoted, the
  real answer is deal_discovery 24, set_completion 9, condition_grading 6.
  Trusting it would have produced "no Pro entitlement is enforced anywhere" —
  a checker written in a hurry lies, again.

## A sweep that stops early looks exactly like a sweep that found nothing (2026-08-23)

The morning's jsonb sweep reported six corrupted columns and was written up as
having "enumerated mechanically over every jsonb column in `public`". Re-running
it that evening — after the encoder was finally live — found a **seventh**:
`user_feedback_events_v1.value_json`, holding
`"{\"notes\": null, \"value\": \"inaccurate\"}"` since 2026-08-17. A
price-disagree feedback record, double-encoded, sitting beside two healthy
objects in the same column.

**Three distinct ways the same sweep returned a false clean**, all found by
running it again rather than by re-reading it:

1. **A statement timeout.** As one `UNION ALL` across every jsonb column, the
   query blew the 120s direct-DSN cap on `market_hits` (2.7M rows) and returned
   **zero rows**. Zero rows is also what "no corruption" looks like. Now one
   statement per column.
2. **`ERROR: invalid input syntax for type uuid`.** With `ON_ERROR_STOP` on, one
   bad relation aborted the run at column **148 of 208** — 60 columns never
   checked, and the output ended without saying so.
3. **A `json` column, not `jsonb`.** `items_card_archived.tag_names` is `json`,
   and `jsonb_typeof()` refuses it without a cast. A hand-written column list
   would have skipped it in silence.

**The rule: a sweep must report its own completeness.** Row count is not
evidence of coverage — print a terminal marker (`=== SWEEP COMPLETE ===`) and
count the checks generated against the checks that ran. An empty result set and
a dead query are indistinguishable otherwise, and this one hid a live defect for
six days.

**And validate values, not just shapes.** The same run flagged
`feature_dictionary.default_value` as holding booleans, strings, numbers and
nulls. That is **not** corruption — it is a column of *default values*, and
`true` / `0` / `"raw"` are exactly what belongs there. Reporting it as a hit
would have been a fabricated defect one line above a real one.

### The one junk file that hard-broke two views

`items_card` and `items_card_archived` both cast the first path segment of every
object in the `item-images` bucket to uuid:

```sql
AND (storage.foldername(o.name))[1]::uuid = i.id
```

That bucket holds exactly **one** object — `Untitled folder/.emptyFolderPlaceholder`,
the artifact Supabase Studio leaves when someone clicks "new folder" in the
dashboard and never names it, created 2025-08-25. Both views therefore **threw**
rather than degraded, for up to a year, with no symptom — because nothing reads
them. They are leftovers from the app that preceded this codebase, appearing
only in `docs/schema-lock.md` and `scripts/schema.lock.json`, both GENERATED
inventories rather than usage. Dropped 2026-08-23.

**A dashboard click wrote unqueryable data into prod**: no migration, no code
path, no review. When a view casts a value it does not control, guard the cast.

⚠️ **DDL stales the lock, and the lock only bites on the NEXT restart.** The
drop made `preflight_schema_lock` FAIL — *proven* by running it, not assumed —
so a restart at that moment would have left prod down, exactly the earlier
hour-of-downtime incident. Regenerated, re-verified (all nine stages PASS), and
the lock pulled back into the repo before anything could restart.

## The item card: every defect was a rule enforced one level too low (2026-08-23)

Two screenshots, six defects, and not one of them was a missing rule. Every
single one was a rule this repo already holds, applied inside a scope that could
not see the thing it needed to see. Full UI write-up in `docs/ui-playbook.md`
("Two containers, one `gap`" and "The same row, rendered by two different
components"); the pattern is the point here.

| defect | the rule | the scope it could not see |
|---|---|---|
| comp prompt inset 32 while every card sat at 16 | don't add a margin inside a padded container | the PARENT's padding |
| two bordered cards touching | a card owns its own bottom margin | the sibling's margins |
| "Price seems off?" under a pending comp prompt | one decision at a time | the other block asking about the same number |
| "Grade" rendered twice | *a kind of row has ONE renderer* | the PARENT's label |
| Category read `yugioh` | *never show a raw slug* | the OTHER branch of the same ternary |
| `value_choice` about to render as a row | plumbing is not a fact | the renderer on the far side of the write |

**A `gap` is invisible from inside a child — and so is a LABEL.** That is the
generalisation worth keeping: whatever a parent owns, the child must be TOLD.
`reservedLabels` is passed down, derived from the same `isGradingEligible`
expression that labels the parent's own row rather than restated as a literal.

### Three things measurement changed, that reasoning would have got wrong

1. **`attrs.grade` is on ZERO of 148 prod rows.** The real grade is in
   `items.condition` (`PSA 9`, `BGS 10`). The duplicate row was
   `editableEntries` synthesising the category field list — a placeholder for a
   key nothing writes. Suppressing it *looks* identical either way; only the
   count says whether it hides data.
2. **Two "internal-looking" keys are real facts.** All 22 keys live in prod
   `attrs` were read before the blocklist was drawn. `item_type` (= "Merch")
   and `sealed` stay; `value_choice`, `intake_timestamp`, `source` go. A
   name-based guess would have hidden both real ones —
   `learning_keyword_filters_need_per_category_false_positive_audit`, again.
3. **The obvious category fix was wrong.** `editableCategory` holds a SLUG when
   seeded from the row and a display NAME straight after a pick, and
   `formatCategoryName` is **not idempotent** — `'Yu-Gi-Oh!'` → `'Yu Gi Oh!'`.
   `categoryDisplayName` discriminates on `CATEGORY_NAME_TO_SLUG`, the same map
   `updateItem` normalises through. The test pins the mangling as well, so if
   that ever stops being true the wrapper is redundant and should go.

### The rules had no way to fail, so they were not rules

Row-building is now a pure `buildAttributeRows` with
`__tests__/components/attributeRows.test.ts` — the FIRST test this component has
ever had, covering the brand suppression and label dedupe shipped the day before
as well. Two things it caught:

- **The a11y label was recomputed from the key**, ignoring every disambiguation
  the builder applied: a row displaying "Grade (captured)" or "Set Name"
  announced plain "Grade" / "Set". The two rows the dedupe exists to separate
  were identical to the one user who cannot see them side by side.
- **The tests passed on first write, which proves nothing.** They now carry the
  counter-case — with `reservedLabels` omitted, the duplicate "Grade" must come
  BACK. Without it, a `grade` row that was never synthesised at all would make
  the rule a no-op wearing a green tick.

⚠️ **None of this is on a device.** Both screenshots were build 152 (submitted
2026-08-22), so every fix from 08-23 is committed and has never been built.
Reading a screenshot as evidence about the current code is how a fixed defect
gets "fixed" twice.

## A codec fix broke every caller it was meant to serve (2026-08-23)

Reported from a screenshot: the item screen rendered **raw JSON** where brand,
rarity and set code belong, with `0` and `1` as the labels.

`app/db.py` registers a jsonb codec with `encoder=json.dumps` — added to fix the
DECODE side, where jsonb columns were coming back as `str`. It silently broke
every caller that had already serialised its own payload, and ~25 of them had:

```python
await conn.execute("... SET attrs = attrs || $3::jsonb", ..., json.dumps(merged))
```

**Proven against the real pool config rather than reasoned about** — and the
cast makes no difference, which is the part that misleads:

| bind | result |
|---|---|
| `dict` + `$1::jsonb` | **object** |
| `json.dumps(dict)` + `$1::jsonb` | **string** |
| `dict` + bare `$1` | object |
| `json.dumps(dict)` + bare `$1` | **string** |

Then jsonb `||` MERGES two objects but CONCATENATES otherwise — also proven, on
prod:

```
'{"a":1}'::jsonb || '{"b":2}'::jsonb           -> {"a": 1, "b": 2}
'{"a":1}'::jsonb || to_jsonb('{"b": 2}'::text) -> [{"a": 1}, "{\"b\": 2}"]
```

So **the first double-encoded write turns an object column into an ARRAY**, and
every write after it appends. `items.attrs` reached
`[{...}, "{\"set_code\": \"\"}", "{\"value_choice\": \"mine\"}"]`.

**The display was the least of it.** `attrs->>'value_choice'` stopped resolving,
so the "keep my value, not the model's" choice — built 2026-08-19 specifically
so a member can outrank the catalogue — was silently not honoured for anyone who
used it after their first attribute edit. A dead feature with no error, again.

### The sweep is the point, not the fix

Enumerated over jsonb columns in `public` by generating the query from
`information_schema` rather than guessing which tables to check:

⚠️ **This sweep was INCOMPLETE, and said so nowhere.** Re-run properly that
evening it turned up a **seventh** column — `user_feedback_events_v1.value_json`,
one double-encoded row from 2026-08-17. See "A sweep that stops early looks
exactly like a sweep that found nothing" below.

| column | rows not an object | last write |
|---|---|---|
| `mandate_deals.policy_reasons` | 526 | **2026-08-23 03:39** |
| `supply_snapshots.metadata` | 248 | — |
| `market_hits.features_json` | 40 | 2026-08-22 |
| `alert_trigger_history.trigger_value` | 5 | 2026-08-19 |
| `quick_predictions.raw` | 2 | — |
| `items.attrs` | 2 (arrays) | 2026-08-22 |

All live, all still being written. Fixed at the chokepoint — CLAUDE.md's own
*"fix the chokepoint, not the callers"* — because 25 call sites is 25 chances to
miss one, and passing a pre-serialised string to a jsonb param is the obvious
thing to write and was correct before the codec existed.

⚠️ **The corrupted ROWS outlive the fix.** The client now flattens an
array-shaped `attrs` back into one object (empty values never overwrite real
ones, so `set_code: "gym1"` survives the `""` appended over it).

### The repair — done, and reversible by construction

All six columns repaired in prod, **823 originals copied into
`public.jsonb_double_encode_backup_20260823` BEFORE the update**, so every row
is restorable. Re-swept afterwards:

| column | shape now |
|---|---|
| `items.attrs` | object (102) |
| `mandate_deals.policy_reasons` | **array** (526) — correct; it *is* a list |
| `supply_snapshots.metadata` | object (16,188) |
| `market_hits.features_json` | object (2,686,508) |
| `alert_trigger_history.trigger_value` | object (108) |
| `quick_predictions.raw` | object (4) |

Two things made it safe rather than lucky:

- **A dry run inside a rolled-back transaction, reconciled by COUNT.** Every
  table's repaired count had to equal its healthy count plus its corrupted
  count (`market_hits`: 2,686,468 + 40 = 2,686,508). A repair that silently
  drops rows reports success exactly like one that does not.
- **`mandate_deals.policy_reasons` had ZERO healthy rows** — the column has
  never held a correct value, so there was no shape to repair *towards*. Its
  reader (`purchase_router.py`) carries a defensive `isinstance(str)` parse, so
  both the old and repaired shapes work and the repair could not break it.
  Checked the reader before repairing into a break.

⚠️ **The repair decays until the encoder is DEPLOYED.** Prod ran
`encoder=json.dumps` for the whole repair window — the fix was committed, not
shipped. `mandate_deals` writes daily, so the first write after the repair
re-corrupts what was just fixed. Hash-diffing the whole `server/` tree against
`/opt/collectors/server/` (not `HEAD~1`, which by then pointed at an app-only
commit) found **nine** drifted files, not one.

### Two defects the audit caught in my own fix

1. **The first encoder passed through anything that PARSED.** Python and
   Postgres disagree: `json.loads("NaN")` succeeds, `SELECT 'NaN'::jsonb` is a
   hard ERROR — so a member typing "NaN" into any field landing in a jsonb bag
   would have 500'd, and a genuine `"123"` would have been stored as the number
   123. Only a dict or list is passed through now; every scalar falls to
   `json.dumps`.
2. **A label dedupe that silently deleted data.** `set_name` and `set` both
   render as "Set" (docs/TAXONOMY.md's two vocabularies, one layer down), so
   duplicates were collapsed — but on a real row BOTH carried values (`"BLAR"`
   and `"jdhd"`) and one vanished. Now only an EMPTY duplicate is dropped.
   **Found by running it against the two ACTUAL corrupted rows instead of a
   fixture** — the invented fixture had one empty side and could not have shown
   it.

### Why 3,829 tests could not see any of this

Every test asserts the **parameter handed to a mocked connection**, never what
that parameter becomes once the codec runs. Both halves were tested; the codec
seam between them was not — the same shape as the CSV-import 401, where
`_auth_override()` injected the very thing the client failed to send.
`server/tests/test_jsonb_encoder.py` targets the codec itself, and 3 of its 3
key assertions fail against the old encoder.

⚠️ **A `git stash` with nothing to stash pops someone else's stash.** Reaching
for a test baseline, `git stash` found no local changes (everything was already
committed) and created nothing — so `git stash pop` restored a **four-month-old
stash**, leaving 16 files with conflict markers. Use a **worktree** at the
comparison commit instead: `git worktree add /tmp/baseline <sha>`. Recovery was
clean only because every modified file was verifiably explained by that stash.

## The app was rate-limiting itself (2026-08-23)

Reported as *"where to buy needs the links for the affiliate links"* — a card on
the catalogue item screen reading **"No marketplaces available for this item."**
The obvious reading was the known one: all 16 affiliate IDs are empty on EC2, so
`build_affiliate_url` returns URLs untagged. That was a red herring; untagged
links still RENDER.

**The prod log had the device's own request.** Not a reconstruction of it — the
line itself:

```
GET /marketplace/affiliate-links?query=Hero%20Mask%20%5BLC02%5D%20(1st%20Edition)
    &category=yugioh&limit=8&region=europe&item_value_eur=366   → 429
```

Run from the server, the same query answers **200 with four marketplaces**. The
links were never missing. The app had spent its own rate limit, the fetch threw,
and the `catch` left `links` at `[]` — which the card renders as a confident
factual claim about the market.

**`RATE_LIMIT_RPM` is GLOBAL and per-path.** `rate_limit_middleware` applies one
per-IP bucket to **every** route, so a single member browsing spends it on
`/billing/status`, `/portfolio/overview`, `/p2p/offers` and everything else at
once. Measured before changing anything:

| measurement | value |
|---|---|
| rate-limit rejections in a day | **797**, across 4 IPs |
| 429s on `/billing/status` alone | **45** — the call that decides what a paying member gets |
| peak for one device simply opening screens | **~55 req/min** against a limit of **60** |

So normal use sat on the edge of the limit and any burst crossed it. 60 is a
figure for an anonymous public API; this serves a mobile client that fans out
dozens of calls per screen, and the bucket is shared by every device behind one
NAT. Raised to **600**. The expensive endpoints keep their own scoped
`per_user_rate_limit` / `per_ip_rate_limit` guards — those are what actually
protect them, and this middleware had been tuned as though it were the only one.

**Three lessons, in order of how much time each would have saved:**

1. **Read the status code before re-reading the query.** Every layer below the
   429 was healthy and would have survived any amount of inspection. An empty
   list on screen is a claim about the RESPONSE, and the response was never
   fetched.
2. **A shared budget is invisible at every call site.** Nothing in
   `affiliate_links_router.py` mentions the global limiter; its own scoped limit
   (100/min) never fired. The endpoint that gets throttled is not the endpoint
   that spent the budget.
3. **`[]` from a `catch` is the house bug in a new place** —
   `learning_empty_answer_rendered_as_zero`, which
   `docs/ui-playbook.md` already records for `market-movers.tsx`. The card now
   distinguishes could-not-ask (`null`) from asked-and-got-nothing (`[]`), with
   a retry.

⚠️ **The FE fix does not restore the links.** It changes what a failure SAYS.
Only the prod `.env` change plus a restart brings the marketplaces back — and
the affiliate IDs remain a separate, still-open blocker
(`project_affiliate_ids_unconfigured`): even with links rendering, every buy tap
earns EUR 0 until an eBay Partner Network campaign ID is set.

**All nine `ExecStartPre` stages were run manually before the restart** — deps,
env, worker imports, schema drift, RLS, models, router drift, schema lock, RPC
lock — because a stale lock only bites on the NEXT restart and prod once sat ~1h
unable to come back up for exactly that reason. All nine pass.

## A loop, a duplicate, and an API that was never deployed (2026-08-22)

**The display-name loop.** Settings' first row pushes `/users/{me}`; a member
with no display name has no `user_public_profile_v1` row, so that screen offers
"Add a display name" — which pushed bare `/settings`, whose first row pushes
`/users/{me}`. Reported as *"you just end in a loop back to settings"*. It was
worse than a loop: breaking out still left you on a screen where the field is
behind an Edit button you have to find. Now `/settings?editProfile=1`, read by
the ROUTE FILE so `check-params` can resolve the contract, opening the editor
once via a ref.

**Two Sell buttons.** Sell moved into the item screen's top row on 08-21 and
`SellOnSparrowSection` stayed at the bottom — and they disagreed: the section
expanded an inline create form while the top row opens `sell/new`, the full flow
with the 8-photo gallery. Removed, with the stale comment in `sell/pick.tsx`
that still described it.

**⚠️ The gallery API was never deployed.** `p2p_listing_router.py` hashed
differently local vs remote, so build 151 — which contains the client gallery —
would have shown ONE image regardless of the data. Found only because seeding
demo data prompted an end-to-end check. **A feature is not shipped when the app
half ships**; hash-diff the server on any change that spans both.

**`item_images.label` is CHECK-constrained** to
front|back|detail|box|certificate|damage|other. A seed using a marker string was
rejected outright, and that rejection exposed the uploader sending `undefined`
for photos 2..8 — accepted, because NULL satisfies a CHECK, but discarding a
field the schema defines. A constraint you meet by accident is one you will
break later.

**The splash wordmark** is baked by `scripts/make_splash.py` from the real icon
and the exact `Roboto_900Black` file `fonts.black` resolves to. `splash.png` had
been byte-identical to `icon.png` and referenced by nothing.

### The gate fix that was worse than the bug

`check-route-param-handoff` bounds a params body with `\n\s*\}`, so a
SINGLE-LINE `params: { … }` runs on and swallows the JSX below — it reported a
correct push as sending a phantom `color` from `{ color: colors.accentText }`
four lines down.

The obvious repair — `[^{}]*`, stop at the first closing brace — made it PASS
and silently cut its coverage from **46 params across 23 sites to 27 across 18**,
because any nested brace or `${}` truncates the object. It was only caught by
comparing the summary counts before and after.

**A gate that under-reports is worse than one that over-reports**, so the gate
was reverted untouched and the call site written multi-line like the other 23.
When a gate blocks you, changing the gate is the last resort, and the test of
any gate edit is that its COVERAGE NUMBERS do not fall.

## The events feed is ~95 rows, and the newsletter had no newsletters (2026-08-22)

Measured before fixing anything. 2,859 events, **108 upcoming** — the feature is
effectively SeatGeek plus a little Ticketmaster.

**`limitless_tcg` is 70% of the table and has never produced an upcoming row.**
Its docstring says "only upcoming tournaments (date >= now)"; the code said "not
more than 3 days stale" and never required the future. All 1,986 rows were
already past at insert — average −12.3 hours — against +62 days for
ticketmaster. Fixing the filter admits NOTHING, which is the honest outcome:
Limitless is a results feed, and `?upcoming=`, `?status=`, `?type=` all return
0 future rows. Left wired with a note to delete it if it writes nothing for a
month.

**The newsletter source had no newsletters.** 949 messages in that inbox since
April, not one from a publisher — the recent ones are GitHub CI notifications
and Google/Vercel service mail. "Site Navigation" and "Performance Cookies" are
what a newsletter parser produces when pointed at service email. The extractor
IS weak, and it was also fed nothing to extract; both are true and only the
first was recorded before today. That mailbox is also **full**, so subscribing
publishers to it does nothing until cleared.

**The replacement is a GATE, not a model.** `newsletter_llm_extract.py` asks the
model to POINT AT text and then verifies deterministically that the text exists:
evidence verbatim in the email, title in the email, and — added by auditing the
gate against itself — the YEAR of `starts_at` present in the evidence span. That
last one was found by constructing the case: real title, verbatim evidence,
invented date → accepted with zero reasons. An LLM's failure mode is the inverse
of a regex's, so none of `event_quality`'s existing penalties would have caught
it. Nothing is wired in; the quarantine stays on until a dry run is measured.

## What actually catches a defect I just wrote (2026-08-22)

A post-completion audit now runs after every change, and it keeps finding real
defects — about **15 across 2026-08-21/22**. What is worth recording is not the
bugs but WHICH method found each, because it is never the obvious one.

| detector | caught | blind to |
|---|---|---|
| `tsc` | a narrowed type, a deleted style with two other callers, dead props, a hook spliced into an effect (surfacing as "cannot find name") | dead code, unreachable branches, logic, empty renders |
| a script / grep | orphaned styles, banned type sizes, invalid Ionicons names | anything it was not written to ask |
| **reading the NEIGHBOURING file** | a catch clause that only caught `PostgresError`, two prices in two currencies on one card, an outline button whose base style had no `borderWidth` | — |
| measuring the data (SQL) | a "signal" that was the untouched default on 13 of 20 rows | — |
| **re-reading my own new lines** | **≈ nothing** | — |

The reason is simple: new lines look right to the person who just wrote them
believing they were right. **The defect is almost always in the SEAM** — what
the caller catches, what the neighbouring row formats with, what the base style
already sets, what the enclosing block already branches on.

So the order that works:

1. **Read the caller and the neighbour, not the diff.**
2. **Run `tsc` after every structural edit**, not once at the end. It catches
   every contract break and no semantic ones — that is exactly its job.
3. **Count, don't skim.** "How many guards in this block" found a twenty-line
   unreachable branch that `tsc` accepts, because dead JSX is legal.
4. **Wrapping an existing block in a condition?** Grep that block for the same
   condition — if it is already there, a branch just died.
5. **Widening a gate for a new child?** Copy that child's condition; do not
   paraphrase it. Paraphrasing is how a bordered, totally empty card shipped.

⚠️ **A checker written during the audit is itself unaudited**, and mine were
wrong twice in two days: a dead-style script used `//.*` with `re.S`, so
stripping line comments ate the rest of every file and it reported 13 dead
styles in a file with one; and a grep for `accessibilityRole="tabbar"` (fatal on
Android) returned two hits that were both comments *warning against it*. Both
would have produced a confident wrong conclusion. Sanity-check a new checker
against a case whose answer you already know — the rule this repo already
applies to its gates.

## Current state (2026-08-21)

### The watchdog was wrong about itself, twice

Worked the daily report end to end. Of 8 HIGH findings, **five were false**: the
coverage canary treated `sold_now > 0` as proof of a crosswalk fault, so
one_piece_tcg — ONE sold comp against 7,675 catalogue rows — was told "the data
is there and the catalogue cannot reach it". Distinct items with a comp vs items
priced: funko 60/60, retro_games 58/58, nintendo_merch 32/32, retro_handhelds
4/4, one_piece 1/1. Every comp that arrived was already used. It now counts
comps landing on catalogue rows that stay UNPRICED, which is the only thing that
claim can mean. `bugs_high` 8 → 2, and lorcana (2,671 orphaned) correctly stays.

**And the digest deleted itself on the days it mattered most.**
`send_ops_alert(body[:3800])` cut MARKUP on a character boundary; landing inside
`<code>` made Telegram reject the whole message, silently. The longer the
report, the likelier the cut splits a tag — delivery failed in proportion to how
much there was to say. Fixed at both ends, pinned by a test that fails against
the old slice.

Two real rejected writes, both invisible in `bake.log`: `user_settings` has no
`settings_json` column (it is `region`) so regional routing was silently off for
everyone, and `market_hits.shipping` is DOUBLE PRECISION and was bound
`::jsonb`. Both proven in both directions against prod, in rolled-back
transactions.

**Logflare answers long windows PARTIALLY.** 6h → 15 errors, 24h → 15, 72h → 14
— fewer than its own subset. `--hours 168` was documented and produced a
confidently wrong report. Use ≤24h.

### The nightly ingest runs a branch nobody was looking at

GitHub cron runs the repo DEFAULT branch — `feature/all-enhancements`, 119
commits behind — and `origin/main` **is deleted**. The within-batch dedupe had
been on a working branch since 2026-07-29 and never reached the pipeline that
runs, losing up to 3,000 catalogue rows a night. Attribution came from client IP
in `edge_logs`: `4.149.x.x` is Azure (an Actions runner), not EC2
(`51.21.210.195`). PR #4.

### The paywall was never our code

`docs/MONETIZATION.md` carried "not checkable from here" for a week. The answer
was a screenshot: **the Apple account has no Paid Applications Agreement** —
only Free Apps. Until it exists Apple returns zero StoreKit products in every
environment, which is the whole of `reason=no-offering`. RevenueCat, the inlined
key and the `store` profile were all verified correct throughout. Agreements are
not in the ASC API at all — do not try to script it.

**The diagnostic that was supposed to settle this could not be read.**
`logger.error` wrote to console and nowhere else: Sentry was initialised the
whole time and never received a line, and `getRecentLogs()` had no consumer —
its own comment named a "diagnostics screen" that did not exist. Now Settings →
Diagnostics (works offline, which matters when the network is what is broken)
plus a Sentry sink. ⚠️ That sink is re-entrant BY CONSTRUCTION — Sentry's
`beforeSend` and `beforeBreadcrumb` both call `logger.error` from their catch
blocks — so it needs the `inSink` latch, proven by removing it and watching the
stack blow.

### Titles were not in the same font, on one platform

A native-stack `headerTitle` is drawn by UIKit, not by an RN `<Text>`, so the
`Text.render` monkey-patch that puts Roboto on everything else never reached
it — and there was no `headerTitleStyle` anywhere. 26 screens rendered San
Francisco over a Roboto body on iOS. Invisible on Android, where the system font
IS Roboto. One line in the global `screenOptions`. **Still open: 25 of those 26
titles are hardcoded English** — `check:i18n-parity` cannot see them because the
failure is a missing KEY, not a missing translation.

### "Find collectors" opened a listings feed

Both `app/inbox.tsx` and `FriendsFollowSection` pushed the marketplace, the
second under a comment asserting the collector search lived there. It does not —
that tab is a listings feed. This is the 2026-08-10 bug in a second place; that
one was the Search TAB redirecting to the marketplace, fixed by making the tab
real, and these survived because the fix looked at the tab and never asked who
ELSE pushed to it expecting a search.

### The marketplace takes 8 photos, and the ones it had were invisible

`item_images` supported many all along; `sell/new.tsx` held one `photoUri`.
Now 8, uploaded SEQUENTIALLY because `position` is assigned by append order and
that order is the buyer's gallery order. `ListingOut.image_urls` + a paged
swipeable gallery.

**The bug underneath was live:** `POST /items/{id}/images` does not write
`items.image_url`, and both listing queries read only
`COALESCE(i.image_url, ci.image_url)` — so a seller's uploaded photo sat in
`item_images` while the listing showed the CATALOGUE shot labelled "Stock
photo". Nobody noticed because that table has 0 rows.

### "Improve the UI" was a `.select()`, not a StyleSheet

The watchlist card showed a target and never a current price — the one question
the screen exists to answer. `watchlist_items` carries `last_market_price`,
`price_trend`, `image_url` and `predicted_value`; the provider selected none of
them and the TS type declared two that were referenced nowhere. Every style on
that card already followed the playbook.

Then, asked whether it needed decluttering: the priority stripe added that
morning was the DEFAULT on 13 of 20 rows — a signal identical on two thirds of a
list is decoration. It now marks only a priority someone chose.

**Measure the data before restyling the thing that renders it.** `image_url` is
0 of 20 populated, so a thumbnail would give every card a placeholder; a
tappable card was rejected because only 7 of 20 rows carry an `item_id`.

## Current state (2026-08-20)

### A screen full of things that were built and never connected

Five separate features on three screens were complete, correct and reachable
from nowhere — the house failure mode, five instances in one day.

- **The marketplace share button did nothing.** `app/listings.tsx` imported
  `ShareToChatSheet`, held `shareFor` state and computed a `sharePayload`
  memo — and never put the element in the tree. eslint said so, as a WARNING,
  in a repo carrying dozens; `verify:prebuild` does not run lint. New gate:
  **`npm run check:unrendered`** (`scripts/check-unrendered-components.mjs`),
  wired into `verify:prebuild` and proven to fail on the pre-fix file. It found
  **7 more** stale component imports on its first run.
  The gate was WRONG IN BOTH DIRECTIONS before it was right: a component named
  only in a `//` comment counted as used (hiding the import), and a
  deliberately commented-out `// import { SellTimingBadge }` counted as an
  import (reporting a phantom). Strip comments first — a comment is neither a
  reference nor a declaration.
- **Sharing to a DM delivered dead text.** RN does not linkify inside `<Text>`,
  so a shared listing arrived as characters the recipient could read and not
  follow. `src/lib/linkify.ts` + a `MessageBody` in the thread screen; our own
  https urls route IN-APP via `inAppListingHref`, everything else to the OS.
- **`GET /p2p/offers/{offer_id}` is not deployed.** "Couldn't load this trade"
  is not the network: the list returns 200 and the detail 404s in **2.5ms**.
  The box (`Aug 19 18:53`) has `/offers` and `/offers/{offer_id}/address` and
  no `/offers/{offer_id}` — md5 `6b029…` vs repo `12e7b…`. The repo also
  defined that handler TWICE, byte-identical; FastAPI keeps the first and the
  second shipped as dead code. Duplicate removed; **the deploy is still owed**.
- **Nothing could reach your own profile.** Every `/users/[userId]` edge points
  at somebody else, so the one screen showing your trade rating was the one you
  could not open and `TradeReputationSection`'s `isSelf` branch had never
  rendered. Now: an avatar in the header cluster (primary) and Settings →
  Account → View public profile (secondary). Checked against the apps that live
  on ratings — Uber gives DRIVERS one tap and buries the RIDER rating under
  Settings → Privacy → Privacy Center, unfindable enough that CNBC and the
  Washington Post published how-tos; Vinted puts it on the avatar.
- **…and that door led to an error page.** `user_public_profile_v1` ends in
  `WHERE COALESCE(NULLIF(display_name,''), NULLIF(username,'')) IS NOT NULL`,
  so a member who never set a name has **no row** and got "Collector not
  found". Measured on prod: the sim account 0 rows, Lena V. 1. There is now a
  self branch: "Your public profile isn't set up yet" + a route to Settings.
  **Open question:** that same `WHERE` makes an unnamed member invisible in
  search and on leaderboards. Requiring a display name at signup would close it
  upstream.

### Prod was AHEAD of HEAD, and the deploy script would have regressed it

A full md5 sweep of `server/` against `/opt/collectors/server/` (585 local vs
572 remote `.py`, 565 in common) settled a claim I had made from ONE file's
mtime and got wrong: **there is no undeployed server code.** `app/`, `workers/`,
`routes/` and `main.py` are byte-identical. Exactly one non-test file differs —
`pipelines/import_watches.py`, a hand-run importer in no worker registry and no
bake manifest. Everything else differing is `server/tests/*`, which nothing
imports or crons.

**What the sweep DID find:** commit `b422174` registered
`GET /offers/{offer_id}` **twice** — two decorators over two identical
`async def get_offer` bodies. FastAPI keeps the first and never dispatches to
the second. Today's `--dirty` deploy shipped the de-duplicated version, so the
BOX was correct and **HEAD carried the regression** — and
`scripts/deploy_to_ec2.sh` derives its file list from `git diff HEAD~1 HEAD`
when `--files` is omitted, so the next default deploy would have re-introduced
it. Committed as `61e1ff9`; HEAD and the box now hash identically
(`16c8de90…`).

**Residue from the 2026-05-02 misdeploy was still on the box**:
`server/social_router.py` and `server/portfolio_router.py`, rsync'd flat into
the tree root at 15:14/15:19 on Aug 19 and then correctly redeployed into
`app/`. Nothing imports them — but `WorkingDirectory=/opt/collectors/server`
puts that directory on `sys.path`, so one future bare `import social_router`
would have silently bound Aug-19 code. Plus an orphan `schema.lock.json` (Aug 9)
sitting beside the live one the gates actually read. All three tarred to
`/tmp/misdeploy_residue_20260820.tar.gz` and removed; no restart needed, and a
restart would have been pure risk since nothing imported them.

### The submission docs told you to spend money

`docs/APP_STORE_SUBMISSION.md` §1 said `eas build --platform ios --profile
production` — no `--local`. The Expo account is on the **Free** plan, so
following the doc verbatim queues a **billable cloud build**, and the profile
name was wrong too (the shipping scripts use `store`). Corrected to the npm
scripts, with the EAS-remote build-number rule and the
`FINISHED ≠ on TestFlight` warning written into §7 where the submit command is,
rather than left in a memory file.

### One header cluster, and two things hiding behind the reported one

Reported as *"top right on portfolio there's a settings icon, notification icon
and profile icon — this should be the same for every screen."* It was not: four
different clusters across five tabs, and Market and Explore had none at all.
Six files hand-rolled the same row.

One `HeaderActions` now — **bell · bubble · gear** — on all five tabs, on
`ScreenHeader` (15 screens) and on the root stack. The avatar came OFF: three
utilities read as a cluster, four read as a toolbar, and identity is not a
utility. It moved to the first row of Settings, which had been showing a
username and an email and **was not tappable**.

Two defects underneath the reported one:

- **The bell lived on Portfolio only**, because its unread count was fetched by
  `app/(tabs)/index.tsx`. A control whose state lives in a screen ends up
  living only on that screen.
- **The cluster changed shape with your inbox.** `InboxHeaderButton` hid itself
  under `COMMUNITY_GATED` — a DISCOVERY flag, reused for a messaging control,
  which is the reuse `featureFlags.ts` already warns about for
  `GAMIFICATION_UI_ENABLED`. Now `MESSAGING_ENABLED`, on: P2P made chat part of
  the trade loop.

⚠️ **Moving a fetch into a shared component multiplies it.** The badge went
from one request per session to one per screen with a header. Cached at module
scope, 60s TTL, **keyed by user id** — module scope survives a sign-out, so an
unkeyed cache would put one member's unread count on the next member's badge.

### One fact, rendered three times, is what "messy" means

The item card showed **"Item Details" twice and the same attributes a third
time** as "Card Details":

- `ItemAttributesSection` was mounted inside `ItemDetailsCard` AND standalone
  from `app/item/[id].tsx`, each fed by its **own fetch of the same row**. The
  inner copy was passed `editableCategory` — a display NAME — into
  `getCategoryFields`, which is keyed by SLUG, so it silently lost the
  category's field order and labels (docs/TAXONOMY.md, "Two vocabularies").
- `CategorySpecificSection` re-rendered the same `attrs` keys as 71 hand-rolled
  rows across 25 category blocks. Every one was a duplicate BY CONSTRUCTION:
  the list renders every key, the blocks re-render a hand-picked subset.

Now: one renderer, inside the details card, under the value it describes.
`CategorySpecificSection` keeps only what the list cannot say — badges (Foil,
1st Edition, Vaulted) and controls (size, build progress, auth links). ~640
lines out, two empty blocks deleted, 19 badge-only blocks de-headered.

**The defect that pass introduced, caught by the post-completion audit:** the
19 badge-only wrappers kept `marginTop + paddingTop + borderTopWidth` while
every remaining child was conditional, so a card that was neither foil nor 1st
edition drew a **stray divider over 12pt of nothing**. Spacing that belongs to
a conditional child has to sit ON that child.

### Copy that states a limit comes from the DOC

- **"Item Insights" → "Advanced analytics."** MONETIZATION.md sells exactly one
  line — *"Advanced analytics (price trend, history, market prices)"* — and the
  analytics screen's prompt already said that. The item card had invented a
  product name that appears in no plan, no store listing and no paywall.
- **"Cannot estimate value" → "Not yet priced."** "Cannot" is a claim about our
  ability and reads as permanent; the truth is that no comp has reached that
  row YET. It is also the wording the server already uses for the same absence
  at category level. The test now pins `UNPRICED_LABEL`, not the string.
- **Leaderboard "Documented" → "Completeness."** NOT set completion:
  `documented_count` counts items whose RECORD is filled in (photo +
  condition/grade + purchase price), while `completionPct` elsewhere counts how
  much of a card SET you own. The secondary line says "N of M items" so the
  percentage cannot be read as owning N% of a set.

### Volume is a different problem from comparison

`app/offers.tsx` grouped competing bids ADJACENT on 2026-08-19 and left the
volume alone: ten listings with five bids each was still 50 cards. Groups now
**collapse to one row** — *"DEMO Charizard Base Set Holo · 4 bids · €28 – €50"*
— expanding in place. All four of the spec's load-bearing rules survive; see
P2P_MARKETPLACE_SPEC §"Two gaps".

Two traps in that change, both caught before shipping:

1. **The stale closure.** `renderOffer` is a `useCallback`; without
   `openGroups` in its deps it closes over the set as it was on mount, the tap
   updates state, the list re-renders from a stale renderer, and the group
   appears not to open. eslint's exhaustive-deps found it.
2. **A pushed trade must not arrive collapsed.** `deepLinkOfferId` highlights
   the card a notification points at; if that bid is not its group's head, the
   card it was pointing at would not be rendered at all.

### The profile card, finally

Reported as unchanged after the 2026-08-19 pass — correctly, because that pass
changed the sections INSIDE the card and never touched the card. It opened with
an 80pt accent banner, a 60pt top pad and a ringed 80pt avatar hanging into it,
then centred the name on an axis nothing below it shared. One left-aligned
identity row now, and the stacking went with it: Collects is a **two-column
grid** (six categories in 3 rows, not 6 full-width rows), Achievements and
Bio/Interests stopped being bordered cards, and the two in-card sections that
carried a *screen* gutter inside a *padded card* now inherit the card's edge.

Two data defects were visible in one screenshot of it, both in
`src/data/providers/userProvider.ts`: `display_handle` was mapped into BOTH
`displayName` and `handle`, so every profile printed its name twice, the second
time as "@Lena V."; and `interests: null` rendered through `?? 0` as a
confident **"0 Categories" directly above six of them**.

## Current state (2026-08-19)

### The offers screen, finally walked on a device (2026-08-19)

The simulator turned out to be usable after all — the app is signed in as
`simcheck@sparrowcollect.test` and the dev client loads from Metro, so the
day's JS is testable without waiting for a build. **Seeded a demo trade scene**
(6 listings / 10 offers, every row titled `DEMO …`) because that account had no
offers, which is also why the offers page looked empty and was CORRECT to.

Two bugs no gate could have found:

- **"Del ete".** Four buttons in a `nowrap`, shrink-to-fit action row squeezed
  the last label until the word broke. Shrinking is right for three and wrong
  for four; the fix is fewer buttons. Two moved to the trade screen.
- **A dead sheet created in the same edit.** Removing the "Book shipping"
  button left `SettleUpSheet` on the list with nothing able to open it —
  `setSettleFor` surviving only inside its own `onClose`. The house bug class,
  self-inflicted in one commit.

**`All` is now a compressed scan view** (requested): keeps everything that
helps you judge, drops everything that acts, one line saying "Tap to manage
this trade". 3½ cards where 2 fit. `Buying`/`Selling` keep inline controls.

⚠️ **The `DEMO …` rows are still in prod** — delete with
`DELETE FROM p2p_offers/marketplace_listings/items WHERE listing_title LIKE
'DEMO %'` (and the matching items) once the walkthrough is done.

### Branding sweep + the seller flow, read end to end (2026-08-19)

**Branding: 858 hex literals, 470 legitimate** (the four palettes, 54 category
tints, franchise colours). Three live violations fixed, one correctly left
alone: `Button.tsx`'s `danger` variant hardcodes white on red, and `accentText`
is #000000 in high-contrast dark — the naive fix would put BLACK ON RED.
`npm run check:brand-colors` gates the pattern that actually breaks. It was
wrong first (a ±6-line window went green when the bug was reintroduced under a
comment) — widened, then proven red.

**Seller flow, read rather than assumed.** Listing creation is already lean:
from the collection it needs only a PRICE (the server supplies the title from
the item); from scratch, title + price. `sell/pick` and `sell/new` were both
rebuilt on 2026-08-07/08 after a dead-end report and are in good shape. The
post-bid half is what changed this week (offers → trade screen → settle). **The
real gap is `/sell/dashboard`: it exists, compiles, and nothing navigates to
it** — `check:reachable` names it alongside `/franchise/[id]` and `/twitch`.

### A trade screen, and "does this need me" is not "may I answer this" (2026-08-19)

`/offer/[offerId]` now owns a trade — a five-step ladder (Respond → Pay/Ship →
Add tracking → Confirm → Rate), each marked done / now / later. Reported as
*"pressing a bid goes straight to the item listing… this is not what you need
to edit/manage… it needs to be one seamless flow."* Every capability already
existed; none of them was owned by a screen. See
docs/P2P_MARKETPLACE_SPEC.md §11c.

**The audit an hour later caught the interesting bug.** The Respond step was
gated on `offerNeedsMyAction`, which returns FALSE for a `superseded` bid on
purpose — it drives the badge, and a rival on a listing you already promised is
not urgent. But §1d keeps that bid alive *specifically* so it can be accepted
when the first buyer ghosts, so Accept/Counter/Decline vanished from the trade
screen while the offers list still showed them. **Two screens disagreeing about
what is legal** — the exact failure the "server owns the state machine" rule
prevents, reintroduced by reaching for a helper that answers a DIFFERENT
question.

> "Does this need me?" is about urgency and drives badges.
> "May I answer this?" is about legality and drives controls.
> `superseded` is the only state where they diverge — which is why the mistake
> was easy to make and invisible everywhere else.

Pinned by an assertion that the two predicates must DISAGREE for a superseded
bid. Also fixed: a declined trade rendered step 1 as dimmed "later", and "Add
tracking" dropped the member on a list to hunt for the button (`action=track`
now opens the sheet on arrival, as the rating prompt already did).

**Two follow-ups left open, both written into the spec:** repoint
`_notify_trade`'s deep link to `/offer/{id}` in the deploy AFTER the build
carrying that route ships (§5e's deploy-order trap), and the `price_verdict`
cost on the two count-only callers.

### CSV import had never inserted a row — and four real fixes had missed it (2026-08-19)

`POST /api/imports/collection` is `Depends(get_current_user_id)`.
`app/(tabs)/add.tsx` uploaded with a bare `fetch` sending only
`Accept: application/json`. Probed against prod with exactly the request the
app sends: **HTTP 401 `{"detail":"Authentication required"}`**.

**Why it survived four rounds of repair — this is the part worth keeping.** The
importer had been fixed repeatedly and every fix was real: `734993b` Excel via
openpyxl, `498c063` the canonical 12-column schema, `43e9d8b` unpriceable
imported rows, `33047ee` the paired columns. All four are SERVER-side,
downstream of a request that never arrived. And `test_import_router.py` is
green at 16 tests because TestClient calls the endpoint with
`_auth_override()` — **the suite injects the very user the client fails to
send.** Both halves were tested. The seam between them was not. Identical shape
to the `pct_of_portfolio` bug found the same day.

Fixed by routing through `postMultipart` (bearer + single-flight refresh +
60s upload timeout). **`npm run check:authed-fetch`** now fails any
`fetch(\`${API_BASE}…\`)` without `getAuthHeaders` nearby, allowlist entries
requiring a written reason. Proven red against the original line. It
immediately found a second instance — `src/api/storageApi.ts`, three unauthed
calls to an authed router, invisible only because nothing calls it.

**Then the import was run end to end with a real token** (sim account, rows
deleted afterwards and the deletion verified): 5 rows → 4 inserted, 1 correctly
skipped for a missing name, all four visible to the user's own PostgREST read.
That run exposed the next one: **`estimated_value` was stored RAW while
`purchase_price` was converted.** A 100 USD purchase stored €86.39 correctly; a
200 USD estimate stored 200. `estimated_value` is a EUR column — the value
chain returns it as `value_eur` — and the template offers a `currency` field
beside it. ~16% wrong for USD, ~170x for JPY, straight into the portfolio
total and the leaderboard. Fixed and pinned by 4 tests, proven red first.

### Offers screen, category vocabulary, and a chart that was wrong by 100x (2026-08-19, later)

**A unit mismatch at a SEAM, wrong by a factor of 100, on a chart that had just
been proven correct.** `/analytics/portfolio/category-breakdown` returns
`pct_of_portfolio` as a FRACTION (`round(val / total_value, 4)`, its own server
test pins `== 0.625`). Home assigned it straight into `percentage`, which the
section renders both as `.toFixed(0)}%` and as a bar `width: ${percentage}%`.
Measured on prod: pokemon at **51.6%** of the portfolio drew **"1%"**,
one_piece_tcg at 48.4% drew **"0%"**, and every bar collapsed to its 2% floor.

Both sides were self-consistent and both were tested; only the join was wrong,
so no test on either side could see it. The mapper moved to
`src/lib/categoryBreakdown.ts` specifically so the seam has one.
**`npm run check:percent-units`** now classifies every server-side ratio field
and requires each client read of a fraction to scale it — the same suffix means
BOTH units across this API (`change_1d_pct` and `change_7d_pct` sit in the same
router with different units). No second live instance; `gain_pct`, `error_pct`,
`mae_pct` and the whole category deep-dive have **no client consumer at all**.

**Two vocabularies for one column.** `items.category` stores a SLUG; every
picker is built from display NAMES. Reading: seven surfaces printed the raw
slug, so a Magic card's badge said *"mtg"*. Writing: `updateItem` wrote the
picker's display name verbatim into the slug column, which would have made that
item vanish from its own category page while still looking correct on its own
screen. Prod measured first — 9 values, all slugs, 0 display names, so latent
rather than live. Normalised at the single write chokepoint. See docs/TAXONOMY.md.

**Offers screen, second pass** (docs/P2P_MARKETPLACE_SPEC.md §11b): competing
bids grouped, rival bids marked `superseded` (§1d keeps them ALIVE on purpose —
accept is an agreement, not a lock — they just stop claiming YOUR MOVE), a
silent 50-row cap admitted, closed trades collapsed to reference rows,
staleness instead of a countdown on a deadline we do not enforce, counters
capped at 5, swipe-to-decline, and "N bids need you" on Home.

**A category page now shows YOUR items** (`YourItemsRail`), reversing part of
the museum redesign. `getCategoryStore`'s items query — running on every
category open since 2026-08-11 with nothing rendering it, and a mapper
hardcoding `price: 0` — was deleted rather than reused.

### ⛔ Check your own new code BEFORE calling it done (2026-08-19)

Asked for after an audit found **three bugs in code written the same hour**, one
already deployed. Five real defects landed that day and **not one was caught
while writing** — gates or an explicit audit caught them all. The cause is a
single habit:

> The happy path is verified against data that CANNOT DISCRIMINATE.

| defect | why the check passed |
|---|---|
| `ORDER BY documented_pct, documented_count DESC` — DESC binds to the LAST column, so the percentage sorted ASCENDING and the least-documented member ranked #1 | every member was at 0%; everything tied, so direction was unobservable |
| `Math.abs(50.01 - 50) >= 0.01` is **false** — a real one-cent difference never prompted | tested €62 vs €50, nowhere near the boundary |
| `setMetric` inside the effect that lists `metric` as a dep (self-cancelling) | only tears down on a dep change, never on first render |
| stale `attrs` spread into a **merge** endpoint (lost update) | one edit per session looks correct |
| Home would have called a whole portfolio "estimated" when no item carried a provenance | prod data had provenance, so the empty case never rendered |

**The pass to run before writing "done":**

1. Ask *what data would make this look right while being wrong* — uniform,
   empty, all-zero, single-row, exactly-at-the-boundary — then test that.
2. **A sort direction, threshold or comparison cannot be proven on uniform
   data.** A 3-row `VALUES` list against prod costs nothing and settled the
   ranking bug in one query.
3. Money in **cents**, never an epsilon.
4. Read the endpoint before assuming merge vs replace, then send the minimum
   payload.
5. Two literals that must agree is a bug waiting (a page size and the guard
   that reads it) — collapse them.
6. "We don't know" must never render as a claim: no provenance is not "all
   estimated", no comps is not "worth 0".
7. Measure the cost you added (DATA_SCALING_PLAN rule 2) instead of assuming it
   is small.

### Stage 2 closed — one definition of item value

`public.item_value_v1(items)` is now THE chain; `v_item_values_v1` is a thin
wrapper over it and every server surface calls the same function
(`/portfolio/items`, `/portfolio/overview`, category-breakdown, the
leaderboard). The leaderboard expresses market-truth as a FILTER on the
function's own label rather than keeping a truncated copy — so the catalogue
step that went missing on 2026-08-17 cannot go missing again.

Two traps, both load-bearing: **SECURITY DEFINER** (as INVOKER the
`price_predictions` read returns an empty set SILENTLY and every catalogue
price falls back to the member's estimate — proven as the `authenticated` role:
direct read 0 rows, view 7 rows / 3 catalog_model), and **call it via LATERAL**
(`(f(i)).field` is expanded into one call per field).

All four endpoints came back byte-identical. One regression on the way:
the LATERAL was placed between a join condition and its `AND i.category = $1`,
re-parenting the filter onto the lateral's `ON TRUE` — and a LEFT JOIN keeps the
row when its condition fails, so the filter stopped filtering instead of
erroring (item_count 1 → 8). Only the endpoint JSON diff would have caught it.

### E2E: the two chains that had never actually run

`server/tests/e2e_value_provenance.py` (12 checks) and
`server/tests/e2e_grade_reminder.py` (10 checks) — both against prod, both
self-cleaning. They exist because neither chain is reachable from a unit test:
the value view is `auth.uid()`-scoped and reads a table RLS denies to clients,
and `grade_reminder_worker` had **never sent a notification** (prod holds no
trade completed over 24h ago, so every cycle correctly did nothing).

The value E2E failed on its first run and BOTH failures were the test:
`items.canonical_ref` is trigger-derived so setting it directly is silently
overwritten, and asyncpg returns `id` as a UUID object so a string-keyed lookup
missed every row. Details in docs/ARCHITECTURE.md.

### Value provenance — what a number on screen is allowed to claim

`v_item_values_v1` now returns **`value_source`** beside `value_eur` (applied
to prod, schema.lock regenerated, preflight PASS). The app renders it as a chip
on item detail and the items list; the leaderboard ranks on the **market-backed
subset only**. Full detail: docs/ARCHITECTURE.md.

**The finding that drove it: the column names lie.**

| column | name suggests | actual only writer |
|---|---|---|
| `quick_predictions` | QuickScan output | `write_quick_valuation` — the daily catalogue rollup. **Comp-backed** |
| `items.predicted_price_eur` | model output | add-manual's **"Estimated value" text field** |

So the chain's link 3 was a hand-typed guess ranked ABOVE `estimated_value`,
where every other writer puts one — a later correction could be outranked by
the original and never show. `estimated_value` is now THE user-estimate column;
`predicted_price_eur` is read-only legacy.

It is now READ by four surfaces, each with its own rule: the chip labels it,
the **leaderboard ranks on the market-backed subset only**, **analytics splits
into three numbers** (paid / market / estimated), and **Home includes the
estimate and says how much of the headline it is**. An unknown source counts as
an estimate everywhere — the side that under-claims.

**A member may override the model, and it actually wins.** Manual add used to
replace their number silently (save, then `revalueItem` writes a catalogue
valuation into the TOP of the chain). The item screen now asks, after the save,
and `attrs.value_choice = 'mine'` sits ABOVE the model in the view — otherwise
"keep mine" could not be honoured at all, since both prediction tables outrank
`estimated_value` and the catalogue model is global data, not the member's row.
Applied to prod; proven byte-identical for anyone who has not chosen, and
proven to flip (74.80 catalog_model → 12.34 user_estimate → restored) for one
who has.

Three write-path defects fixed with it: `updateItem` accepted `price` and
mapped it to nothing (a trap for the offline queue, which replays queued args
verbatim); `persistQuickscanDraft` posted four fields and dropped the scan's
estimate and condition, so a scanned item saved with no value; and
`app/item/[id].tsx` derived a THIRD value chain that skipped both prediction
tables.


**Trade ratings are now READ somewhere.** Two-sided rating has existed since
Stage 2 (`member_grades`, either party, anchored to a completed offer). What
was missing was every surface that should show it. Full writeup:
`docs/P2P_MARKETPLACE_SPEC.md` §12 and `docs/alerts-and-insights.md`.

Four bugs found while wiring it, **all four instances of classes this file
already names** — which is the point of naming them.

| What | Class | Where |
|---|---|---|
| Dossier valuation + 90-day chart empty for EVERY item, every user — bound the **bare** `canonical_key` against the namespaced `item_ref` | identifier formats (below) | `dossier_agent.py` |
| Dossier printed **no grade for a graded item** — read `attrs["grade"]`, which no writer writes | reader/writer never met | `dossier_agent.py` |
| Every server-sent `deep_link` is RELATIVE; `new URL()` throws on those into a catch that logs and returns — **6 senders, all with a dead tap** | dead-by-wiring | `usePushNotifications.ts` |
| `seller_collection_size` counted **archived** items, crediting a seller for what they had already sold | archived-as-owned | `p2p_listing_router.py` |

The first two are in `dossier_pdf`, a **Pro** feature. The third is the reverse
of the usual shape: the SEND side was correct and the RECEIVE side dropped it,
so nothing server-side looked wrong and the notification visibly arrived.

**The fourth was found BY a gate that had been blind to the query.** Splitting
the listing SQL around a shared fragment turned one string literal into three,
and `check:archived` reports per literal — the detail query had been passing
only because its `WHERE l.id = $1` made the whole literal read as a by-id
lookup. Keeping gates literal-scoped is what made it visible.

### The server test suite was 31-red, and it was mostly EVIDENCE

31 failures → **7** (3,763 passing). Almost none was a broken product; they
were stale *pins*, and several were pinning behaviour that had been
deliberately changed. **The doc decides, not the test** — "fixing" the code
until the suite went green would have reopened real bugs:

| pinned | truth | if you had believed the test |
|---|---|---|
| free `max_mandates == 3` | **0** since 2026-07-31 | reopens the deep-link bypass and makes the paywall advertise mandates the buyer gets none of |
| pro `advanced_analytics is False` | **True** since 2026-07-28 | sends a paying Pro user to the paywall instead of `/analytics` |
| `/items-export/overview` header `id,title,…` | the 12-col round-trip schema | breaks export → edit → re-import |
| pricecharting is disabled | **re-enabled 2026-07-22** (keyless public-site scrape) | drops the only sold comps retro_games has |
| eBay `sold_comps` parses a Finding response | **stubbed `return []`** since 2026-04-26 | resurrects a revoked API and flaps the breaker shared with Browse |

Two mechanisms worth keeping:

- **`items_export` now pins `EXPORT_COLUMNS == IMPORT_COLUMNS`.** They are two
  lists in two files kept in step by a *comment*; nothing enforced it, so a
  column added to one side would silently make every exported file
  un-importable.
- **A mock that routes on SQL TEXT cannot see which VALUE was bound.** The
  `canonical_ref` fix passed its first mutation test for that reason. The mock
  now records `(sql, args)` and the test asserts the ref — structure could
  never have caught a bare-vs-namespaced key
  (`learning_validate_values_not_just_structure`).

✅ **Parsing dependencies declared (2026-08-19)** — `beautifulsoup4==4.14.3`
and `lxml==5.4.0` in `requirements.txt` + `constraints.txt`, pinned to what is
installed on the box. The note below is kept because the FAILURE SHAPE is the
lesson:

⚠️ **Undeclared parsing dependencies (the original finding).** `booth`, `suruga_ya` and
`yahoo_auctions` `from bs4 import BeautifulSoup` and ask for the **lxml** tree
builder; `requirements.txt` declares **neither** — both arrive transitively via
`crawl4ai`. `suruga_ya` and `yahoo_auctions` are LIVE, and both failure modes
degrade to "0 hits" (bs4 missing → warning + `[]`; lxml missing →
`FeatureNotFound` swallowed by `except Exception`). If that transitive
dependency moves, two sources go quietly dry with nothing red. Declare both,
pinned to what the box already has.

**Not deployed, not device-walked.** The server half needs
`scripts/deploy_to_ec2.sh` + the 9 preflight stages run manually, and the whole
chain — completed trade → push → tap → rate → the number on the tile and the
profile — has not been walked on a device.

## Current state (2026-08-10)

**iOS build 125 is on TestFlight** (uploaded 20:17 CEST, submission
`001c0dc3`). 121 and 123 were built locally and **never submitted** — see
"Submission status is not TestFlight status" below.

Seven fixes landed today; four are instances of classes this file already names.

| What | Class | Where |
|---|---|---|
| Category "average value" counted unpriced items as **EUR 0** | `unknown-as-zero` | `portfolio_router.py` — DEPLOYED |
| Watchlist rendered empty when the read fired before auth | loading-states §2 | `(tabs)/wishlist.tsx` |
| Member-listings rail 401'd before auth — **same class, new code, same day** | loading-states §2 | `(tabs)/marketplace.tsx` |
| XP printed `12.500` on a Dutch phone, `12,500` on a US one | device locale ≠ `user_settings.locale` | `leaderboard.tsx` |
| Unified search reachable from **nowhere** | dead-by-wiring | `(tabs)/search.tsx` |

### An unpriced item is not a zero-euro item (DEPLOYED)

`/portfolio/category-stats` ended its COALESCE chain in `0`, so `AVG` counted
every unpriceable item as a EUR 0 **sample in the denominator**. For the 40+
categories with no sold-comp source (~62k rows at 0% priced) the reported
average collapsed toward zero. `avg_value` is replaced by a **median plus
min/max**; a category with nothing priced returns `null`, not `0.0`, and reads
"not yet priced".

**`check-silent-failures.mjs` did not catch it** — the checker reads JS/TS and
this was SQL inside a Python string. Every new AXIS needs its own sweep; this is
the third time that sentence has been written here.

⚠️ **Build 125 predates the FE half.** It still reads `avg_value`, which the
deployed server no longer returns. `formatPrice` renders `—` for null so it
degrades rather than crashes, but the analytics screen shows "avg —" until the
next build.

### Submission status is not TestFlight status

`eas submit` runs fastlane pilot with `skip_waiting_for_build_processing:true`
and `"groups":[]`, so a submission reads **FINISHED the moment Apple accepts the
bytes** — before processing, and without assigning it to a tester group. For
`--path` submissions of local IPAs, EAS also records **no build number at all**
(`appStoreConnectBuildUpload` is null), and `build:list` only shows cloud
builds. So EAS cannot answer "which build did I last send to Apple?"

Authoritative sources are only App Store Connect and Apple's processing email.
Keep renaming the shipped artifact to `*-uploaded.ipa` — on 2026-08-10 that
filename was the only surviving record that 120, not 121 or 123, was the last
build submitted.

### A feature can be complete, correct, and reachable from nowhere

Distinct from the silent-failure class below, and not caught by any existing
gate. Three found on 2026-08-10:

- **Unified search** (`app/search.tsx`, `GET /search/unified`, trigram index,
  built the day before) — **zero** call sites pushed to `/search`, while
  `(tabs)/search.tsx` redirected to a marketplace screen whose search never
  reads `category_items`. Reported as "rolex daytona is not in the catalogue".
  It was: 12 Daytona rows, 77 Rolexes, 1,416 watches.
- **`WatchlistWidget`** and **`CategoryLeaderboardSection`** — both exported
  from a barrel, both rendered by no screen.

`check-dead-nav.mjs` reports PASS on all of it: it asks whether a router target
**resolves**, never whether anything **reaches** it.

**`npm run check:reachable` now asks the other half** (added 2026-08-12,
`scripts/check-unreachable-screens.mjs`): it builds the push/`Link`/`Redirect`
graph over `app/**` and reports any screen with no inbound edge. Proved against
`app/market-hub.tsx` — restore it with its entry point repointed and the gate
names it. **Advisory (exit 0)** like `audit_orphan_tables.py`, because it
currently reports a real backlog: `/franchise/[id]`, `/sell/dashboard`,
`/sets-to-complete`, `/twitch` are all live screens nothing navigates to. Flip
`--strict` and add it to `verify:prebuild` once that list is empty.

It does **not** catch the second half of the 2026-08-10 finding: a component
exported from a barrel and rendered by no screen is not a route, so nothing in
the route graph sees it. That gap is still open.

**`check:params` resolves a push target to its route FILE.** A one-line
re-export (`export { default } from '../search'`) therefore reads as "that route
reads: (none)". Push to the file that actually calls `useLocalSearchParams`, or
the contract stops being checkable.

## Overview
Sparrow Collect is a collector app for tracking collectibles (Pokemon, MTG, Funko, Warhammer, K-pop, etc.) with AI-powered scanning and valuation. **54 categories**, ~140K curated catalog items, **44 marketplace adapters**.

## Tech Stack
- **Frontend:** Expo SDK 54 (React Native 0.81) with Expo Router, TypeScript
- **Backend:** FastAPI (Python 3.12) with Supabase/PostgreSQL, asyncpg, partitioned monthly
- **ML:** 36 Ridge regression models (log-scale for high-variance categories), OpenAI Vision + heuristic fallback
- **Payments:** RevenueCat (iOS IAP, shipped 2026-05-09); Stripe dormant for future web/Android
- **Theme:** Tiffany Blue (#81D8D0) accent, EUR currency, Roboto font

## Current state (2026-08-09)

- **A completed P2P trade now MOVES THE OBJECT.** `_settle_completed_trade`
  (`p2p_offers_router.py`) retires the seller's item (decrements if they hold
  several), mints the buyer a NEW row — never the seller's, which would hand
  over their `purchase_price` / `purchase_notes` / `cost_basis` — releases the
  soft reservation, and declines + notifies every other live offer. Deployed and
  verified 40/40 by `server/tests/e2e_p2p_stage2.py` against prod.
  - **`for_sale` is NOT written there.** Trigger `trg_sync_item_for_sale`
    recomputes it from the live listing set, scoped to `marketplace_id='sparrow'`.
    A first draft duplicated that rule *without* the scope; a prod census proved
    the trigger already handled it. Two impls of one rule is the bug, not the fix.
  - Archive, not delete: **29 tables FK to `items.id`, mostly ON DELETE CASCADE**
    — including `marketplace_listings`, `price_ground_truths` and
    `verified_sales`. Deleting a sold item would erase the sale and the
    calibration data the completion had just written.
- **`items.archived` is now honoured** — and `/archived` exists so it is
  reversible. Archiving is reachable from a SWIPE, so hiding without a restore
  route would have been a one-way trapdoor. Gate: `npm run check:archived`.
  - Achievement counters (`items_router`, `intake_router`) are deliberately
    exempt: milestones are LIFETIME activity, and archiving is not un-scanning.
  - Aggregates (`data_moat`), the admin dashboard, and listing browse carry
    `archived-exempt:` markers stating why.
  - **The valuation/learning loop is unaffected either way** — it runs off
    `market_hits` and `price_ground_truths` keyed by `item_ref`/`item_id`, and a
    flag flip cascades nowhere.

- **iOS build 121** built locally; **120 is on TestFlight**. Backups kept as
  `builds/sparrow-ios-local-b120-uploaded.ipa` / `-b121.ipa`, because
  `build:ios:local` overwrites `sparrow-ios-local.ipa` in place.
- **`appVersionSource: remote`** — `app.json`'s `ios.buildNumber` (101) is NOT
  what ships. Read `CFBundleVersion` out of the built `.ipa`.
- **Expo Go cannot host this app.** `react-native-purchases` and
  `@sentry/react-native` are hard static imports, so the sim needs a native dev
  build: `SENTRY_DISABLE_AUTO_UPLOAD=true npx expo run:ios --device "iPhone 17"`.
  Without that env var the build dies at the Sentry phase with *"An organization
  ID or slug is required"* — the same reason `eas.json`'s dev profiles set it.
- **DAC7 is inform-only, deliberately.** Counters + notice + a member-facing
  screen exist; there is **no** column anywhere for a TIN, address or IBAN and
  that is a decision, not a gap. `marketplace-terms.tsx` §6, the notice in
  `_dac7_accrue`, and `app/tax-reporting.tsx` must say the same thing — change
  one, change all three. Open (legal, not code): whether registration is
  required with only excluded sellers, and whether the 5% event-ticket fee
  (`terms.tsx:154`, `:173`) pulls events in.

### Earlier (2026-07-25)

- **Active branch:** `feature/micro-interactions-haptics`. iOS build 100 built locally 2026-07-25 (`builds/sparrow-ios-local.ipa`); last on TestFlight was 96.
- **Apple:** Individual enrollment (Team `3DX8FBF7S6`), App ID `6767359453`, bundle `io.sparrowcollect.app`.
- **IAP:** RevenueCat Free + Pro (EUR 4.99/mo, EUR 39.99/yr) + Premium. **All current
  accounts and items are TEST data** (confirmed 2026-07-25) — treat prod data as disposable.
- **Builds are LOCAL ONLY** — `npm run build:ios:local`. Never `eas build` without `--local`.
- **Before any local build:** `npm run verify:prebuild` (tsc + seam tests + live Supabase contract).
- **Android (assessed 2026-07-31):** the app builds and runs on Android — verified on a
  device, no crash. `npm run build:android:local` (.aab for Play) /
  `npm run build:android:apk` (installable, same shipping config). What is missing is
  console setup only: Play enrolment + service account, `EXPO_PUBLIC_REVENUECAT_ANDROID_KEY`,
  FCM. **Run `npm run preflight:android` before any Android build or submit** — it checks
  all of those plus the Android-only code traps below. See `docs/ANDROID_LAUNCH.md`.

### The Android variant of the failure mode below

**The one that is NOT silent — and is launch-blocking.** `accessibilityRole="tabbar"`
is iOS-only; on Android react-native throws `IllegalArgumentException` while creating
the view, a **FATAL EXCEPTION**. One line in `src/components/QuickNavBar.tsx`, mounted
by **38 screens**, so the entire app past the five root tabs died on Android. Two
logged-out launch tests both said "no crash". **Only a real authenticated session
walking real screens found it** — see [[feedback_never_call_app_ready_without_e2e_verify]].
Use `"tablist"` for a tab container; the gate now validates every role value.

Android gaps in this codebase are otherwise all the same shape: **a platform-specific
path that degrades to a no-op instead of an error**, so the app quietly does less on
Android while iOS looks fine and nothing goes red. Found 2026-07-31, all silent:
`SafeAreaView` imported from `react-native` (iOS-only, a plain `View` on Android);
`<Modal>` without `onRequestClose` (back button dead on Android only);
`expo-store-review` never installed under a guarded `require`; the RevenueCat Android
key unset so the paywall could not sell; FCM absent so push tokens always threw.
`scripts/preflight_android.mjs` is the checker — extend it rather than fixing the next
one by hand.

### Production watchdog (added 2026-07-25)

`server/scripts/watchdog.py` — read-only daily report of what users did, what is
healthy, and what is silently failing. Cron `0 9 * * *` (server TZ Europe/Paris)
via `/opt/collectors/scripts/watchdog_daily.sh`, Telegram digest, JSON kept 30
days in `/opt/collectors/logs/`. See `docs/WATCHDOG.md`.

It reads **Supabase Logflare logs** (postgres/edge/auth) via the Management API,
which is the only layer that sees DB rejections and PostgREST failures — the EC2
journal cannot. On its first run it surfaced four production errors that every
app-side audit had missed.

### Partition retention vs `schema.lock.json` (2026-08-02)

`schema.lock.json` no longer locks partition CHILDREN — `regen_schema_lock.py`
filters `c.relispartition`. Children are created by pg_cron on the 25th and
dropped by `partition_drop_worker`; locking them made routine retention look
like schema drift. Before the fix, dropping `market_hits_y2026m07` +
`price_history_y2026m07` (2.9 GB, correctly exported to S3) left
`preflight_schema_lock.py` failing — and that gate **only runs at startup**, so
the API stayed up and the *next* bake restart would have hard-downed it, hours
after the unrelated-looking cause. The partitioned PARENTS are still locked in
full. Full writeup + the verification protocol for a destructive drop:
`docs/DATA_SCALING_PLAN.md` § 10.

**S3 checks against the warehouse bucket must `source /opt/collectors/.env`
first.** The EC2 instance role has no access; the export worker uses env
credentials. A bare `aws`/`boto3` call on the box reports `AccessDenied` and
looks exactly like missing data.

### The failure mode this codebase is prone to

A writer and a reader that were never connected, plus a construct that turns
"not connected" into an empty result instead of an error: a bare
`except: pass`, Pydantic or Zod dropping an undeclared field, a CHECK constraint
narrower than the code, a LEFT JOIN yielding NULL, a `?? 0` default. Nothing
goes red, so a dead feature is indistinguishable from an unused one.

**Enumerate this class mechanically; never triage it by judgment.** The pattern
that made bugs surface late was: fix the reported instance, hand-triage the
rest, declare done — then the user hits the next one. `npm run verify:silent`
(`scripts/check-silent-failures.mjs`) turns each variant into a check:

| class | what it renders |
|---|---|
| `ungated-demo-data` | invented data as the user's real data |
| `capped-aggregate` | a partial number as the whole truth |
| `unchecked-write` | success when the write failed |
| `unknown-as-zero` | "unknown" as "zero" |
| `swallowed-catch` | no trace at all |
| `prod-invisible-log` | a trace stripped from release builds |

**Each new AXIS needs its own sweep — the existing gates are axis-shaped and
report PASS on everything outside their axis** (2026-08-09). Three more classes,
each found by a user report and each previously invisible to every check:

| gate | class it catches | why nothing else saw it |
|---|---|---|
| `npm run check:effects` | an effect that lists a state **it writes** in its own dep array, so React tears it down and its `.then`/`.catch` are disarmed mid-flight | not an unbounded await — the request SUCCEEDS. `app/offers.tsx` carrier picker was dead on every open while the endpoint served 9 carriers to curl |
| `npm run check:params` | a route param pushed but never read by the destination | `check-dead-nav.mjs` contains the string `params` **zero times** — it only asks whether the route file exists. `typedRoutes` is on but types params as `UnknownInputParams`, an OPEN record, so `prefillTitle` on `/add-manual` is legal TS. 5 live dead handoffs |
| `npm run i18n:parity` | a key in `en.json` missing from another locale | `i18n:check` finds UNWRAPPED strings — it polices the code, not the files. `fallbackLng: 'en'` means a missing key renders **English**, silently. en had 597 keys, all 6 others had 424 |
| `npm run check:archived` | a read of `items` that counts **archived** rows as owned | an archived row is a VALID row, so nothing errors. `archived` was written by swipe/bulk archive and respected by 8 VIEWS, but by **no read of the table** — the bulk dialog promised "archived items will be hidden from your active collection" and the next refresh brought them straight back ([[learning_a_written_promise_to_users_is_a_spec]]). 50 reads, all silent |
| `npm run check:reachable` **(advisory)** | a screen with **no inbound navigation edge** — it exists, compiles, resolves, and cannot be arrived at | `check-dead-nav` asks the opposite question and passes forever. The Market hub's three signal modules were unreachable for a day; `/franchise/[id]`, `/sell/dashboard`, `/sets-to-complete` and `/twitch` still are. **Not in `verify:prebuild`** — it reports a backlog, and a blocking gate would wedge every deploy until that backlog is zero (same reasoning as `audit_orphan_tables.py`) |

All except `check:reachable` are wired into `verify:prebuild`, and each was
proven to fail before it was fixed.

**Writing a graph-shaped gate: match the literal, not the call.** Two false
positives had to be killed before `check:reachable` was trustworthy, and both
generalise — an edge inside a **ternary**
(`router.push(cond ? '/purchase' : '/subscription')`) is invisible to any
call-shaped regex, and a **template literal carrying a query**
(`` `/events/x?eventId=${id}` ``) dies on a character class that stops at `?`.
A gate that cries wolf stops being read, which costs more than the bug. `check:params` compares against the target's **declared** params, not
substrings — a substring version passed a genuinely dead `mode: 'watchlist'`
because the word "mode" appears elsewhere in the file.

The first four are at 0 and each was proven to fail before being fixed. Two real
bugs it caught: `fetchPortfolioSeries` returned a fabricated €1200→€2050 curve
ungated in production (its `DEMO_ITEMS` sibling *had* been gated — the fix was
applied to one of three and never swept), and `usePortfolioInsights` summed a
list capped at `limit: 50` to produce the portfolio total.

Intentional swallows carry a `best-effort:` marker stating why, so a decision is
distinguishable from an oversight. Remaining and reported, not hidden: 91
swallowed catches (none touching a backend call) and 181 logging only via
warn/info.

**One logger, not two.** `@/utils/logger` used to strip `warn` while
`@/lib/logger` printed it; 102 files imported one and 44 the other, so whether a
failure survived into a release build depended on which import a file happened
to have. Collapsed to one implementation; every level is retained in a bounded
ring buffer readable via `getRecentLogs()`, so a failure is recoverable even
when it is not printed.

Three advisory audits exist for it — none blocks CI:
- `server/scripts/audit_orphan_tables.py` — tables read by code that nothing writes
- `server/scripts/audit_column_drift.py` — reader/writer on different columns
- `server/scripts/audit_key_overlap.py` — **joins whose two sides share no values**

**When something looks empty, check whether it is REJECTED before assuming it is
unused.** Look at Supabase > Logs > Postgres, not just the app journal.

### Identifier formats — read this before writing a JOIN

The 2026-07-25 incident: every query joining `items.canonical_key =
price_predictions.item_ref` matched zero rows, for every user, for ~4 months.
44 sites in 13 files. Portfolio value, category health, category stats,
timeseries, deep-dives, insights, exports and valuation-on-add were all
silently empty. **Nothing ever errored** — an empty join is a valid result.

| column | format | example |
|---|---|---|
| `items.canonical_key` | **bare** catalog key | `sm10-sm10-101` |
| `category_items.item_key` | **bare** | `sm10-sm10-101` |
| `items.canonical_ref` | **resolved price ref** (trigger-maintained) | `pokemon:sm10-sm10-101` |
| `price_predictions.item_ref` | **namespaced** always (0 bare rows in 1.7M) | `pokemon:sm10-sm10-101` |
| `price_prediction_daily.item_ref` | **namespaced** always | `pokemon:sm10-sm10-101` |
| `market_hits.item_ref` | **namespaced** always | `pokemon:ex8-ex8-13` |
| `purchase_mandates.canonical_ref` | **namespaced**, nullable (2026-08-12) | `pokemon:base1-base1-1` |

Rules:
- Join predictions/market_hits with **`items.canonical_ref`**, never `canonical_key`.
- **A mandate stores ONLY the namespaced form.** `purchase_mandates` joins
  `price_predictions.item_ref` and nothing else, so it needs one column, not the
  bare/namespaced pair `items` carries. The API takes a BARE `canonical_key`
  from the picker and builds the ref from the item's own `category_items` row —
  never from the request body and never from the mandate's `category` field,
  because a ref with the wrong prefix matches zero rows and returns an empty
  join instead of an error. NULL = a free-text mandate, valued by an
  ILIKE-on-query fallback that is deliberately **not** trusted for money:
  `value_summary.deal_savings` counts keyed mandates only.
- Join the catalog with **`items.canonical_key`** — `v_category_summaries_v1`
  depends on the bare form. Do NOT "normalise" canonical_key to namespaced.
- `ItemCreateRequest.canonical_key` documents a namespaced *example* but
  `/catalog/match` returns a bare key. That contradiction caused this bug.
  `canonical_ref` passes an already-namespaced key through without
  double-prefixing, so correcting the writer later is safe.
- Adding a text-key join? Declare it in `audit_key_overlap.py::PAIRS`.
- **No index on `canonical_ref`.** One was added, then dropped: EXPLAIN showed
  the planner seq-scans `items` (already filtered by `user_id`) and drives the
  join through the existing per-partition `price_predictions_*_item_ref_idx`.
  Identical plan and cost with and without it — governance rule 1 in
  `docs/DATA_SCALING_PLAN.md` is "default = refuse to add". Revisit only if a
  plan shows `items` as the expensive side.

### Loading states — the rule for any screen that fetches

Two bugs on 2026-07-25, both presenting as "stuck on a skeleton", both from the
same cause: **supabase-js ships NO per-request timeout.** A query fired while the
session is hydrating does not fail fast — it stalls behind the auth lock.

1. **Every direct Supabase read in a loading-gating path must use
   `withTimeout`** (`src/lib/withTimeout.ts`). chat/category/user/watchlist
   providers already did; `listItems` did not, so a stalled read left
   `isLoading` true forever with no error and nothing in the logs — and
   `logger.warn` is stripped in release builds, so it was invisible on exactly
   the builds where it mattered. Log timeouts with `logger.error`.
2. **Don't fire the first read until auth has hydrated.** Gate on
   `useAuthContext().loading`: `usePaginatedList` takes `enabled`, and
   index.tsx's focus effect returns early. This took cold-start auth-window
   burns from ~46 to 0.
3. **Any gate needs a deadline.** Gating on auth means a wedged session can pin
   the skeleton again by another route — `GATE_MAX_WAIT_MS` (5s) fetches anyway.

`usePaginatedList` enforces 1 and 3 for every caller (items, alerts, events, and
any list screen added later), so this cannot be reintroduced by a new screen.
Pinned by `__tests__/hooks/usePaginatedList.test.ts` — the three cases nobody had
covered were: a promise that never settles, a gate that opens, a gate that never
does. Wired into `verify:prebuild`.

**⚠️ Bounding an AUTH call is not automatically safe.** `withTimeout` is
`Promise.race`: it abandons the inner call without cancelling it. If a timeout
then leads to a SECOND concurrent auth op, two refreshes on one rotating
refresh-token trip Supabase's reuse detection and **revoke the session** — the
multi-week 401 saga ([[project_2026_07_11_auth_401_root_cause_lock]], why the
client uses `lock: processLock`). It is safe only when the bounded call neither
refreshes nor retries, and there is a recovery path. `httpClient.readAccessToken`
and `AuthProvider` follow that pattern; read `docs/AUTH_AND_WEB_DEPLOY.md` before
touching any of it.

**4. The bound now lives on the CLIENT, not the call site** (2026-07-25).
Fixing call sites one at a time did not converge. A hand grep found 49 unbounded
`await supabase`; a mechanical check found **90** — the grep missed multi-line
`await supabase\n  .from(...)`. So `installRequestTimeouts()` in
`src/lib/supabase.ts` wraps `.from()` and `.rpc()`: every PostgREST call is
bounded by construction (15s), including code not yet written.

On timeout it **resolves** with `{ data: null, error: { code: 'TIMEOUT' } }` —
the shape callers already destructure — rather than rejecting, which would trade
silent hangs for unhandled throws. Screens may still set a tighter bound
(`listItems` uses 8s); the client is the backstop that stops "forever", not
"slow".

`auth.*` is deliberately NOT wrapped, for the revocation reason above. Those 18
call sites are listed in `scripts/unbounded-await-allowlist.json`, each with a
written reason. `npm run verify:unbounded` fails if the central bound is removed
or a new unallowlisted auth await appears; both regressions were reintroduced to
prove it bites. Pinned by `__tests__/lib/supabaseTimeout.test.ts`.

**Save paths count too.** `add-manual.tsx` had three unbounded awaits between
`setSaveState("saving")` and anything clearing it, so the button hung forever:
nothing saved, no error, nothing logged. Any await between a spinner going up
and coming down must be bounded.

### The catalog ↔ price crosswalk

Not every category shares a namespace between catalog and predictions. Measured
catalog→price coverage ("can a user's item get a price?"):

| category | rows | priced | how |
|---|---|---|---|
| mtg | 25,407 seed | 98% | same slug both sides, no bridging needed |
| pokemon | 20,236 seed | 99% | same slug both sides |
| yugioh | 58,565 tcgcsv | **100%** | derived from the price source (per-PRINTING) |
| yugioh | 38,312 seed | 88% | via `catalog_price_refs` (per-CARD, approximate) |
| lorcana / digimon / one_piece_tcg | 22,042 tcgcsv | **100%** | derived from the price source |
| ⤷ same, old seed rows | 2,302 seed | 0% | superseded; see the seed/tcgcsv split below |
| lego, watches, whiskey, gunpla, warhammer, … (40+) | ~62,000 | **0%** | **no sold-comp source** — see below |

**The winning move was NOT a crosswalk.** Matching two namespaces was measured
and rejected (name-only was 224-of-226 ambiguous for lorcana; adding set gave
8.2% / 1.3% / 0.0%). Instead `import_tcgcsv.py --catalog` DERIVES catalog rows
from the same products that produce the prices, so
`category || ':' || item_key == price_predictions.item_ref` holds **by
construction** — which is exactly why pokemon/mtg never needed bridging. Runs
daily via `run_once(catalog=True)`, gated to `CATALOG_CATEGORIES`.

`catalog_price_refs` remains for the **seed** yugioh rows only, built by
`pipelines/build_catalog_price_crosswalk.py`. `items.canonical_ref` is resolved
by `trg_items_canonical_ref`, preferring the direct key (printing-exact) and
falling back to the crosswalk.

**Seed vs tcgcsv:** the old `source='seed'` rows still exist alongside the
derived ones and are mostly unpriceable. Do NOT bulk-delete them — 7.6% are
non-card merchandise (figures, Digivices) that tcgcsv cannot cover, and user
items point at seed keys. Deduplicate in the browse query using `source`. An item
linked to a seed key shows €0 even though its tcgcsv twin is priced — that is the
known `Azurite Sea Booster Box` case.

**The 62,000 gap is ONE stubbed function, not a sourcing problem.** The scraper
runs and collects ~74k hits/day for those categories (lego 26,903, warhammer
18,477 …), but `ebay_caller.py:387 sold_comps()` **returns `[]`** pending
migration to the Marketplace Insights API, so everything falls back to the Browse
API = active listings, `is_listing = TRUE`, and `valuation_worker.py:279`
excludes them. A listings→sold haircut is NOT calibratable: only 205 refs have
both, and the observed ratio is backwards (1.32–1.60).

**Accuracy limit — do not present yugioh crosswalk prices as printing-exact.**
The passcode price is per CARD, so every printing of a card shows the SAME
value: a scarce 1st-edition and a common reprint are indistinguishable. Stored
with `method='name_slug'`, `confidence=0.75` so it can be filtered later.
Ambiguous names (8) are skipped, never guessed.

**Rebuilding the crosswalk does NOT refire the trigger** — the builder
re-touches `items` afterwards. If you change `catalog_price_refs` by hand, run
`UPDATE items SET canonical_key = canonical_key WHERE canonical_key IS NOT NULL`.

**Structural checks cannot catch this class.** The table existed, was populated,
the column names matched, the SQL was valid, the endpoint returned 200. Only
comparing the VALUES on each side reveals it — which is all `audit_key_overlap.py`
does. Coverage caveat: even with the correct join only ~13% of predicted refs
are catalog-reachable; TCG categories key predictions by TCGplayer product id
(`lorcana:tcgplayer:702699:normal`) while the catalog uses set-slugs, so
lorcana/digimon/one_piece_tcg sit at 0% until an id crosswalk exists.

## Key Files
- `app/(tabs)/_layout.tsx` - Main tab navigation (5 visible tabs: Home, Items, Add, Events, Marketplace; wishlist + search are hidden routes)
- `app/(tabs)/index.tsx` - Portfolio dashboard with line chart
- `app/(tabs)/items.tsx` - Item list with search/filter, multi-select, bulk operations
- `app/(tabs)/add.tsx` - QuickScan and manual add entry
- `app/quickscan.tsx` - Camera capture flow
- `app/item/[id].tsx` - Item detail with price bands
- `app/analytics.tsx` - Portfolio insights dashboard
- `src/data/DataProvider.ts` - Data interface
- `src/data/MockDataProvider.ts` - Mock implementation
- `src/taxonomy/` - Category classification system

## Data Flow
```
UI Components → dataProvider (singleton)
  ├─ MockDataProvider (default, for development)
  └─ SupabaseDataProvider (mode="real", for production)
```

---

## UI/UX Improvement Roadmap

### Priority 1: Core Flow Friction Reducers

#### 1.1 "I Got It!" Wishlist → Portfolio Flow ✅ DONE
- [x] Add "Mark as Acquired" button on wishlist item detail
- [x] One-tap creates item in portfolio with pre-filled data
- [x] "Congrats!" animation on acquisition
- [x] Prompt for actual purchase price (feeds ML model)
- **Files:** `app/(tabs)/wishlist.tsx`, `src/data/DataProvider.ts`

#### 1.2 QuickScan Result Enhancement ✅ DONE
- [x] Price confidence gauge/meter visualization
- [x] "Why this price?" expandable explanation section
- [x] Quick-edit inline for name/category before saving
- [x] "Scan Another" button for batch sessions
- **Files:** `app/item/[id].tsx`, `src/components/PriceConfidenceGauge.tsx`

#### 1.3 Category Drill-Down from Item Detail ✅ DONE
- [x] Tappable category pill → category store
- [x] "See X similar items" link
- [x] "Missing from this set" teaser
- **Files:** `app/item/[id].tsx`, `app/categories/[categoryId].tsx`

### Priority 2: Engagement & Delight

#### 2.1 Portfolio Milestones & Achievements ✅ DONE
- [x] Achievement badges: "First item", "10 items", "€1000 portfolio"
- [x] Streak tracking for daily activity
- [x] Tier system (bronze, silver, gold, platinum)
- **Files:** `src/lib/achievements.ts`, `src/components/AchievementBadge.tsx`

#### 2.2 Visual Collection Grid (Gallery View) ✅ DONE
- [x] Toggle between list/grid on Items tab
- [x] Pinterest-style image grid
- [x] Tap to zoom with lightbox modal
- **Files:** `app/(tabs)/items.tsx`, `src/components/ItemGalleryGrid.tsx`

#### 2.3 Price Alert Animations ✅ DONE
- [x] Pulse animation on significant value change
- [x] Red/green micro-animation on price delta
- [x] "Hot" badge on trending items
- **Files:** `src/components/PriceDeltaBadge.tsx`

### Priority 3: Discovery & Social

#### 3.1 "Collectors Like You" Recommendations
- [ ] "People who collect X also collect Y" on category store
- [ ] Surface overlapping collections from public profiles
- [ ] "Follow Collection" feature
- **Files:** `app/categories/[categoryId].tsx`, `src/data/DataProvider.ts`

#### 3.2 Event Integration Improvements ✅ DONE
- [x] Native calendar integration (iOS/Android)
- [x] Countdown timers for upcoming drops
- [x] "Set Reminder" with push notification
- [x] Separate upcoming/past events sections
- **Files:** `app/(tabs)/events.tsx`, `src/lib/calendar.ts`, `src/components/EventCountdown.tsx`

#### 3.3 Marketplace Trust Integration
- [ ] "For Sale" listings on item detail
- [ ] Trust score badge on sellers
- [ ] "Price Check" comparing value to market
- **Files:** `app/item/[id].tsx`, `src/components/MarketListings.tsx` (new)

### Priority 4: Power User Features

#### 4.1 Bulk Operations ✅ DONE
- [x] Multi-select mode on Items tab
- [x] Bulk category reassignment
- [x] Bulk export selected items
- [x] Bulk delete with confirmation
- [x] Long-press to enter multi-select
- **Files:** `app/(tabs)/items.tsx`, `src/hooks/useMultiSelect.ts`

#### 4.2 Advanced Filters & Sorting ✅ DONE
- [x] Filter by: condition, price range, category
- [x] Sort by: value (high/low), name (A-Z/Z-A), recently added
- [x] Save filter presets with names
- [x] Collapsible filter sections
- **Files:** `app/(tabs)/items.tsx`, `src/components/FilterSheet.tsx`

#### 4.3 Portfolio Insights Dashboard ✅ DONE
- [x] Category breakdown pie chart
- [x] Best/worst performers
- [x] Liquidity score
- [x] Diversity index
- [x] Portfolio tier badges
- **Files:** `app/analytics.tsx`, `src/components/PortfolioPieChart.tsx`

### Quick Wins ✅ ALL DONE

| Feature | Status | File |
|---------|--------|------|
| Haptic feedback on save/delete | [x] | `src/lib/haptics.ts` |
| Pull-to-refresh on all lists | [x] | Items, Events, Wishlist |
| Empty state illustrations | [x] | `src/components/EmptyState.tsx` |
| Skeleton loaders | [x] | `src/components/Skeleton.tsx` |
| Swipe-to-delete | [x] | `src/components/SwipeableRow.tsx` |
| Long-press context menu | [x] | Multi-select mode on Items |

---

## Implementation Notes

### Completed UI/UX Sprint (2026-02-02)
- [x] Full UI/UX improvement roadmap implemented
- [x] 12 major features completed
- [x] 6 quick wins implemented
- [x] All core components created and integrated

### New Components Created
- `src/components/PriceConfidenceGauge.tsx` - Visual confidence meter
- `src/components/PriceDeltaBadge.tsx` - Price change animations
- `src/components/ItemGalleryGrid.tsx` - Pinterest-style grid
- `src/components/AchievementBadge.tsx` - Achievement display
- `src/components/EventCountdown.tsx` - Countdown timer
- `src/components/FilterSheet.tsx` - Advanced filter modal
- `src/components/EmptyState.tsx` - Empty state illustrations
- `src/components/Skeleton.tsx` - Loading skeletons
- `src/components/SwipeableRow.tsx` - Swipe gestures
- `src/components/PortfolioPieChart.tsx` - Category breakdown

### New Utilities Created
- `src/lib/haptics.ts` - Tactile feedback
- `src/lib/calendar.ts` - Calendar/notification integration
- `src/lib/achievements.ts` - Achievement system
- `src/hooks/useMultiSelect.ts` - Multi-selection hook

### Completed Cleanup (2026-02-02)
- [x] ErrorBoundary integrated into root layout
- [x] Comprehensive .env.example documentation
- [x] .gitignore updated for backup files
- [x] Logger utility created (src/lib/logger.ts)
- [x] Console.log replaced with logger in critical paths

### Taxonomy System
- Version: 2026.02.02
- Categories: Pokemon, MTG, Yugioh, Funko, Lorcana (Phase 1) + more
- Collection tags: BTS, Taylor Swift, Disney, Star Wars, etc.
- Deterministic mapper with confidence scores

### Environment Variables
See `.env.example` for full documentation. Key vars:
- `EXPO_PUBLIC_SUPABASE_MODE` - "mock" or "real"
- `API_SHARED_SECRET` - Backend API authentication
- `DB_ENABLED` - Database connectivity toggle

### A second HTTP client is a second auth story (2026-08-13)

The bound-on-the-client fix above (point 4) covers `supabase` and `httpClient`.
It did not cover `src/services/collectorsClient.ts`, an undocumented third
client that built its own requests: `X-API-Key` (empty — `EXPO_PUBLIC_API_KEY`
is unset), **no `Authorization` header**, and a bare `fetch` with no timeout and
no AbortController.

Every `/portfolio/*` route takes `Depends(get_current_user_id)`, so every call
it made 401'd. Each loader in `portfolioAnalyticsStore` catches and returns
null, so the failure was silent and portfolio analytics computed an empty
portfolio for every user, forever.

**The tell is in the access log, not the code.** Same endpoint, two clients:

```
193 GET /portfolio/overview 200   <- httpClient callers
  4 GET /portfolio/items    401   <- collectorsClient, and never a 200
```

An endpoint that 200s for one caller and 401s for another is not a server
problem. Before debugging a screen that shows no data, count status codes per
path in `/opt/collectors/bake.log` — if a path has never returned 200 in
production, the caller is the bug.

**Rules:**

1. **One client.** `src/api/httpClient.ts` is it (ARCHITECTURE.md says `src/api/`
   is the API client). It owns the bearer, the single-flight 401 refresh and
   `REQUEST_TIMEOUT_MS`. Anything else calling `fetch` directly re-opens all
   three holes at once.
2. **Fix the chokepoint, not the callers.** Deleting the duplicate and
   repointing its callers looked right until tsc found `categoriesClient.ts`
   importing it as `'./collectorsClient'` — a RELATIVE path that a grep for
   `services/collectorsClient` does not match. One shared `request()` covers
   both callers and every future one. See
   [[learning_enumerate_mechanically_never_triage_by_judgment]].
3. **A silent-null loader hides the whole class.** Every loader here was
   `try { ... } catch { return null }`, which is why a 100%-failing endpoint
   produced no error, no empty state and no log for months.

**Verifying an authenticated endpoint without an app session:** mint a JWT with
`SUPABASE_JWT_SECRET` — HS256, and it needs `aud: "authenticated"` *and*
`iss: $SUPABASE_JWT_ISSUER`, or `get_current_user_id` rejects it. Then call
`http://127.0.0.1:8000` on the box with `Host: api.sparrowcollect.com`. This is
read-only; do not reset a user's password to get a token.

### Three "is this rendering right?" questions, three different bugs (2026-08-28)

Asked why `Valuation Report` and `Market Prices` were empty on a populated item.
The visible answer was correct — both lazy-load on first tap — and underneath it
were two real defects plus a third found on the way. None was the one the
screenshot suggested.

**Read the log before theorising about the network.** The device log said it
outright:

    [useItemMarketplace] dropped 3 irrelevant comp(s) of 3 for
    "Rayquaza ex (Emerald 097)" — keyword search returned other products

Three of three is not a tuning problem, it is a structural one. The filter was
mine, added six days earlier, and it required tokens (`emerald`, `097`) that our
own comps structurally never carry. See `docs/MARKET_DATA.md`, "The fourth
defence is on the DISPLAY path".

**Measure the column before writing a rule about it.** Every fix below was sized
against prod first, and each measurement changed the fix:

- `sealed`: exactly **3 rows** in the whole DB, all `false`, on a category that
  never declares the field → the rule keys on the *declared field list*, not on
  the word.
- Empty `Collection` / `Condition` rows: **73 and 76 of 112 items** → the common
  case, so worth a rule rather than a special case.
- Boolean attrs overall: **one key in existence** → confirmed the rule could not
  hide anything else.

**"Unknown item" was RLS, not the timeout the toast was showing.** Supabase
answered in 250 ms from the laptop; the deep link pointed at an item owned by a
*different* account than the simulator was signed into. A zero-row RLS result
and a 15 s timeout render identically. `learning_a_wrong_diagnostic_is_believed_
for_sessions` — verify the artefact before believing its logs.

**A relaunch that fixes it is evidence, not a workaround.** The invisible list
row appeared after a cold start, which is what pointed at "added while the app
was open" and from there at the stagger hook. The symptom disappearing under a
specific condition names the cause.

**Simulator input is unreliable and it lies quietly.** `cliclick` moves the
pointer and reports success while the Simulator window is in pointer-capture
mode (`iPhone 17 – Press esc to stop capture`) and swallows every synthetic
event. Escape releases it; it re-enters on its own. Navigate with
`simctl openurl` and relaunch with `simctl terminate` + `launch` rather than
tapping. When input stops landing, **stop driving the sim and say which findings
are device-verified and which are test-verified** — do not let a flaky harness
turn into a claim.

**A test file is not a gate until `verify:prebuild` names it.** Four suites were
green and gating nothing, including one added the day before. The suite count
had gone up, which is exactly why I did not notice — a *different* file's tests
accounted for the rise.
