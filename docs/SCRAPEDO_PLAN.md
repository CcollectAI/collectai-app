# Scrape.do — 1,000 free requests a month, currently 0 used

## Measured 2026-08-31, not assumed

```
GET https://api.scrape.do/info
{"IsActive":true,"ConcurrentRequest":5,"MaxMonthlyRequest":1000,
 "RemainingConcurrentRequest":5,"RemainingMonthlyRequest":1000}
```

**1,000 of 1,000 remaining.** The account is live and the key is set on prod
(`SCRAPEDO_API_KEY`, 43 chars). Nothing has spent a single request this month.

⚠️ **Correction — `SCRAPEDO_ENABLED` is `false`, not `true`.** An earlier pass
here reported it as "SET", which is *presence*, not *value*. Reading the value
showed `false`, and `configured()` is `SCRAPEDO_ENABLED and bool(API_KEY)` — so
every call short-circuits before the HTTP request. Proven by spending zero
credits on a live `sold_comps("LEGO 10307 Eiffel Tower", "lego")`: 0 hits,
`RemainingMonthlyRequest` unchanged at 1000, and `configured() == False`.

> ⚠️ Note on naming: this is **Scrape.do**, not Crawl4AI. Crawl4AI is
> self-hosted, has no quota, and *has* been running — 8,159 rows across 1,755
> items in August. Scrape.do is the managed, anti-bot equivalent, and it is the
> one sitting idle.

## Why it is idle

Not a bug and not a missing key. `"scrapedo"` is in `DISABLED_ADAPTERS`
(`server/app/agents/marketplace_routing.py:231`), and `adapter_serves_category()`
checks that set **before** anything else — so the env flag and the API key are
both overridden in code.

## Why it is worth switching on — the thing crawl4ai cannot do

`scrapedo_caller._build_search_url(query, site, sold=True)` appends
`&LH_Complete=1&LH_Sold=1` — the **eBay sold-listings** search. Those pages are
real completed sales with real dates.

That matters because **99.98% of our comps are price-index snapshots with no sale
timestamp** (`docs/COLLECTOR_DEMAND.md` §1). Scrape.do is the only route to
genuine sold comps that does not wait on the eBay Marketplace Insights
application (`docs/EBAY_MARKETPLACE_INSIGHTS.md`, 1–6 weeks, approval not
guaranteed). The same adapters that would serve LEGO, whiskey, watches and
comics were disabled in May for *"anti-bot blocking"*, *"Akamai WAF 403"* and
*"prices are now JS-rendered"* — which is the exact problem Scrape.do exists to
solve.

## ⛔ Do NOT just re-enable it

There is **no quota tracking anywhere** in `scrapedo_caller.py` — only a
failure-based circuit breaker, which trips on errors, not on spend. And each
search loops `CATEGORY_SITE_TARGETS[category]`, so one item lookup costs 3–5
requests.

A single scrape cycle over the valuation backlog would burn all 1,000 in minutes,
then fail silently for the rest of the month — the free-tier version of
`learning_a_fallback_cached_as_long_as_the_real_thing`.

## The plan, in order

### 1. Build the meter first (code — mine)

- A persisted monthly counter (reset on the 1st, UTC), incremented per request.
- A hard stop at a configurable `SCRAPEDO_MONTHLY_BUDGET`, default **900** — a
  reserve below the real 1,000 so a miscount cannot overrun the account.
- Log at **ERROR** when the budget is exhausted, naming the count. A quota that
  runs out silently is indistinguishable from an adapter that is switched off.
- Reconcile against the live `/info` endpoint daily and alert if our count and
  theirs disagree by more than 5% — our counter is a belief, theirs is the fact.

### 2. Spend it where there is no sold data at all

1,000/month is ~33/day. It cannot refresh a catalogue, so it must not be pointed
at one. Proposed split:

| Budget | Target | Why |
|---|---|---|
| **700** | eBay **sold** pages for the most-held items in categories with **zero** sold comps — lego, watches, whiskey, vinyl_records, jewellery, action_figures | The only real `ended_at` data we can get this month |
| **200** | Re-probe the WAF/JS-blocked specialty sources — catawiki, brickeconomy, masterofmalt, abebooks | They were killed by exactly what Scrape.do bypasses. Probe before re-enabling: `learning_dont_allowlist_dead_assert_dead` |
| **100** | Reserve | Retries, and headroom for a miscount |

### 3. Re-enable, narrowly

Remove `"scrapedo"` from `DISABLED_ADAPTERS` **only after step 1**, and route it
to the zero-sold categories rather than to everything —
`ADAPTER_CATEGORY_ROUTING["scrapedo"]` is currently `None`, which means *every*
category. That must become an explicit set, or the budget goes to Pokémon, which
already has 831,303 comps.

### 4. Measure the result

After a month, the question is answerable: how many items in previously
zero-sold categories now have a real `ended_at` comp. If the answer is near zero
because the pages do not parse, that is worth knowing in month one rather than
month six.

## THREE switches, and all three must be on

This is why "the key is set" was never enough. They are independent, and each
one alone silently disables the adapter:

| # | Switch | Where | State |
|---|---|---|---|
| 1 | `SCRAPEDO_ENABLED` | prod `.env` | **`false`** ⛔ **← the remaining blocker** |
| 2 | `DISABLED_ADAPTERS` | `marketplace_routing.py` | ✅ removed 2026-08-31 |
| 3 | `ADAPTER_CATEGORY_ROUTING` | `marketplace_routing.py` | ✅ narrowed from `None` to 11 zero-sold categories |

## The one step left — yours, because it is a prod env change

```bash
# 1. flip the killswitch
ssh collectai
sudo sed -i 's/^SCRAPEDO_ENABLED=false/SCRAPEDO_ENABLED=true/' /opt/collectors/.env
grep '^SCRAPEDO_ENABLED=' /opt/collectors/.env        # must print true

# 2. deploy the code, then run the preflight chain MANUALLY before restarting
#    (preflight is ExecStartPre — a failure there hard-downs the API)
cd /opt/collectors && set -a; . ./.env; set +a
.venv/bin/python scripts/preflight_schema_lock.py     # must say PASS

# 3. restart
sudo systemctl restart collectai-bake.service
```

Then confirm it is actually spending:

```bash
curl -s "https://api.scrape.do/info?token=$SCRAPEDO_API_KEY" | jq .RemainingMonthlyRequest
```

It should fall below 1000 within a scrape cycle. If it does not, `configured()`
is still false — check the value, not the presence.

## Status

| | |
|---|---|
| Meter built | ✅ `app/lib/scrapedo_quota.py`, 9 tests, mutation-proven |
| Wired into the client | ✅ `scrapedo_client.scrape()` calls `allow()` before the request |
| Removed from `DISABLED_ADAPTERS` | ✅ |
| Routing narrowed | ✅ 11 categories with zero sold comps; pokemon and mtg excluded |
| `SCRAPEDO_ENABLED` on prod | ❌ **`false` — the one step left** |
| Requests used this month | **0 of 1,000** |
