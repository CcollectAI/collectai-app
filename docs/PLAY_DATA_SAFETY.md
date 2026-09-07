# Google Play — Data safety declaration

The Data safety form is **required to publish** and, unlike most of the
listing, it is a compliance statement: Play treats a mismatch between this form
and the app's real behaviour as a policy violation, not a typo. Apple's Privacy
Nutrition Labels ask nearly the same questions, so the answers below serve both.

Every row was derived from code and from the live database, not from memory.
The authoritative list of what we hold per user is
`server/app/routes/account_router.py::_ALLOWED_TABLES` — the same list account
deletion walks, kept honest by `server/scripts/audit_account_deletion.py`. If a
new table holding user data is added, the audit fails, and **this file is then
out of date too.**

## Global answers

| Question | Answer | Evidence |
|---|---|---|
| Is all user data encrypted in transit? | **Yes** | Every client call goes to `https://api.sparrowcollect.com` and `https://*.supabase.co`; no cleartext origin exists in `src/`. |
| Can users request that their data be deleted? | **Yes** | In-app: Settings → Delete Account. Web, no install needed: `https://sparrowcollect.com/delete-account`. Both call `DELETE /account`; verified end to end 10/10. |
| Do you have a data deletion URL? | `https://sparrowcollect.com/delete-account` | ⛔ Must be **live** before you submit the form — see the deploy caveat at the bottom. |
| Does the app follow the Families policy? | No — not targeted at children | Rating is set for a general audience. |
| Is data collected from an SDK you don't control? | Sentry, RevenueCat | Both declared below. |

## Data types — what to tick

"Collected" means transmitted off the device. "Shared" means passed to a
third party for their own use — our processors (Supabase, Sentry, RevenueCat)
are **not** "shared" under Play's definition, since they act on our behalf.

| Play data type | Collected | Shared | Purpose | Optional? | Where it lives |
|---|---|---|---|---|---|
| **Email address** | Yes | No | Account management | Required | Supabase `auth.users` |
| **Name** (display name / username) | Yes | No | Account management, App functionality | Required | `profiles` |
| **User IDs** | Yes | No | Account management | Required | UUID throughout |
| **Photos** | Yes | No | App functionality (item photos, scan-to-identify) | **Optional** | `item_images`, Supabase Storage |
| **Approximate location** | Yes | No | App functionality (Nearby Events) | **Optional** | Query only; rounded to 2 dp (~1.1 km) client-side in `src/api/eventsApi.ts`, held in an in-memory cache for 600 s, never written to a table |
| **Precise location** | **No** | No | — | — | Deliberately not transmitted — see below |
| **Other in-app messages** | Yes | No | App functionality (buyer/seller chat) | **Optional** | `chat_messages` |
| **Purchase history** | Yes | No | App functionality (collection value, DAC7 reporting) | **Optional** | `items.purchase_price`, marketplace sales |
| **Other user-generated content** | Yes | No | App functionality | **Optional** | `items`, `events`, `marketplace_listings`, reviews |
| **App interactions** | Yes | No | Analytics, App functionality | Required | `notification_impressions/_interactions/_outcomes`, `quickscan_history` |
| **In-app search history** | Yes | No | App functionality | **Optional** | `quickscan_history`, `on_demand_lookups_audit` |
| **Crash logs** | Yes | No | Diagnostics | Required | Sentry |
| **Diagnostics** | Yes | No | Diagnostics | Required | Sentry |
| **Device or other IDs** | Yes | No | App functionality (push delivery) | **Optional** | `user_push_tokens` (Expo push token) |

### Do NOT tick these — verified absent

- **Financial info › Payment info / Credit card.** We never see a card. Purchases go through Google Play Billing via RevenueCat. Purchase *history* is a separate type and is ticked above.
- **Contacts, SMS, Call logs, Health, Fitness, Web browsing history, Installed apps, Audio, Videos.** No API in the app touches any of them; `RECORD_AUDIO` is explicitly in `blockedPermissions`.
- **Calendar events.** `expo-calendar` writes event reminders to the device calendar and reads nothing back to us. Accessed on-device ≠ collected — do not tick it, but be ready to explain the permission if review asks.
- **Advertising ID.** No ads SDK is present; no manifest in `node_modules` declares `AD_ID` (checked).

### Precise location: why the answer is "No"

`expo-location` returns a precise fix, and the app takes one in two places.
Only one of them leaves the device as a *query*:

- `app/(tabs)/events.tsx` → `getNearbyEvents()` — **rounded to 2 dp at the API
  boundary** before it is sent. The server already rounded to 2 dp to build its
  cache key, and the search radius is 1–500 km, so the feature is unaffected.
- `src/hooks/useEventForm.ts` — sets the **venue** of an event the user is
  publishing. That is address data the user chose to share, not their
  whereabouts, and is correctly left precise.

⚠️ This answer depends on a second fix. Uvicorn's access log records the full
request path, so `GET /events/nearby?lat=..&lon=..` used to write coordinates
straight into `/opt/collectors/bake.log`. `server/app/logging_filters.py` now
redacts every query value that is not on a small allowlist — it **fails
closed**, so a future parameter cannot leak by being forgotten.
`server/tests/test_access_log_redaction.py` proves it, and was mutation-tested
(neutering the filter fails the two tests that matter). **If that filter is
ever removed, this declaration becomes false.**

**DEPLOYED and verified in production 2026-09-07 21:06** (all nine
ExecStartPre gates passed on the way up, healthz 200). Proven against the live
API rather than the test suite — a real request with distinctive coordinates,
then a grep of the log for them:

```
GET /events/nearby?lat=51.929123&lon=4.878456&radius_km=50   -> 200
occurrences of 51.929123 / 4.878456 in bake.log              -> 0
the access line actually written:
  "GET /events/nearby?lat=%3Credacted%3E&lon=%3Credacted%3E&radius_km=50" 200 OK
```

Keys stay readable, the allowlisted `radius_km` survives, the coordinates are
gone, and the endpoint still returns 200 — the feature is unaffected. The
structured JSON logger was already clean (it logs `"path"` without the query).

## Ads — the answer is "No", and it is provable

Play asks whether the app contains ads, and the answer decides whether an "Ads"
badge appears on the listing. `AdBanner` **is** mounted on the Items tab and
`src/ads/` is a complete abstraction, so the honest-looking answer is "yes" —
but three independent gates in `src/ads/useAds.ts` must all pass before a single
pixel renders, and two of them are off at the source:

| Gate | State | Evidence |
|---|---|---|
| `featureFlags.FEATURE_ADS` | **false** | `src/config/featureFlags.ts:165` |
| provider initialised | **never** | default provider is `NoOpAdProvider`; `initialize()` and `isInitialized()` both `return false` (`src/ads/provider.ts:64-72`) |
| user on the free plan | n/a | only reached if the two above pass |

There is also **no ad network SDK in the dependency tree at all** — the unit IDs
are `PLACEHOLDER_*` strings. So: **Contains ads = No.**

⚠️ Flipping `FEATURE_ADS` to true makes this answer, the privacy policy's
"dark" paragraph, and the Data safety form all wrong at once. Treat enabling
ads as a three-document change.

## Third parties

| SDK | Data | Why it is not "shared" |
|---|---|---|
| **Sentry** (`@sentry/react-native`) | Crash logs, diagnostics, user UUID | `sendDefaultPii: false`; `beforeSend` in `app/_layout.tsx` plus `src/lib/sentryScrub.ts` scrub PII. Only `Sentry.setUser({ id })` — the UUID, never the email. |
| **RevenueCat** (`react-native-purchases`) | Purchase/subscription state, an app user ID | Processor for entitlement checks; billing itself is Google Play. |
| **Supabase** | Everything above | Our database and auth host, acting on our instructions. |

## Before you submit the form

1. ⛔ **Deploy `web/`.** `https://sparrowcollect.com/delete-account` must return
   200 when Play checks it. `web/` has not been deployed since before
   2026-08-20 — the live AASA still lacks `/l/*`. See
   `docs/AUTH_AND_WEB_DEPLOY.md`.
2. Privacy policy URL: `https://sparrowcollect.com/privacy` (already live).
3. Re-run the deletion audit (needs `DB_DSN_DIRECT`; easiest on the box:
   `ssh collectai` then `cd /opt/collectors/server && set -a && . /opt/collectors/.env && set +a && /opt/collectors/.venv/bin/python scripts/audit_account_deletion.py`). If it
   reports a new table, a data type is probably missing from the table above.
4. Answer "Data collection" **per data type**, and remember Play asks
   *"Is this data required, or can users choose whether it's collected?"* — the
   **Optional** column above is the answer to that question.
