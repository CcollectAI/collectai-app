# CollectAI — Pro Grade Improvement Plan

Updated 2026-02-12. Tracks all remaining work to take the app from MVP to production-ready.

---

## Status Key

- [ ] Not started
- [~] In progress
- [x] Complete

---

## Week 1 — Backend Infrastructure

### 1. CI/CD Pipeline
- [x] GitHub Actions workflow: lint (ruff) + pytest on every PR
- [x] Fail PR if tests fail or coverage drops below threshold
- [ ] Auto-deploy backend to EC2 on merge to main (SSH + docker compose)
- [ ] EAS Build config for Expo preview builds (future)

### 2. Healthz DB Check
- [x] `/healthz` should `SELECT 1` against the connection pool
- [x] Return `{"ok": false, "db": "down"}` with 503 when pool is dead
- [x] Add DB latency to response: `{"ok": true, "db_ms": 3}`

### 3. Structured Logging (JSON)
- [x] Configure logging_mw to output JSON format in production
- [x] Add `request_id` (UUID per request) via middleware (`app/request_id.py`)
- [x] Add `user_id` to log context where available (ContextVar in request_id.py, set in auth.py)
- [x] Keep human-readable format in DEV_MODE

### 4. File Handle Leaks (8 remaining)
- [x] All 8 files already use proper `with` context managers — verified clean

### 5. Bare Exception Cleanup (12+ remaining)
- [x] Fixed 8 handlers in 5 files (vision_s3_sanity, alert_delivery_worker, export_training, predictions_to_db)
- [x] 3 files already had specific exception types (train_ridge, migrate_logs, calibrate)

---

## Week 2 — API Scalability

### 6. API Pagination (all list endpoints)
- [x] Create shared `PaginationParams` dependency (`app/features/pagination.py`): `limit` (1-200, default 50) + `offset`
- [x] Add to `events_router.py` — GET /events
- [x] Add to `alerts_feature_router.py` — GET /alerts/mine, GET /trigger-history
- [x] Add to `watchlist_router.py` — GET /watchlist
- [x] Add to `feedback_router.py` — GET /feedback/corrections (new endpoint)
- [x] Add to `provenance_router.py` — GET /provenance/items/{id}
- [x] Frontend: `usePaginatedList` hook + infinite scroll on items, events, alerts (ActivityIndicator footer)

### 7. Response Caching (in-memory TTL)
- [x] Create `app/cache.py` with `@ttl_cache(seconds=N)` decorator
- [x] Cache taxonomy registry: 1 hr TTL (taxonomy_router /current + /categories)
- [x] Cache barcode lookups: 24 hr TTL (Open Library + Google Books results)
- [x] Add `Cache-Control` headers + `X-Cache: HIT/MISS` to taxonomy endpoints
- [x] Add `/ops/cache` stats endpoint for monitoring

### 8. Error Response Schema
- [x] Verified: all routers already use generic detail messages — no `str(e)` leaks found
- [x] Create standard `ErrorResponse` model: `app/errors.py` with `ErrorResponse` + `error_response()` helper

---

## Week 3 — User-Facing Reliability

### 9. Push Notifications
- [x] Backend: `user_push_tokens` table migration (`20260211_push_tokens.sql`)
- [x] Backend: `POST /notifications/register` + `DELETE /register` + `GET /tokens` endpoints
- [x] Backend: `send_push()` + `send_push_to_user()` helpers (`app/push.py`) using Expo Push API
- [x] Workers: alerts_worker calls `send_push_to_user()` when firing alerts
- [x] Frontend: `src/hooks/usePushNotifications.ts` — permission request + token registration
- [x] Frontend: `registerForPushNotificationsAsync` + auto-register to backend on auth resolve
- [x] Frontend: notification tap handler → navigates to `/item/[id]` or `/events/[eventId]`

### 10. Crash Reporting (Sentry)
- [x] Add `sentry-sdk[fastapi]==2.22.0` to requirements.txt
- [x] Backend: `sentry_sdk.init()` in main.py with DSN from env (guarded import)
- [x] Backend: request_id tagged on every Sentry event via request_id_middleware
- [x] Add `@sentry/react-native` ^6.5.0 to package.json
- [x] Frontend: Sentry.init() in app/_layout.tsx (guarded require, DSN from env)
- [x] Wire `ErrorBoundary.componentDidCatch` to `Sentry.captureException`
- [x] Add Sentry user context (user_id) on login via `useAuth.ts`

### 11. Pin All Dependencies
- [x] All 19 Python dependencies pinned with `==` in requirements.txt
- [x] `bandit` + `pip-audit --strict` already in CI workflow
- [x] Add `npm audit` check to CI (`frontend-audit` job: Node 20, npm ci, npm audit --audit-level=moderate)

---

## Week 4 — UX Polish (no visual changes without approval)

### 12. SQLite Offline Cache
- [x] `src/data/offlineCache.ts` — expo-sqlite cache with TTL, get/set/clear/evict
- [x] `src/data/CachedDataProvider.ts` — stale-while-revalidate wrapper for all list endpoints
- [x] Cache: listItems (5m), portfolio (2m), watchlist (2m), alerts (5m), categories (15m), events (15m)
- [x] `src/hooks/useNetworkStatus.ts` — online/offline detection (no visual banner yet — needs approval)
- [x] Cache invalidation: wired on create/delete/archive/rsvp/watchlist mutations

### 13. Optimistic Updates
- [x] `useOptimisticMutation.ts` — generic hook (mutate, rollback, reconcile)
- [x] `archiveItem()` + `deleteItem()` — bulk ops in items tab, instant remove + reload rollback
- [x] `rsvpEvent()` — toggle attendance in list + detail screens
- [x] `createItem()` — temp ID → server ID reconciliation hook (exported, ready to wire)
- [ ] Show undo toast on destructive actions (needs UI approval)

### 14. Database Migrations
- [x] `scripts/migrate.py` — custom asyncpg migration runner (no external deps)
- [x] Auto-creates `schema_migrations` table, scans `supabase/migrations/*.sql`
- [x] Transaction-per-migration, strips existing BEGIN/COMMIT, rollback on failure
- [x] CLI flags: `--status`, `--dry-run`, `--target VERSION`
- [x] Deploy integration: commented deploy job in ci.yml showing where migrate runs

### 15. Image Optimization
- [x] 12 components migrated from RN Image → expo-image with `cachePolicy="disk"`
- [x] `app/lib/image_optimizer.py` — resize to 1200px max, JPEG q85, strip EXIF
- [x] `generate_blurhash()` — pure-Python fallback + optional blurhash lib
- [x] `POST /photos/upload` — server-side optimize + blurhash, returns cdn_url + blurhash + dimensions

---

## Ongoing — Maintenance & Quality

### 16. Frontend Tests
- [x] Add Jest + React Native Testing Library + jest-expo to devDependencies
- [x] Update package.json `"test"` script to `jest --passWithNoTests`
- [x] 3 starter test files: ItemCard (5), useNetworkStatus (5), offlineCache (6) = 16 tests
- [ ] Test critical flows: barcode scan, search filtering
- [ ] Test DataProvider: mock vs Supabase switching
- [ ] Target: 30% frontend coverage initially

### 17. API Versioning
- [x] Add `/v1/` prefix to all router includes in main.py (21 routers aliased under _v1)
- [x] Keep unversioned routes as aliases (backward compat for 1 release)
- [ ] Document deprecation timeline

### 18. Worker Scheduling
- [x] Created `app/worker_registry.py` with `record_run()` + `get_status()` (in-memory, with overdue detection)
- [x] Schedule intervals: price_monitor (6h), alerts (1h), vision_ingest (on-demand), valuation (6h)
- [x] Add worker health endpoint: `GET /ops/worker-status`
- [x] Log last-run timestamps (wired into alerts_worker + valuation_worker)

### 19. Deep Linking
- [x] Configure `collectai://` scheme in app.json + iOS bundleIdentifier + Android intentFilters
- [x] `public/.well-known/apple-app-site-association` + `assetlinks.json` (need Team ID + signing key)
- [x] Routes already handle params via Expo Router file-based routing
- [x] `src/utils/deepLink.ts` — getItemShareUrl() + getEventShareUrl()

### 20. Security Hardening
- [x] Add `bandit -r app/` SAST to CI (already in .github/workflows)
- [x] Add Trivy Docker image scanning to CI (docker-scan job, HIGH+CRITICAL, main only)
- [ ] Rotate all Supabase keys (anon key, service role key)
- [ ] Move secrets to AWS Secrets Manager or similar vault
- [x] SSRF protection: `app/ssrf.py` + wired into intake `/url` endpoint with 2 tests
- [x] Per-user rate limits: intake (30/min) + vision (20/min) via sliding-window in `app/rate_limit.py`

### 21. Code Quality Cleanup
- [x] Replace 260+ print statements in scripts/ops/pipelines with logger (all 3 dirs done)
- [x] Fix 200+ TypeScript `any` types in frontend (hooks, lib, screens, components, app/ all done)
- [x] Gate 3 demo screens behind `__DEV__` + vision_debug_router behind DEV_MODE
- [x] Delete .bak files, add `*.bak*` to .gitignore (verified: already clean + already in .gitignore)
- [x] Remove duplicate ErrorBoundary in `src/ui/` (verified: no duplicate exists, single def in src/components/)
- [x] Consolidate duplicate API key definitions → new `app/config.py` (central config, 14 backend files + 3 frontend files updated)
- [x] Triage 15+ TODO/FIXME comments → 2 stale removed, 13 legitimate kept

### 22. Test Coverage
- [x] Added tests for: ssrf (42), errors (16), worker_registry (13), push (13), cache (21), rate_limit (10) = 115 new tests
- [x] Added tests for: intake_agent (17), marketplace_agent (30), dossier_agent (24), notification_router (11), image_optimizer (25), predict_router (15) = 122 new tests
- [x] Test count: 452 → 689 passing
- [ ] Add tests for remaining feature routers
- [ ] Increase coverage threshold: 40% → 50% → 60% → 70%
- [ ] Add integration tests for critical DB flows

### 23. Accessibility
- [x] Add accessibilityLabel to all Pressable and icon-only buttons (14 elements across 12 files)
- [x] Add accessibilityRole to all interactive elements (button, checkbox roles)
- [ ] Test with VoiceOver (iOS) and TalkBack (Android)
- [ ] Ensure minimum 4.5:1 contrast ratio on all text

---

## Round 15 — Hardening + Geo-Aware Currency (2026-02-12) ✅ COMPLETE

### R15-1. SECURITY: DEV_MODE production guard
- [x] Added `validate_config()` in `app/config.py` — hostname check blocks DEV_MODE on non-local hosts
- [x] `FORCE_DEV_MODE` escape hatch for CI/staging
- Files: `app/config.py`, `main.py`

### R15-2. SECURITY: Startup env validation
- [x] `validate_config()` fails fast if `SUPABASE_JWT_SECRET` or `DB_DSN` empty in non-DEV mode
- [x] Warn-only for optional keys: `EBAY_CLIENT_ID`, `OPENAI_API_KEY`, `FAL_KEY`, `TCGPLAYER_BEARER_TOKEN`, `AWS_ACCESS_KEY_ID`
- [x] Wired into `main.py` startup event
- [x] Fixed bare `except` in `app/auth.py` (split into ImportError + Exception with type logging)

### R15-3. GEO-AWARE MULTI-CURRENCY & REGIONAL PRICING
- [x] `src/lib/format.ts`: `formatPrice(amount, currency?, locale?)` — supports EUR, USD, JPY, GBP
- [x] `src/lib/fx.ts`: `convertCurrency()` for any-to-any conversion via EUR pivot
- [x] `src/lib/settings.tsx`: `Currency`, `Region`, `NumberLocale` types + `REGION_DEFAULTS` mapping
- [x] All 23 files with inline `formatCurrency` / `Intl.NumberFormat` replaced with `formatPrice()`
- [x] User geolocation opt-in: Americas→USD, Europe→EUR, Japan→JPY, other→EUR
- [x] Backend: `user_settings` table (currency, region, locale) + `user_settings_router.py` (GET/PUT)
- [x] Migration: `20260212_performance_indexes_and_user_settings.sql` with RLS + CHECK constraints
- [x] Market adapters preserve `source_price` + `source_currency` in MarketHit dicts
- [ ] **REMAINING**: Live FX rate API integration (currently uses static fallback rates)
- [ ] **REMAINING**: Regional market price comparison (same item, different regions)
- [ ] **REMAINING**: Delivery time/shipping cost factor in portfolio valuation
- [ ] **REMAINING**: Cross-region availability flag display

### R15-4. BACKEND: Exception handling cleanup
- [x] Replaced bare `except Exception` with specific types in 8 routers:
  - photo_upload_router, marketplace_router, insights_router, alerts_feature_router,
  - marketplace_trust_router, feedback_router, notification_router, provenance_router
- [x] All use `asyncpg.PostgresError`, `httpx.RequestError`, `BotoCoreError`, `ClientError` as appropriate

### R15-5. BACKEND: Consistent error response codes
- [x] All 8 routers adopted `error_response()` with machine-readable codes
- [x] Codes: `DB_ERROR`, `AUTH_FAILED`, `VALIDATION_ERROR`, `EXTERNAL_API_ERROR`, `UPLOAD_ERROR`

### R15-6. DATABASE: Performance indexes migration
- [x] Migration: `20260212_performance_indexes_and_user_settings.sql`
- [x] `alert_trigger_history(user_id, trigger_type, created_at DESC)`
- [x] `item_provenance_events(user_id, event_type, created_at DESC)`
- [x] `user_settings` table with PK, RLS, CHECK constraints, updated_at trigger

### R15-7. WORKERS: Idempotency keys
- [x] `alerts_worker.py`: 24h dedup check before INSERT into alert_trigger_history
- [x] `vision_ingest_worker.py`: `FOR UPDATE SKIP LOCKED` to prevent double-processing
- [x] `price_monitor_worker.py`: already had `_already_fired()` dedup (verified)

### R15-8. WORKERS: Circuit breaker for external APIs
- [x] `workers/circuit_breaker.py`: CLOSED→OPEN (5 failures)→HALF_OPEN (60s cooldown)
- [x] Pre-configured: `ebay_circuit`, `tcgplayer_circuit`, `openai_circuit`
- [x] Wired into `ebay_caller.py` and `tcgplayer_caller.py` (check/record_success/record_failure)
- [x] `/ops/circuits` monitoring endpoint in main.py

### R15-9. DEPS: psycopg2 review
- [x] Verified: `psycopg2-binary==2.9.11` is current stable (NOT EOL). No change needed.

### R15-10. DEPS: pip-audit in CI
- [x] Added `pip-audit --strict` step to `.github/workflows/sanity.yml`

### R15-11. ML: Vision model version tracking
- [x] Added `model_version: Optional[str]` to `ClassificationResult` dataclass
- [x] Set in all 4 creation sites: CLIP (`clip:fal-ai/clip@{url}`), OpenAI (`openai:{model}`), heuristic (`heuristic:v1`)

### R15-12. TESTS: Fill coverage gaps
- [x] `tests/test_circuit_breaker.py` — 31 tests (state machine, transitions, reset, global circuits, edge cases)
- [x] `tests/test_config_validate.py` — 25 tests (DEV_MODE guard, FORCE_DEV_MODE, required vars, config constants)
- [x] `tests/test_worker_idempotency.py` — 16 tests (alerts dedup, SKIP LOCKED verification, SQL structure)
- [x] Total: 72 new tests, all passing

### R15 Audit Findings (2026-02-12)

**Security audit** (1 CRITICAL, 4 HIGH, 6 MEDIUM, 6 LOW):
- [ ] **C-1/H-2**: Add URL validation to `_fetch_image_url()` — block private IPs, restrict schemes (SSRF risk)
- [ ] **H-3**: Add auth to `/ops/*` endpoints (circuits, cache, worker-status)
- [ ] **M-4**: Fix `FOR UPDATE SKIP LOCKED` — wrap SELECT+UPDATE in same transaction, or use "claim then process" pattern
- [ ] **L-4**: Fix partial-update logic in `user_settings_router.py` — preserve existing DB values for non-provided fields

**Performance audit** (3 HIGH, 6 MEDIUM, 7 LOW):
- [ ] **P-HIGH**: Cache `Intl.NumberFormat` instances in `format.ts` (Map by locale+currency key, max 16 entries)
- [ ] **P-HIGH**: Batch alerts_worker N+1 queries (JOIN instead of per-item SELECT, reduces 151→2 queries)
- [ ] **P-HIGH**: Fix vision_ingest_worker transaction scope — "claim then process" pattern for correct concurrency
- [ ] **P-MED**: TCGPlayer `sold_comps()` makes redundant `search()` call (3 HTTP requests → 2)
- [ ] **P-MED**: Share httpx.AsyncClient across image fetches in vision batch

**Test coverage gaps** (5 files at 0% coverage):
- [ ] `app/routes/user_settings_router.py` — P1: 13 test cases needed
- [ ] `app/agents/adapters/ebay_caller.py` — P1: 11 test cases (circuit breaker integration)
- [ ] `app/agents/adapters/tcgplayer_caller.py` — P1: 11 test cases (+ 429 handling bug)
- [ ] `src/lib/format.ts` — P2: 12 test cases (formatPrice/formatNumber)
- [ ] `src/lib/fx.ts` — P2: 8 test cases (convertCurrency)

---

## Previously Completed (Rounds 1-14 + Hardening)

- [x] All 6 agentic layers implemented
- [x] Evidence-native valuation pipeline
- [x] Intake agent (barcode → vision fallback)
- [x] Dossier factory + HTML export
- [x] JWT auth on all routers
- [x] Worker retry/dead-letter on all workers
- [x] Metrics + telemetry endpoints
- [x] Rate limiting middleware
- [x] CORS + security headers
- [x] Error boundary component
- [x] 761 backend tests passing (was 689, now +72 from R15)
- [x] Bulk archive (archiveItem, not deleteItem)
- [x] Alert threshold validation (Literal types + bounds)
- [x] Transaction boundaries on marketplace + vision worker
- [x] Auth on barcode lookup endpoint
- [x] alerts_worker.py fixed (correct schema)
- [x] get_optional_user_id for anonymous-accessible endpoints
- [x] Hardcoded color fixes on main tab screens
