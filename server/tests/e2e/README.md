# Live E2E test suite

Real-DB / real-HTTP audit scripts. Every script:
1. Mints one or two ephemeral users via the Supabase admin API (`/auth/v1/admin/users`)
2. Logs in to get a real JWT
3. Hits live endpoints on `BASE = http://localhost:8000`
4. Asserts response shape / status code
5. Cleans up users + any DB rows it created

Unlike `server/tests/test_*.py` (which mock asyncpg), these run against the real bake service against the real DB. They're the only thing that catches schema drift, RLS gaps, async-coercion bugs, and missing dependencies — see `learnings.md` 2026-04-22 for the full backstory.

## Running

Locally / on EC2 — bake service must be up at `http://localhost:8000`:

```bash
cd /opt/collectors/server
set -a && source /opt/collectors/.env && set +a
sudo -E -u ubuntu /opt/collectors/.venv/bin/python tests/e2e/run_all.py
```

Required env vars (already in EC2 `.env`):
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_SERVICE_KEY`)
- `SUPABASE_ANON_KEY` (or `SUPABASE_KEY`)
- `DB_DSN_DIRECT` (or `DB_DSN`) — for cleanup queries

## Inventory (15 scripts)

### Feature flows (today, 2026-04-22)
| Script | Coverage | Endpoints | Purpose |
|---|---|---|---|
| `e2e_chat.py` | DM thread | 7 | Send / list / read / mark / edit / delete |
| `e2e_deal_desk.py` | Offer negotiation | 6 | Propose / counter×2 / accept / list / detail |
| `e2e_deal_desk_full.py` | Ship + complete | 5 | Propose / accept / ship / complete + rate / detail |
| `e2e_deal_desk_edges.py` | Deal edges | 5 | History / evidence / reputation / risk-flags / for-sale |
| `e2e_user_writes.py` | Items + watchlist + scan | 5 | Add / edit attrs / watchlist add / scan / delete |
| `e2e_user_writes2.py` | Settings + notifs + photos | 6 | Beta-signup / alert-prefs / push register / notif prefs / mark-read / photo presign |
| `e2e_billing.py` | Stripe | 3 | Checkout / portal / validation |
| `e2e_events_social.py` | Events + social | 6 | Create / RSVP / follow / unfollow / block / unblock |
| `e2e_marketplace.py` | Marketplace | 5 | Search / fees / listing CRUD |
| `e2e_misc.py` | Sets + sponsor | 5 | Set progress add/remove / sponsor company CRUD |
| `e2e_summary_notif.py` | Notifs read paths | 3 | Value summary / notifications list / unread-count |

### Pre-existing (R50m, prior sessions)
| Script | Coverage |
|---|---|
| `e2e_v2.py` | Pro features (price-trend / dossier / provenance / marketplace) |
| `e2e_bulk.py` | Bulk version of e2e_v2 across all 55 categories |
| `e2e_pro_features.py` | Older pro-features sweep |
| `e2e_analytics.py` | Analytics endpoints |

## Adding a new test

Copy `e2e_misc.py` as a template — it shows the canonical pattern (admin_create_user, login, hit endpoints, cleanup, results table). Keep tests under ~150 LOC each; a single bake feature per file.

## CI integration (TODO)

These should run as a CI job on every PR. Blocked on:
- A non-prod Supabase project (so test users don't pollute the real auth.users table)
- A non-prod DB schema mirror

For now, run them manually after a deploy via `tests/e2e/run_all.py`.

## Known limitations

- Each script creates its own test user; concurrent runs of the same script will hit the "user already exists" branch and reuse the same uid (safe but slower).
- Rate limits will start firing if all 15 scripts run within the same per-user window (~30s). The runner inserts a 5s pause between scripts.
- `e2e_marketplace.py` runs a real aggregate scrape that takes 30-90s.
