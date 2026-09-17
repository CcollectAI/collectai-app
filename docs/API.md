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

## Every endpoint that answers WITHOUT a token (enumerated 2026-09-17)

Read out of the code, not out of this file: 21 handlers have no `Depends(...)`
auth in the signature or the decorator, no router-level dependency, and no
in-body key check. All 21 are deliberate; the list exists so the next person can
tell "public by design" from "public by accident" without re-deriving it.

| Method | Path | Why it is open |
|---|---|---|
| GET | `/catalog/{category_id}/items`, `/catalog/{category_id}/items/{item_key}/price`, `/catalog/{category_id}/collections`, `/catalog/top-movers` | catalogue reference data, IP rate limited |
| GET | `/sets`, `/sets/{set_id}` | set reference data |
| GET | `/taxonomy/categories`, `/taxonomy/{version}` | category vocabulary |
| GET | `/marketplace/listings/fees`, POST `/marketplace/listings/fees/calculate` | fee schedules; the handler's own docstring says "public, no auth required" |
| GET | `/sponsor-companies/{company_id}` | a sponsor's public profile |
| GET | `/photos/view/{photo_key:path}` | **capability URL**: React Native's `<Image>` cannot send an Authorization header. `_PHOTO_KEY_RE` is the security boundary — see the handler's docstring |
| POST | `/webhook`, `/revenuecat-webhook` | provider webhooks; each verifies its own signature/secret in the body |
| POST | `/api/beta-signup` | the landing page's form |
| GET | `/api/imports/template` | the CSV import template |
| GET | `/marketplace/health`, `/marketplace/adapter-health`, `/vision-predict/health`, `/vision-predict/categories`, `/pipeline/status` | health and reference |

**`/pipeline/status` used to return `str(e)` on a DB failure** — internal error
text from a public endpoint. Fixed 2026-09-17; the text stays in the log.

Two things that look like findings and are not, recorded so the next sweep does
not re-open them: `POST /vision-predict/classify` declares its auth in the
DECORATOR (`dependencies=[Depends(get_current_user_id), …]`), and
`PUT /marketplace/listings/accounts/defaults/ebay` uses
`Depends(require_seller_age_verified)`, which returns the user id. A scan that
only reads the signature, or that matches a hand-written list of dependency
names, reports both as open.

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
| PATCH | `/items/{item_id}/attributes` | JWT | Merge keys into `items.attrs` (jsonb). `item_size`/`size_system` fold into the SAME jsonb — the table has no columns for them |
| PATCH | `/items/{item_id}/purchase` | JWT + Rate Limit | Set or clear the cost basis. Writes `purchase_price`, `purchase_price_eur` and `purchase_currency` **together** — see the router's own header for why a client-side patch is a ~170x currency bug |

### `{"ok": true}` means a row was written (2026-09-17)

Both PATCHes answer:

| | |
|---|---|
| **404 `NOT_FOUND`** | the id is not this member's, or does not exist. The `WHERE` carries `user_id`, so those are the same case and get the same sentence — the endpoint cannot be used to probe which item ids exist |
| **503 `DB_UNAVAILABLE`** | no database. Both used to answer `200 {"ok": true, "item_id": …}` here, and the app takes `ok` as "saved": it closes edit mode and toasts success, so the edit vanished silently. One of the two carries the purchase price |

An **empty** attributes patch still answers `200 {"ok": true}`, and that is
honest — nothing was going to be written, so the answer does not depend on the
database. The handler checks it BEFORE `get_db_pool()` for exactly that reason.

`PATCH /items/{id}/purchase` sends `purchase_price: null` to CLEAR (both halves,
plus the fees). **Omitting** a field means "leave it alone" — a distinct third
state, detected with `model_fields_set`, so a member can edit fees without the
client resending a price that would be re-converted at today's FX rate.

## Portfolio

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/portfolio/summary` | No | Lightweight portfolio summary |
| GET | `/portfolio/overview` | API Key | Portfolio overview (Signals proxy) |
| GET | `/portfolio/items` | API Key | Portfolio items (Signals proxy) — see the value fields below |
| GET | `/portfolio/timeseries` | API Key | Portfolio timeseries (Signals proxy) |

### A failed read answers 503, never zeros (2026-09-17)

`/portfolio/overview`, `/portfolio/items`, `/portfolio/timeseries`,
`/portfolio/category-stats`, `/portfolio/category-health`,
`/portfolio/category-correlation` and `/alerts/trigger-history` used to catch
their own database errors and answer **200** with an empty payload — the
overview with `{"total_value": 0, "item_count": 0, "items": []}`, which is the
sentence Home puts in its hero. A caller cannot tell that from an empty
collection, so the app showed €0 to a member whose database read had failed.

They now `raise error_response(503, …, code="DB_UNAVAILABLE" | "DB_ERROR")` when
the query fails AND the Signals proxy fallback fails. **Clients must treat 503
on these paths as "unknown", not as "empty"** — the app does: `ApiError` reaches
Home's `seriesFailed`, which renders "—" and hides the estimate line rather
than printing a number nobody has.

Gated by `python3 server/scripts/check_empty_on_failure.py` (in
`verify:prebuild`): a route handler may not return an empty payload from an
`except` block without a written `# empty-ok: <why>`. A payload that SAYS it
failed (`{"status": "error", …}`) is not a finding.

### `/portfolio/items` — the value fields tell you what they are worth trusting

Three fields on each row exist so a caller cannot mistake one kind of number
for another (added 2026-07-28 and 2026-08-19):

| field | meaning |
|---|---|
| `current_value` | the canonical chain: catalog model → quick valuation → the member's own numbers |
| `has_purchase_price` | **false ⇒ `unrealized_pl` is model drift, not profit.** The server falls back to the earliest prediction as cost basis when no purchase price is on file. Never sum P/L across items without checking it |
| `value_source` | which link produced `current_value`: `catalog_model` / `catalog_daily` / `quick_scan` are comp-backed; `user_estimate` / `app_estimate` are numbers nobody checked; `none` means nothing answered |

An **absent** `value_source` (an older server build) must be read as *unknown*,
never as market — the conservative side is the one that under-claims.

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
| GET | `/alerts/trigger-history` | JWT | Alert trigger history. **`read` is part of the contract** — see below |
| POST | `/alerts/trigger-history/{trigger_id}/read` | JWT | Mark trigger as read. 404 `NOT_FOUND` if it is not yours or does not exist; 503 `DB_ERROR` if the write failed |

### Marking an alert read — three ways it used to do nothing (2026-09-17)

`POST /alerts/trigger-history/{id}/read` answered `{"ok": true}` from THREE
exits where nothing had been written: no database configured, a swallowed
`asyncpg.PostgresError`, and a row count nobody read (so another member's
trigger id answered `ok`). It now answers 404 / 503 / 404 respectively.

`GET /alerts/trigger-history` has always returned each row's **`read`** flag,
and the client dropped it on mapping — `useAlertsFeed` hardcoded
`isRead: false`. So even a successful write was invisible: the alert came back
as new on the next fetch and `unreadOnly` could never filter anything. Clients
must read `read`; `AlertFeedItem.read` is now a REQUIRED field so a mapping
cannot omit it silently.

**A `derived-…` id is not a trigger id.** The app builds client-side alerts from
an item's price band (`derived-drop-<itemId>`); they have no row here, are not
uuids, and this endpoint answered 400 for every one. Do not post them.


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
| POST | `/events/{event_id}/announcements` | JWT + Rate Limit | Post an announcement. **403 unless host or sponsor admin.** Also DMs every going/interested attendee, in a background task. Returns 201 |
| GET | `/events/{event_id}/announcements` | JWT | List announcements, with `is_read`. **403 for a non-attendee**, which the app renders as its own state |
| POST | `/events/{event_id}/announcements/{announcement_id}/read` | JWT | Mark one announcement read |
| POST | `/events/{event_id}/announcements/batch-read` | JWT | Mark a batch read |
| GET | `/events/my-announcements/unread-count` | JWT | Unread count across every event the member attends |

### The announcement DM had not delivered a single message since 2026-04-30

`_send_announcement_dms` found-or-created a thread in **`dm_threads`** and then
inserted into `chat_messages_v1`, whose `thread_id` FK was repointed to
`chat_threads_v1` on 2026-04-30. `dm_threads` holds **0 rows** on production
(read back 2026-09-17), so every send violated the FK, the per-attendee `except`
logged a warning, and the summary line said `sent=0` **at INFO**. Five months.

Rules for anything that writes a DM from now on:

1. **Go through `rpc_send_message_v1(thread_id, user_id, body)`** — the same
   writer `chat_router.send_message` uses. A second private copy is how one
   surface gets a schema fix and another silently does not.
2. **Threads live in `chat_threads_v1`** (upsert on `ux_chat_threads_v1_dm_pair`,
   pair canonicalised least/greatest) with both `chat_thread_members_v1` rows —
   the inbox reads membership.
3. **`dm_user_a/b` REFERENCE `auth.users`** and `event_attendees` does not, so
   filter attendees on `EXISTS (SELECT 1 FROM auth.users …)`: 3 of production's
   distinct attendee ids are deleted accounts.
4. **Honour blocks (`app/lib/blocks.py`) and a `denied` `chat_dm_requests_v1`
   row.** An announcement is still a DM.
5. **A total failure logs at ERROR**, not INFO. `sent=0` in an INFO line is
   invisible.

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

**Example rows are skipped by MARKER, never by name (2026-09-14, needs deploy).**
The template ships three example rows, and only the first said "(delete this
row)"; the importer skipped nothing but nameless rows. A member who typed their
own rows under the examples imported a €9,800 Rolex and a LEGO Falcon they do
not own (0 such rows in prod when found). All three are now `EXAMPLE – … (delete
this row)` and rows matching that marker are skipped with "Example row from the
template — skipped". Not by name: the template is the round-trip format of
`/items-export/overview`, so a member's own export can hold a real "Rolex
Submariner 116610LN". Tests in `server/tests/test_import_router.py`; run locally
through a stub harness (the full server venv needs Xcode CLT 26.3 to build),
mutation-proven — with the skip removed, the unchanged template imports 3 rows.

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

### `allowed_sources` — must be the CALLER's source tag, exactly (2026-09-14)

`policy_engine.py` check 5 rejects a hit unless `hit["source"] in
allowed_sources` — an exact string match, and nothing validates the values on
write (no CHECK, no enum). So a toggle is only as good as the tag its caller
stamps: `server/app/agents/adapters/<name>_caller.py`, the `"source"` field.

`create-mandate.tsx` sent **`"mercari"`** while `MercariUSCaller` tags
**`"mercari_us"`**: switching Mercari on would have rejected every Mercari
result (whether the Mercari caller is configured on prod was not checked). The other six toggles (ebay, tcgplayer, cardmarket, discogs, stockx,
bricklink) were checked against their callers and match. The screen now keeps
`value` (the tag) apart from `brand` (the label-map key) and maps a stored
legacy `mercari` on load. Prod had **0 mandates** when found, so nobody was
affected. Found by checking the help page's "pick which marketplaces" claim.

## Catalog Browser

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/catalog/{category_id}/items` | No (IP rate limit) | Browse the catalog. `sort=value\|newest\|set\|title` (`value` ranks by latest comp price and implies `priced_only`), `priced_only`, `q`, `rarity`, `limit`, `offset`. `total` is always the full category count. Drives the category-page overview rail. |
| GET | `/catalog/{category_id}/collections` | No | Set_code-grouped discovery collections with cover art. `display_name` is the catalogue's own set name when it is unique in the category (`mv_catalog_collections.set_name`), else the code — humanised only if all-lowercase. ✅ `server/scripts/20260914_collection_set_names.sql` applied and the router deployed 2026-09-14, in that order — the reverse 500s the rail. Recreating the MV again? Same order, and check `relacl` came back |
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
| POST | `/p2p/offers/{offer_id}/respond` | JWT + Rate Limit | `action=accept\|decline\|counter\|withdraw`. Accept reserves softly; it does not delist. **One transaction, offer row locked** |
| POST | `/p2p/offers/{offer_id}/confirm` | JWT + Rate Limit | Seller marks sent, buyer marks received. **Both ⇒ completed** — the only completion writer. **One transaction, offer row locked**; see below |
| POST | `/p2p/offers/{offer_id}/tracking` | JWT + Rate Limit | Attach carrier + consignment code. **Seller only**, while `accepted`/`shipped`. DISPLAY ONLY — never advances the trade |
| GET | `/p2p/carriers` | No | Carrier picker options. `linkable=false` ⇒ no code-only tracking URL exists (PostNL/DPD need the recipient's postcode), so render a copyable code, not a link |
| POST | `/p2p/offers/{offer_id}/grade` | JWT + Rate Limit | Grade the counterparty. Only after two-sided completion |
| GET | `/p2p/members/{member_id}/reputation` | JWT | Trade count + positive %; % hidden below 3 grades |

### Both write paths take the offer row's lock (2026-09-17)

`respond` and `confirm` each read the offer, decided in Python, and then wrote —
with no transaction and no `FOR UPDATE`. Two consequences, both live:

* **Partial writes.** `accept` updates `p2p_offers` and then
  `marketplace_listings`; a failure between them left an accepted offer whose
  listing was never reserved. `withdraw` left the mirror — a cancelled offer
  still holding the reservation, invisible to the seller.
* **Concurrent responses.** Two confirms in flight each saw only their own
  timestamp, so `both` was false for both callers and **completion never
  fired**: the trade stuck at `accepted` with two confirmations and no way
  forward, since `ALREADY_CONFIRMED` rejects the retry. The other interleaving
  ran the completion body twice — including `_dac7_accrue`, which is a tax
  number.

Anything added to these handlers must keep the shape:

1. **Decide under the lock.** `FOR UPDATE` on `p2p_offers` — and `FOR UPDATE OF o`
   in `respond`, whose query LEFT JOINs the listing and the address (Postgres
   refuses to lock the nullable side of an outer join).
2. **Writes that must agree go in the same transaction**, `_settle_completed_trade`
   included: it takes the caller's `conn`, which is what makes the object move
   atomically with the completion.
3. **Hooks that open their own connection go after the commit** —
   `_stale_supply_hook`, `_sold_comp_hook`, `_ground_truth_hook`,
   `_dac7_accrue`. `_sold_comp_hook` reads `marketplace_listings`, so inside the
   transaction it sees the pre-commit status and skips.
4. **Notifications outside the lock.** They are writes too, and nothing should
   hold a row lock across them.

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
| POST | `/social/block/{user_id}` | JWT | Block a user + deny any pending DM request between the pair. 503 `DB_UNAVAILABLE` with no database — **never a success claim** |
| DELETE | `/social/block/{user_id}` | JWT | Unblock a user. Same 503 |
| GET | `/social/blocked` | JWT | List blocked users. 503 rather than `[]` when the read cannot run |
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

## Billing & subscription webhooks

Undocumented here until 2026-09-17, which is part of why the bug below lived so
long. `server/app/routes/billing_router.py`.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/billing/status` | JWT | Current plan + limits (`PLAN_LIMITS`) |
| POST | `/billing/webhook` | Stripe signature | Stripe events (sponsorships, tickets, web subscriptions) |
| POST | `/billing/revenuecat-webhook` | `Authorization: <REVENUECAT_WEBHOOK_AUTH>` | In-app purchases — **the only path from a mobile purchase to `subscriptions`** |

### The idempotency contract, and the way it used to fail

Both handlers claim the provider's event id before doing any work:

```sql
INSERT INTO processed_webhook_events (event_id, event_type)
VALUES ($1, $2) ON CONFLICT (event_id) DO NOTHING RETURNING event_id
```

A returned row means "ours to process"; no row means a duplicate delivery, and
the handler returns 200 immediately.

**Nothing ever deleted that row.** So a failure *after* the claim was permanent:
the provider's retry short-circuited on the claim and the work never happened.
For RevenueCat that meant a member could be **charged, written into the revenue
ledger (`subscription_events`), and left on `free` forever** — `get_user_plan`
reads `subscriptions`, and nothing reconciles the two. The code even reasoned
that "a retry would be a no-op on the ledger anyway", which is true and beside
the point: the retry exists to write the *other* row. Stripe had the same shape
across sponsorships, tickets and plan changes.

Rules for anything added to these handlers:

1. **Any failure after the claim must release it** — `_release_webhook_claim()` —
   and then return 5xx so the provider retries. Never 200 on a failed write.
2. **Every write must stay idempotent**, because a released claim means the whole
   handler runs again: `ON CONFLICT DO NOTHING` on the ledger, upserts for state.
3. A permanently failing event is now retried on the provider's schedule instead
   of swallowed once. That is deliberate — a retry storm is visible in
   `bake.log`, an unpaid-for subscription is not.

Verified on prod 2026-09-17: `processed_webhook_events` held 10 rows, and **0
paid events had no `subscriptions` row** — the bug had not yet bitten a real
member (the 6 ledger rows are test events with unresolvable users).

## Error Response Format

All errors use a consistent format via `error_response()`:

```json
{
  "detail": "Human-readable message",
  "code": "MACHINE_READABLE_CODE"
}
```

Common codes: `VALIDATION_ERROR`, `DB_ERROR`, `NOT_FOUND`, `UNAUTHORIZED`, `RATE_LIMITED`.

**`detail` is UI.** `src/lib/userErrorMessage.ts` shows the server's own sentence
when the server wrote one, so `detail` must BE a sentence — never `str(e)`. A
caught exception's text belongs in the log; the response gets wording a member
can act on. 13 handlers were shipping a library's words (asyncpg naming tables,
GoTrue, botocore, eBay, a PIL "cannot identify image file <_io.BytesIO object at
0x…>") before 2026-09-17.

Two exceptions, both written down at the line:
* our OWN validators' messages, which are composed for the sender —
  `app/ssrf.validate_url` ("URL points to a private/internal IP address"),
  `s3_storage` ("content_type not allowed: image/tiff"), `warm_tier`
  ("limit too high — split into chunks");
* ops endpoints behind an ops key, where the reader is debugging.

Both carry `# raw-error-ok: <why>` above the line, and
`server/scripts/check_error_copy.py` (in `verify:prebuild`) fails anything else.
