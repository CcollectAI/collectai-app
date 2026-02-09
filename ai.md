# CollectAI — AI-Driven Improvement Progress

All improvements implemented by Claude Code across multiple rounds.

---

## Round 1 — Codebase Audit & Initial Improvements (23 items, P0–P3)
- Pipeline infrastructure: import_common.py structured logging, shared HTTP session, IngestStats, validation
- import_all.py: SQLite checkpoint persistence (--resume), parallel execution (--parallel N)
- train_price.py: 5-fold CV alpha tuning, QuantileRegressor for q10/q90, --include-feedback flag
- model_loader.py: Canary deployment support (MODEL_CANARY_TRAFFIC_PCT env var)
- calibration_job.py: Gate thresholds from config/gate.yaml, Slack alerts on drift
- GH Actions: nightly-train-eval-gate.yml, nightly-ingest.yml
- DB migration: 20260209_canary_and_matviews.sql (is_canary, materialized views, calibration_snapshots)
- config/gate.yaml: Expanded to 20 categories with PICP/ACE thresholds

## Round 2 — Inference & API Cleanup
- **inference.py**: Supports ridge_v1 and ridge_v2; uses trained q10/q90 coefficients
- **explainer.py**: Accepts ridge_v2 model_type
- **routes.py**: Removed 10+ duplicate endpoints; replaced fake_model_predict() with real 3-tier inference (ridge → baseline → heuristic); added _load_model_artifact(), _attrs_to_features()
- **quickscan_advanced_router.py**: Dynamic feature extraction matching model's feature list
- **35 import scripts**: Bulk cleaned — removed local rarity_maps, print→logger, close_http_client()

## Round 3 — Tests, Frontend, Backend Gaps
- **SupabaseDataProvider.ts**: listItems/searchItems now JOIN price_predictions (q10/q50/q90/conf_score)
- **collectorsApi.ts**: Added predictV2() method
- **test_routes_predict.py**: 39 tests for prediction logic + condition matching bug fix (longest-match-first)
- **routes.py**: db_conn() context manager on all 19 endpoints; condition substring matching fix

## Round 4 — Security & Reliability
| File | Fix |
|------|-----|
| routes.py | Path traversal fix (tempfile.mkstemp for /ingest/photo) |
| routes.py | 12 bare `except: pass` → `logger.warning()` |
| routes.py | Input clamping on 5 market endpoints (since_days, limit, spike_pct, horizon_days, iqr_k) |
| 4 workers | try/finally for DB connection cleanup (alerts, valuation, signal, vision) |
| 10 files | `datetime.utcnow()` → `datetime.now(timezone.utc)` |
| model_loader.py | Deterministic canary routing (md5 hash of routing_key) |
| ci.yml | Removed `\|\| true` from pip install |

**Tests**: 97 across 3 files (inference 20, import_common 38, routes_predict 39) — all passing

## Round 5 — DB & ML Hardening
| File | Fix |
|------|-----|
| 20260209_missing_indexes.sql | 8 indexes: items(user_id,category), events(created_by), events(category,start_date), market_hits(normalized_key,ended_at), market_hits title trigram, user_price_alerts(user_id), price_predictions(item_id,asof), feedback(item_id) |
| Dockerfile | Non-root user (appuser:1000), HEALTHCHECK on /healthz |
| .dockerignore | Excludes .env, data/, artifacts/, node_modules, .git |
| app/db.py | Configurable pool: DB_POOL_MAX_SIZE (10), DB_COMMAND_TIMEOUT (30s), DB_CONNECT_TIMEOUT (10s), DB_MAX_IDLE_LIFETIME (300s) |
| train_price.py | Price validation (reject ≤0), outlier clipping (99.5th percentile), atomic model write (tempfile + os.replace) |
| inference.py | Coef length mismatch warnings for q50, q10, q90 |
| main.py | Global exception handler — logs full traceback, returns generic 500 to client |

## Round 6 — Security & Middleware
| File | Fix |
|------|-----|
| rate_limit.py | Real sliding-window rate limiter: 60 RPM/IP (RATE_LIMIT_RPM env), 429 with Retry-After header, exempt /healthz /version /ops/status |
| limit_body.py | Real body size limiter: 10MB default (MAX_BODY_BYTES env), 413 response |
| middleware_stack.py | Security headers: X-Content-Type-Options: nosniff, X-Frame-Options: DENY, Referrer-Policy, Permissions-Policy, X-XSS-Protection |
| collectorsApi.ts | 15s AbortController timeout, 2 retries with exponential backoff (500ms base) on 5xx/network errors |
| ci.yml | Added `black --check .` formatting step + `pytest --cov-fail-under=40` coverage threshold |
| train_price.py | Replaced 8 print() statements with logger.info/logger.error(exc_info=True) |
| .gitignore + git | Removed 16 tracked .env files (git rm --cached), expanded .gitignore patterns for env/.env*, functions.env, supa_test.env* |

## Round 7 — Input Validation & Logging
| File | Fix |
|------|-----|
| routes.py | File handle leak fix: `json.load(open(...))` → `with open(...) as f` |
| routes.py | 5 remaining silent exceptions now logged (env loading, float conversion, days_ago, quantile calc, import fallback) |
| routes.py | Specific exception types: `except (TypeError, ValueError, KeyError)` instead of bare `except Exception` |
| events_router.py | Pydantic Field validation: title max 255 chars, description max 5000, lat ge=-90 le=90, lng ge=-180 le=180, date regex YYYY-MM-DD, format enum |
| events_router.py | Silent RSVP exception → logger.warning |
| watchlist_router.py | `Field(default_factory=datetime.utcnow)` → `lambda: datetime.now(timezone.utc)` |
| provenance_router.py | Same datetime fix |
| alerts_feature_router.py | Same datetime fix |
| main.py | Filename sanitization: os.path.basename + regex whitelist, truncate to 100 chars |
| main.py | File size limits: 20MB for quickscan images, 50MB for CSV/Excel imports |
| logging_mw.py | Real request logger: method, path, status code, duration_ms (exempt health paths) |
| add.tsx | Removed duplicate null check (dead code at lines 89-91) |

---

## Test Summary
- **97 tests** across 3 test files, all passing
- test_inference.py: 20 tests (standardization, ridge v1/v2, quantiles, edge cases)
- test_import_common.py: 38 tests (rarity maps, condition maps, validation, IngestStats)
- test_routes_predict.py: 39 tests (feature extraction, prediction fallback, condition matching, normalization)

## Round 8 — Metrics, Categories, Logging Cleanup
| File | Fix |
|------|-----|
| app/metrics.py | Real metrics middleware: request count + duration per endpoint, /metrics endpoint in Prometheus text format (zero dependencies) |
| src/data/categories.ts | Added retro_handhelds (36th category) — now fully aligned with types/category.ts |
| pipelines/s3_image_cache.py | All 7 print() → logger.info/warning with proper formatting |
| pipelines/newsletter_scraper.py | `assert self._conn` → `raise RuntimeError(...)`, parsedate_to_datetime wrapped in try/except |
| 12 scripts/workers | **Zero `datetime.utcnow()` remaining** in entire codebase — all replaced with `datetime.now(timezone.utc)` |

## Round 9 — Tests, Bug Fixes & Code Quality
| File | Fix |
|------|-----|
| tests/conftest.py | Fixed broken import: `from app.main import app` → `from main import app` (tests now run without `--noconftest`) |
| routes.py | 2 remaining file handle leaks fixed: `json.load(open(path))` → `with open(path) as _f: json.load(_f)` at lines ~1062 and ~1183 |
| barcode_lookup_router.py | Missing null check: `_lookup_market_price()` now guards against `title=None` (prevents TypeError on `title[:40]`) |
| tests/test_rate_limit.py | **NEW** — 14 tests: _prune (8 tests: empty, within window, expired, mixed, cutoff boundary, order, scale), _client_ip (6 tests: direct IP, X-Forwarded-For single/multi/spaces, no client, IPv6) |
| tests/test_metrics.py | **NEW** — 13 tests: _looks_like_id (9 tests: UUID, hex, short, empty, boundary), _label (6 tests: basic, ID replacement, trailing slash, method/status, root, multi-segment), _render_metrics (4 tests: empty, data, newline, sort order) |
| tests/test_inference.py | **4 new tests** — coef mismatch warnings: q50 mismatch logs warning, empty cols/coef no warning, q10/q90 mismatch logs warning, matching coefs no warning |

**Tests**: 134 across 5 files (inference 24, import_common 38, routes_predict 39, rate_limit 14, metrics 13) — all passing

## Round 10 — Middleware Wiring, Proxy Hardening & Security
| File | Fix |
|------|-----|
| main.py | **BUG FIX**: `limit_body_middleware` was imported but **never wired** — body size limiting was not active! Now wired into middleware chain |
| main.py | **BUG FIX**: `ensure_metrics_once(app)` was never called — `/metrics` endpoint was never installed. Now active |
| main.py | Portfolio proxy endpoints: `r.raise_for_status()` moved inside httpx context manager; wrapped in try-except with 502/503 responses; DRY'd into `_proxy_signals()` helper |
| barcode_lookup_router.py | 2 bare `except Exception: pass` → `logger.debug()` for author/work lookup failures |
| photo_upload_router.py | Path traversal guard: reject `..` in photo_key before ownership check |
| photo_upload_router.py | 3 error detail leaks fixed: `detail=f"...{e}"` → generic messages (presign, delete, list endpoints) |

## Round 11 — Input Validation Expansion & Worker Hardening
| File | Fix |
|------|-----|
| feedback_router.py | Pydantic Field validation: item_id max 64, feedback_type max 50, value max 500, notes max 2000, corrected_condition max 100, corrected_category max 64 |
| feedback_router.py | 2 error detail leaks fixed: `detail=f"...{str(e)}"` → generic messages |
| provenance_router.py | OwnershipEventCreate: user_id min 1/max 255, event_type regex enum, note max 2000, source max 50 |
| watchlist_router.py | WatchlistCreate: name max 255, category max 64, item_id max 64, currency regex `^[A-Z]{3}$` |
| events_router.py | CreateEventRequest.kind: regex enum (collection_drop/meetup/stream/convention/release) |
| events_router.py | RsvpRequest.status: regex enum (going/interested/not_going) |
| events_router.py | FollowCategoryRequest.category_id: min 1 / max 64 |
| barcode_lookup_router.py | BarcodeLookupRequest: barcode min 1/max 50, code_type max 20 |
| alerts_evaluator.py | print→logger, try/finally for DB connection cleanup |
| alerts_watchlist.py | print→logger, added logging import |
| ingest_ebay_sold.py | print→logger, try/finally for DB connection cleanup |

## Round 12 — Logger Formatting, Worker Hardening & Import Cleanup
| File | Fix |
|------|-----|
| routes.py | 12 f-string logger calls converted to %-formatting: `logger.warning(f"...{x}")` → `logger.warning("...%s", x)` (deferred formatting, avoids unnecessary string interpolation) |
| main.py | Removed duplicate imports at lines 435-441 (already imported at top of file); consolidated import block |
| backfill_normalized_key.py | print→logger, try/finally for DB connection cleanup |
| build_fts_index.py | print→logger, added logging import, try/finally for load_recent_hits() |
| calibration_compute.py | print→logger, try/finally for DB conn, 2 file handle leaks fixed (`open().write()` → `with open()`) |
| capture_calibration.py | print→logger, added logging import |
| dedupe_hits.py | print→logger, try/finally for DB connection cleanup |
| ingest_bricklink.py | print→logger, added logging import |
| ingest_tcgplayer.py | print→logger, added logging import |
| alerts_watchlist.py | try/finally added to `recent_price_for()` (was already using try/finally in main()) |

---

## Cumulative Stats
- **134 tests** across 5 test files, all passing
- **12 rounds** of improvements
- **~90 files** modified
- **0** remaining `datetime.utcnow()` calls
- **0** remaining file handle leaks (`json.load(open(...))` pattern)
- **0** remaining silent `except: pass` blocks
- **0** remaining error detail leakage (`detail=f"...{e}"` patterns)
- **0** remaining `print()` in workers (all converted to `logger`)
- **0** remaining f-string logger calls in routes.py
- **36/36** categories in frontend categories.ts
- **All middleware** wired and active (rate limit, body limit, security headers, logging, metrics)
- **All Pydantic models** validated (events, feedback, provenance, watchlist, barcode)
- **All workers** use try/finally for DB connection cleanup

## Known Remaining Issues
1. **AUTH**: All feature routers use hardcoded "demo-user" — needs JWT validation before production
2. **RLS bypass**: Backend asyncpg connections bypass Supabase RLS policies
3. **Secret rotation**: .env files removed from git but tokens exposed in git history — rotate Supabase keys
4. **Test coverage gaps**: Feature routers (events, feedback, watchlist, etc.) lack dedicated tests
5. **Workers**: No retry logic or dead-letter handling
