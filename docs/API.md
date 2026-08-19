# API Reference

Base URL: `http://localhost:8000` (dev) | `http://51.21.210.195:8000` (production)

## Authentication

Most endpoints require a JWT token in the `Authorization: Bearer <token>` header. Tokens are issued by Supabase Auth.

- **JWT Auth**: `get_current_user_id` — returns 401 if missing/invalid
- **Optional Auth**: `get_optional_user_id` — returns `null` for anonymous users
- **API Key**: `require_api_key` — inter-service shared secret via `X-API-Key` header
- **Ops Key**: `require_ops_key` — operations API key via `X-Ops-Key` header

In `DEV_MODE=true`, JWT auth falls back to `DEV_USER_ID` without a token.

---

## Health & System

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/healthz` | No | Service health (with DB check) |
| GET | `/version` | No | Service version |
| GET | `/pipeline/status` | No | ML pipeline and ingest health |

## Items

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/items` | No | Create demo item (in-memory) |
| GET | `/items` | No | List demo items |

## Portfolio

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/portfolio/summary` | No | Lightweight portfolio summary |
| GET | `/portfolio/overview` | API Key | Portfolio overview (Signals proxy) |
| GET | `/portfolio/items` | API Key | Portfolio items (Signals proxy) |
| GET | `/portfolio/timeseries` | API Key | Portfolio timeseries (Signals proxy) |

## Barcode & Intake

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/barcode/lookup` | JWT | Barcode/ISBN lookup (local → Open Library → Google Books) |
| POST | `/intake/process` | JWT + Rate Limit | Full intake (image + barcode + hints) |
| POST | `/intake/barcode-only` | JWT + Rate Limit | Barcode-only intake |
| POST | `/intake/image-only` | JWT + Rate Limit | Image-only intake |
| POST | `/intake/url` | JWT + Rate Limit | Import from marketplace URL — **⛔ NOT part of the app. Deferred to a future build.** See note below |
| POST | `/intake/save` | JWT | Persist intake result as collection item |

### ⛔ URL import (`POST /intake/url`) is deliberately out of scope

**Product decision (Merle, 2026-07-30): the URL-import feature is not part of
the app. It can be a future build. Do not wire it up, and do not "fix" it.**

State of play, so nobody rediscovers this and mistakes it for a bug:

- `app/import-url.tsx` exists but is **intentionally unreachable** — no
  `router.push`, no entry in `AddMenuModal`, no `Stack.Screen` in `_layout.tsx`.
  That is correct, not an oversight.
- `server/app/ssrf.py::validate_url` currently rejects **every** domain-name URL:
  `_is_private_ip` returns `True` for anything it cannot parse as an IP, so a
  hostname is reported as "private/internal IP" and the DNS-resolution check
  below it never runs. Verified on prod 2026-07-30 — `www.ebay.com` and
  `cardmarket.com` are both blocked.
- `server/tests/test_ssrf.py` passes anyway because it patches `_is_private_ip`
  with `_mock_private_ip_for_domain`, a local reimplementation that returns
  `False` for domain names. The mock encodes the correct behaviour; the shipped
  function does not. Treat that suite as **not** covering the real guard.
- Net effect: the endpoint is closed, which is the safe direction. Nothing is
  exposed. It simply cannot import.

If URL import is ever picked up, the work is: fix `_is_private_ip` to
distinguish "not an IP" from "private IP" (so hostnames reach the DNS check),
drop the mock from the test so it exercises the real function, then add an
entry point. Until then, leave all three alone.


## QuickScan

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/quickscan` | No | Simplified QuickScan proxy |
| POST | `/quickscan/upload-image` | No | Upload image for QuickScan |
| POST | `/quickscan-advanced/single` | No | Enriched single-item scan |
| POST | `/quickscan-advanced/batch` | No | Multi-item batch scan |

## Vision

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/vision-predict/health` | No | Vision service health |
| GET | `/vision-predict/categories` | No | List 36 supported categories |
| POST | `/vision-predict/classify` | JWT + Rate Limit | Classify item image |

## Marketplace

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/marketplace/search` | JWT | Search across eBay, TCGPlayer, Cardmarket |
| POST | `/marketplace/comps/{item_ref}` | JWT | Find sold comparables |
| GET | `/marketplace/health` | No | Adapter health check |

## Watchlist

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/watchlist/mine` | JWT | Get user's watchlist (paginated) |
| POST | `/watchlist/mine` | JWT | Add item to watchlist |
| DELETE | `/watchlist/mine/{watch_id}` | JWT | Remove item from watchlist |

## Alerts

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/alerts/mine` | JWT | List price alerts (paginated) |
| POST | `/alerts/mine` | JWT | Create/update price alert |
| DELETE | `/alerts/mine/{alert_id}` | JWT | Delete/disable alert |
| GET | `/alerts/trigger-history` | JWT | Alert trigger history |
| POST | `/alerts/trigger-history/{trigger_id}/read` | JWT | Mark trigger as read |


## Provenance

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/provenance/items/{item_id}` | JWT | Item provenance timeline |
| POST | `/provenance/items/{item_id}/events` | JWT | Append provenance event |

## Insights

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/insights/personalized` | JWT | Personalized portfolio insights |
| GET | `/insights/home-widget` | JWT | Home widget snapshot |

## Price Prediction

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/predict/evidence/{item_id}` | JWT | Price prediction with evidence |

## Dossier

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/dossier/{item_id}` | JWT | Full item dossier (JSON) |
| GET | `/dossier/{item_id}/summary` | JWT | Lightweight dossier summary |
| GET | `/dossier/{item_id}/export` | JWT | Export dossier as HTML |

### What the dossier can and cannot fill in (2026-08-19)

Two fields were empty for **every** item until 2026-08-19, both silently:

- **`valuation` and the 90-day `price_history`** — the two lookups bound
  `items.canonical_key` (BARE) against `price_predictions.item_ref` /
  `price_prediction_daily.item_ref` (ALWAYS namespaced). Zero rows matched, for
  every item and every user. They now bind `items.canonical_ref`, the
  trigger-maintained resolved ref. An item whose `canonical_ref` is NULL has no
  price ref at all and correctly gets no valuation — there is deliberately no
  fallback to the bare key, which matches nothing by construction.
- **`identity.grade`** — read `attrs["grade"]`, a key no writer writes. Grade
  lives in `items.condition_grade` (the CSV importer writes it there and
  `/items-export` reads it back from there); only `graded_by` and `sealed` are
  in `attrs`.

Still empty, deliberately: **`collections` is always `[]`.** `items` has no
`collections` column, so `generate_dossier` hardcodes it. There IS a usable
column — `items.collection_name` (singular), which `/items-export/full` already
surfaces — but wiring it changes what the Pro PDF prints, so it is an open
product decision rather than a bug.

## Events

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/events` | Optional | List events (filterable by category) |
| POST | `/events` | JWT | Create event |
| GET | `/events/{event_id}` | Optional | Event details |
| POST | `/events/{event_id}/rsvp` | JWT | RSVP to event |
| DELETE | `/events/{event_id}/rsvp` | JWT | Remove RSVP |
| GET | `/events/categories/followed` | JWT | List followed categories |
| POST | `/events/categories/{category_id}/follow` | JWT | Follow category |
| DELETE | `/events/categories/{category_id}/follow` | JWT | Unfollow category |
| GET | `/events/categories/{category_id}/following` | JWT | Check if following |

## Storage (S3)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/storage/presign-upload` | JWT | Generate presigned upload URL |
| GET | `/storage/presign-download/{pointer_id}` | JWT | Generate presigned download URL |
| GET | `/storage/objects` | JWT | List object pointers |
| DELETE | `/storage/objects/{pointer_id}` | JWT | Soft-delete object pointer |

## Taxonomy

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/taxonomy/current` | No | Current taxonomy version |
| GET | `/taxonomy/versions` | No | All taxonomy versions |
| GET | `/taxonomy/categories` | No | Flat category list for UI |
| GET | `/taxonomy/{version}` | No | Specific taxonomy version |

## Import

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/imports/template` | No | Download CSV import template |
| POST | `/api/imports/collection` | JWT | Import collection from CSV/Excel |

## Smart Deal Agent

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/purchase/mandates` | JWT | Create purchase mandate |
| GET | `/purchase/mandates` | JWT | List mandates (paginated) |
| GET | `/purchase/mandates/{mandate_id}` | JWT | Get mandate details |
| PATCH | `/purchase/mandates/{mandate_id}` | JWT | Update mandate |
| DELETE | `/purchase/mandates/{mandate_id}` | JWT | Deactivate mandate |
| GET | `/purchase/deals` | JWT | List deals (paginated, filterable) |
| GET | `/purchase/deals/{deal_id}` | JWT | Get deal details |
| POST | `/purchase/deals/{deal_id}/click` | JWT | Track affiliate click |
| POST | `/purchase/deals/{deal_id}/confirm` | JWT | Confirm purchase |
| POST | `/purchase/deals/{deal_id}/decline` | JWT | Dismiss deal |
| GET | `/purchase/stats` | JWT | Agent stats |

### `canonical_key` — what a mandate is VALUED against (2026-08-12)

`POST` and `PATCH /purchase/mandates` accept an optional **`canonical_key`**,
the **BARE** catalogue key that `/catalog/match` and the catalogue screens
already return (`base1-base1-1`, not `pokemon:base1-base1-1`). **Do not
namespace it** — the server derives the prefix from the item's own
`category_items` row and stores the result in `canonical_ref`. Sending an
already-namespaced key is tolerated (the bare tail is taken) but is not the
contract.

```jsonc
POST  /purchase/mandates   { "name": "...", "search_query": "charizard",
                             "max_price": 120, "canonical_key": "base1-base1-1" }
PATCH /purchase/mandates/:id { "canonical_key": null }   // clears → free-text
```

| | |
|---|---|
| **It does not replace `search_query`** | The query is what we send to marketplaces; the key is what we value the results against. Two jobs. Keep the query editable so a user can narrow it ("PSA 10") without breaking valuation. |
| **It overwrites `category`** | The mandate takes the picked item's category. `canonical_ref` and `category` disagreeing would mean the mandate reads as one thing and values as another. |
| **Unknown key → `400 UNKNOWN_CANONICAL_KEY`** | The key is looked up at write time, so a typo fails immediately instead of creating a mandate that silently values nothing forever. |
| **`MandateResponse.canonical_ref`** | Namespaced, or `null` for a free-text mandate — read it to show keyed vs unkeyed without a second call. |

**Why it exists:** without a key, the deal agent values every result by
`item_ref ILIKE '<search_query>'`, which returns ONE prediction for the whole
query. Measured on a live mandate: 27 deals sharing `q50 = €1.08` against
listings from €2.59 to €216.54. `value_summary.deal_savings` therefore counts
**only keyed mandates** — a free-text mandate's deals are counted but contribute
€0, because a category average must never be shown to a user as money saved.

**Who sends it (2026-08-12):** `app/purchase/create-mandate.tsx` — a "value
against" block that calls `/catalog/match` with the name the user typed and
lets them pick. Optional by design: skipping it creates a free-text mandate,
which still works, just without money figures.

Two rules that screen has to honour, both learned by getting them wrong:

- **A picked key belongs to the name it was picked for.** The screen stores
  that name alongside the key and drops both if the name is edited afterwards.
  Without this a user picks "Rolex Submariner", retypes the name, and the
  mandate silently values against the Rolex forever — the precise failure the
  picker was built to prevent.
- **Send `null`, don't omit.** Clearing the key means transmitting an explicit
  `null`; a field left out of the PATCH body reads as "unchanged". The screen
  detects intent via `model_fields_set`, because the server's
  `model_dump(exclude_none=True)` cannot tell the two apart.

## Catalog Browser

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/catalog/{category_id}/items` | No (IP rate limit) | Browse the catalog. `sort=value\|newest\|set\|title` (`value` ranks by latest comp price and implies `priced_only`), `priced_only`, `q`, `rarity`, `limit`, `offset`. `total` is always the full category count. Drives the category-page overview rail. |
| GET | `/catalog/{category_id}/collections` | No | Set_code-grouped discovery collections with cover art |
| POST | `/catalog/match` | JWT + Rate Limit | Match a manual (title, category) entry → best catalog item_key for canonical_key |

## Catalog Learning

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/catalog/suggest` | JWT + Rate Limit | Submit unrecognized item suggestion (10/hr/user) |
| GET | `/ops/catalog-suggestions` | Ops Key | List suggestions (paginated, filterable by status/source) |
| POST | `/ops/catalog-suggestions/{id}/action` | Ops Key | Approve/reject/map a suggestion |
| GET | `/ops/category-candidates` | Ops Key | List new category candidates |
| POST | `/ops/category-candidates/{id}/action` | Ops Key | Approve/reject/merge a candidate |

## P2P Marketplace (member-to-member)

Governed by `docs/P2P_MARKETPLACE_SPEC.md`. **Sparrow never touches funds** —
there is no checkout, no escrow and no payout endpoint here by design, and §5b
of the spec sets out what may and may not be added.

Note these are **not** mounted under `/v1/` (unlike most of the API above),
matching how `p2p_listing_router` / `p2p_offers_router` are registered in
`main.py`.

### Listings (Stage 1)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/p2p/listings` | JWT + Rate Limit | List an item you own (`item_id`) **or** list without a collection (`title` + optional `category`/`canonical_key` — the item is created for you, tagged `source='marketplace'`). 400 `ITEM_OR_TITLE_REQUIRED`, 409 `ALREADY_LISTED`, 404 `ITEM_NOT_FOUND` (ownership enforced server-side). `photo_catalogue_consent` (default **false**) opts the listing photo into catalogue reuse under ToS §3 |
| GET | `/p2p/listings` | JWT | Browse. Repeatable `category`, `canonical_key`, `q`, `mine`, `sort`, `price_min/max`, `price_currency`. **Excludes blocked members both ways** |
| GET | `/p2p/listings/{listing_id}` | JWT | Deep-link target for `sparrowcollect.com/l/<id>`. Returns sold/delisted with real status, not 404. A blocked seller's listing 404s (never 403 — that would confirm it exists) |
| POST | `/p2p/listings/{listing_id}/delist` | JWT | Mark sold/delisted. Removes the buyable `market_hits` row **synchronously** |
| POST | `/p2p/listings/{listing_id}/report` | JWT + Rate Limit | DSA Art 16 notice-and-action. Re-reporting is a no-op and does not inflate the counter |
| GET | `/p2p/facets/categories` | JWT | Categories that actually have live listings, with counts |
| GET | `/p2p/demand/{item_id}` | JWT | Pre-listing demand. **Ownership enforced** — demand is competitive information |

### Offers, completion, tracking (Stage 2)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/p2p/offers` | JWT + Rate Limit | Make an offer. 403 `USER_BLOCKED` if either party blocked the other |
| GET | `/p2p/offers` | JWT | Offers made or received (`role=all\|buying\|selling`) |
| POST | `/p2p/offers/{offer_id}/respond` | JWT + Rate Limit | `action=accept\|decline\|counter\|withdraw`. Accept reserves softly; it does not delist |
| POST | `/p2p/offers/{offer_id}/confirm` | JWT + Rate Limit | Seller marks sent, buyer marks received. **Both ⇒ completed** — the only completion writer |
| POST | `/p2p/offers/{offer_id}/tracking` | JWT + Rate Limit | Attach carrier + consignment code. **Seller only**, while `accepted`/`shipped`. DISPLAY ONLY — never advances the trade |
| GET | `/p2p/carriers` | No | Carrier picker options. `linkable=false` ⇒ no code-only tracking URL exists (PostNL/DPD need the recipient's postcode), so render a copyable code, not a link |
| POST | `/p2p/offers/{offer_id}/grade` | JWT + Rate Limit | Grade the counterparty. Only after two-sided completion |
| GET | `/p2p/members/{member_id}/reputation` | JWT | Trade count + positive %; % hidden below 3 grades |

### Moderation (DSA Art 16/17)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/ops/listing-reports` | Ops Key | Open moderation queue, **oldest first** |
| POST | `/ops/listing-reports/{listing_id}/action` | Ops Key | `action=remove\|dismiss` + `ground` + optional `explanation`. Resolves every open report, and **issues the Art 17 statement of reasons to the seller** via `notification_history` |

**Art 17 is not optional at our size.** It sits in Section 2 of the DSA, and the
Art 19 micro-enterprise exclusion reaches only Section 3 (Arts 20–28). Removing
a listing without telling the seller why is the breach itself, which is why the
takedown and the notification share one transaction — if the seller cannot be
told, the removal rolls back.

Valid `ground` values: `illegal_content`, `terms_breach`, `counterfeit`,
`prohibited_item`, `misleading`. Anything else returns 400 `UNKNOWN_GROUND`.

## User Settings

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/settings` | JWT | Get user settings |
| PUT | `/settings` | JWT | Upsert user settings |

## Operations

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/ops/status` | Ops Key | Ops status |
| GET | `/ops/worker-status` | Ops Key | Worker status |
| GET | `/ops/cache` | Ops Key | Cache stats |
| GET | `/ops/circuits` | Ops Key | Circuit breaker status |

---

## API Versioning & Deprecation

All endpoints are available at both unversioned paths (`/items`, `/alerts/mine`, etc.) and under the `/v1/` prefix (`/v1/items`, `/v1/alerts/mine`, etc.). Both resolve to the same handlers.

**Deprecation timeline:**

| Phase | Target | Action |
|-------|--------|--------|
| Current | v1.0 | Unversioned and `/v1/` paths both active (backward compatible) |
| v2.0 | +6 months | New endpoints may only appear under `/v2/`; `/v1/` frozen (no new features) |
| v2.0 + 12 months | | Unversioned paths removed; clients must use `/v1/` or `/v2/` explicitly |
| v2.0 + 18 months | | `/v1/` deprecated; returns `Sunset` header + `Deprecation` header |
| v2.0 + 24 months | | `/v1/` removed |

**Client migration guidance:**
- All new integrations should use `/v1/` prefix immediately.
- The `Sunset` header (RFC 8594) will be added to deprecated endpoints at least 6 months before removal.
- Response bodies will include a `deprecation` field when applicable.

---

## Rate Limits

| Scope | Limit |
|-------|-------|
| Vision classification | 20 req/min per user |
| Intake endpoints | 30 req/min per user (shared) |
| Catalog suggestions | 10 req/hr per user |

## Social

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/social/users/search?q=&limit=` | JWT | Search public profiles by name/handle |
| POST | `/social/block/{user_id}` | JWT | Block a user |
| DELETE | `/social/block/{user_id}` | JWT | Unblock a user |
| GET | `/social/blocked` | JWT | List blocked users |
| GET | `/social/leaderboard/category/{category_id}?metric=&limit=` | JWT | Top collectors in ONE category |
| GET | `/social/users/{user_id}/categories?limit=` | JWT | What a collector collects + their rank in each |

### `GET /social/leaderboard/category/{category_id}` (2026-08-16)

Ranks the collectors of a single category. `metric=items` (default) ranks by
items owned; `metric=value` ranks by value held.

**This is not the XP leaderboard.** `GET /gamification/leaderboard` ranks by
`user_gamification.weekly_xp | monthly_xp | total_xp`, which has **no category
dimension at all**, and its UI is gated off behind `GAMIFICATION_UI_ENABLED`
because the number is not meaningful. A per-category board therefore had to be
built on real data.

**Privacy is the design, not a filter bolted on.** Settings → Privacy has
"Allow discovery" and "Show item count", and the help text promises both do
something, so:

- the base is `user_public_profiles`, which already excludes members who turned
  discovery off;
- anyone with `show_item_count = false` is excluded outright — a board of item
  counts is exactly the disclosure that switch refuses;
- `metric=value` **additionally** excludes `show_collection_value = false`, so
  it is a strictly shorter board than `metric=items`.

Missing `user_privacy_settings` rows default to TRUE, matching the table
defaults and the client.

`value_eur` uses the app's canonical valuation expression, which is
`public.v_item_values_v1`:

    quick_predictions.q50_eur (latest by created_at)
      -> price_predictions.q50 via items.canonical_ref (latest by generated_at)
      -> items.predicted_price_eur
      -> items.estimated_value
      -> 0

**The second step was missing until 2026-08-17** and the board quoted numbers no
other screen agreed with — 8 of 74 live items differed, one member reading
EUR 78.90 here against EUR 185.15 in their own portfolio. Nothing failed; a
leaderboard of plausible wrong numbers looks exactly like a correct one.

The chain is written out in SQL rather than selected `FROM v_item_values_v1`
because that view ends `WHERE user_id = auth.uid()` — it answers "what is MY
collection worth" and returns nothing when aggregating across members. That
duplication is why it drifted, so `server/tests/test_leaderboard_value_parity.py`
now diffs both copies against the view per user, under a real auth context
(`set_config(..., FALSE)`; TRUE is transaction-local and makes the two sides
agree trivially). **Change one copy, change both, and run that test.**

`npm run check:item-value-source` does NOT cover this — it checks the FE
provider and `mapItemRow`, and cannot see SQL inside a Python string.

**A short board is a correct board** — do not pad it, and do not treat a small
row count as an error. On prod today `mtg` returns 3 ranked collectors, all with
`value_eur = 0` because those items carry no valuation yet; the client says so
explicitly rather than rendering a ranking of zeros.

### `GET /social/users/{user_id}/categories` (2026-08-17)

What a collector collects, most-held first, with their standing in each. The
profile previously showed totals and achievements only, so two members with
completely different collections read almost identically.

Returns `{user_id, categories: [{category_id, item_count, value_eur, rank,
total_ranked}], value_visible}`.

**`rank` is nullable and null means NOT RANKED — not last place.** It is null
when the member is not in `user_public_profiles` (discovery off) or hides their
item count, and that is the COMMON case because discovery is off by default. A
rank is a statement about a count, so hiding the count withholds the rank too:
"#2 of 40" hands back exactly the ordering the switch refused. The client
renders this as its own state and never as a number.

The same three switches as the leaderboard, and they are not interchangeable:

| switch off | effect |
|---|---|
| not in `user_public_profiles` | empty list — not a 404, which would confirm the account exists |
| `show_item_count` | categories still listed, `item_count` 0, **no rank** |
| `show_collection_value` | `value_eur` 0 **and** `value_visible: false`, so the client can say "hidden" rather than "EUR 0" |

Viewing your OWN profile bypasses all three — hiding your collection from
yourself is not a privacy feature.

Ranking is computed in the SAME statement as the totals, restricted to the
categories that member holds. Calling the leaderboard endpoint once per category
would be 12 HTTP round trips to our own API to render one screen.

## Error Response Format

All errors use a consistent format via `error_response()`:

```json
{
  "detail": "Human-readable message",
  "code": "MACHINE_READABLE_CODE"
}
```

Common codes: `VALIDATION_ERROR`, `DB_ERROR`, `NOT_FOUND`, `UNAUTHORIZED`, `RATE_LIMITED`.
