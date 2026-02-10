# CollectAI — Improvement Plan (Post ai.md Audit)

Comprehensive audit of the codebase after 12 rounds of improvements documented in `ai.md`.
Generated 2026-02-10 by Claude Code.

---

## Executive Summary

Despite 12 rounds of improvements, **significant gaps remain** across backend, frontend, tests, and CI/CD. The `ai.md` doc focused primarily on `app/` and `main.py` but left `scripts/`, `ops/`, `services/`, and `pipelines/` largely untouched. The frontend has accumulated substantial tech debt including 24+ demo screens, 200+ `any` types, and hardcoded secrets.

---

## CRITICAL (P0) — Fix Before Any Production Use

### 1. Hardcoded Secret in Source Code
- **File:** `src/api/marketplace.ts`
- **Issue:** `const API_KEY = process.env.EXPO_PUBLIC_API_KEY ?? "dev-local-secret-collectai";` — secret string as fallback
- **Fix:** Remove fallback, fail explicitly if env var missing

### 2. Hardcoded EC2 IP + Unencrypted HTTP
- **File:** `src/api/config.ts`
- **Issue:** `http://3.75.182.41:8000` hardcoded, uses HTTP not HTTPS
- **Fix:** Use environment variable only, enforce HTTPS, add domain name

### 3. Exception Detail Leaks in HTTP Responses (9 endpoints)
- **File:** `app/features/events_router.py` (lines 175, 265, 343, 397, 428, 461, 495, 526, 557)
- **File:** `main.py` (line 514)
- **Issue:** `detail=f"Failed to ...: {str(e)}"` exposes internal error messages to clients
- **Fix:** Replace with generic messages, log `e` server-side only

### 4. AUTH — Hardcoded "demo-user" (Known, Still Open)
- **Files:** 8+ feature routers + `main.py` + frontend stores
- **Issue:** All feature routers use hardcoded `"demo-user"` instead of JWT-authenticated user
- **Fix:** Implement JWT validation middleware, extract user from token

### 5. Secret Rotation
- **Issue:** `.env` files removed from git but tokens still in git history
- **Fix:** Rotate all Supabase keys, API keys, and AWS credentials

---

## HIGH (P1) — Fix Before Beta

### 6. File Handle Leaks (8 remaining instances)
| File | Line | Pattern |
|------|------|---------|
| `services/collectors_merge/scripts/export_insurance_pdf.py` | 12 | `json.load(open(in_path))` |
| `scripts/db_migrate.py` | 19 | `open(f).read()` |
| `scripts/export_training_and_trigger.py` | 199 | `open(meta_path, "w").write(...)` |
| `ops/embed_backlog.py` | 7 | `[json.loads(x) for x in open(...)]` |
| `ops/eval/precision_at_k.py` | 12 | `open(...)` without close |
| `ops/batch_predict.py` | 29 | `out=open(OUT,"a")` without exception safety |
| `scripts/jsonl_tools.py` | 19 | Manual close, no exception safety |
| `ops/make_predictions_from_s3.py` | 40 | `open(local, "rb")` in dict |

**Fix:** Wrap all in `with open(...) as f:` context managers.

### 7. Bare Exception Patterns (12+ remaining)
| File | Lines |
|------|-------|
| `ops/vision_s3_sanity.py` | 17 |
| `scripts/train_ridge_versioned.py` | 30 |
| `scripts/migrate_logs_to_sqlite.py` | 28 |
| `scripts/alert_delivery_worker.py` | 77 |
| `scripts/export_training_and_trigger.py` | 180, 189 |
| `scripts/calibrate_confidence.py` | 24, 35 |
| `pipelines/s3_image_cache.py` | 252 |
| `main.py` | 387, 537 |
| `ops/predictions_to_db.py` | 23 |

**Fix:** Replace bare `except:` with specific types (`except (ValueError, KeyError, json.JSONDecodeError):`), add logging.

### 8. Unpinned Dependencies
- **File:** `requirements.txt`
- **Issue:** 24/26 dependencies have no version pins (fastapi, numpy, scikit-learn, asyncpg, etc.)
- **Fix:** Pin all to exact versions or use Poetry lockfile

### 9. 68 Untested Endpoints Across 13 Feature Routers
| Router | Endpoints | Priority |
|--------|-----------|----------|
| events_router.py | 19 | HIGHEST |
| alerts_feature_router.py | 6 | HIGH |
| barcode_lookup_router.py | 6 | HIGH |
| photo_upload_router.py | 6 | HIGH |
| watchlist_router.py | 6 | HIGH |
| trends_and_deepdive_router.py | 6 | MEDIUM |
| quickscan_advanced_router.py | 5 | MEDIUM |
| feedback_router.py | 4 | MEDIUM |
| insights_router.py | 4 | MEDIUM |
| marketplace_trust_router.py | 4 | LOW |
| provenance_router.py | 4 | LOW |
| items_export_router.py | 2 | LOW |
| screenshot_intel_router.py | 2 | LOW |

**Fix:** Write test files for each router, prioritize by user-facing importance.

### 10. Inconsistent Python Versions in CI
- `ci.yml` uses Python 3.12
- `nightly-train-eval-gate.yml` and `nightly-ingest.yml` use Python 3.11
- **Fix:** Standardize to 3.12 across all workflows

---

## MEDIUM (P2) — Improve Before Public Release

### 11. Print Statements (260+ remaining)
- **Dirs affected:** `scripts/` (~80), `ops/` (~50), `pipelines/` (~40), `services/` (~15), `pipelines/newsletter_scraper.py` (~30)
- **Fix:** Replace with `logger.info()` / `logger.warning()` for proper structured logging

### 12. Frontend — 200+ `any` Types
- **Dirs affected:** `src/screens/`, `src/components/`, `src/cache/`, `src/haptics/`, `src/ui/`
- **Fix:** Replace `any` with proper TypeScript interfaces, especially for navigation props, API responses

### 13. Frontend — 40+ Console Statements in SupabaseDataProvider
- **File:** `src/data/SupabaseDataProvider.ts`
- **Fix:** Replace with proper error reporting service (Sentry/Crashlytics)

### 14. Frontend — 30+ Console Statements Across Screens
- **Files:** `app/search-status.tsx`, `app/item-status-debug.tsx`, `app/wishlist.tsx`, `app/chat/[threadId].tsx`, `app/(tabs)/index.tsx`, `app/(tabs)/add.tsx`, `app/(tabs)/items.tsx`, etc.
- **Fix:** Replace with error boundary catches + reporting service

### 15. Duplicate ErrorBoundary Components
- `src/ui/ErrorBoundary.tsx` (20 lines, uses `any`)
- `src/components/ErrorBoundary.tsx` (184 lines, properly typed)
- **Fix:** Delete `src/ui/ErrorBoundary.tsx`, use the `src/components/` version everywhere

### 16. Duplicate API Key Definitions
- `src/config/api.ts`: `export const API_KEY = process.env.EXPO_PUBLIC_API_KEY ?? '';`
- `src/api/marketplace.ts`: `const API_KEY = process.env.EXPO_PUBLIC_API_KEY ?? "dev-local-secret-collectai";`
- **Fix:** Single source of truth in `src/config/api.ts`, import elsewhere

### 17. No Security Scanning in CI
- **Missing:** bandit (Python SAST), pip-audit (CVE scanning), Trivy (Docker image scanning)
- **Fix:** Add `bandit -r app/` and `pip-audit` steps to `ci.yml`

### 18. Test Coverage Threshold Too Low
- **Current:** `--cov-fail-under=40`
- **Target:** 70% minimum
- **Fix:** Increase incrementally as tests are added (50 → 60 → 70)

### 19. Backend Python Files Mixed in React Native `app/` Directory
- **Files:** `app/db.py`, `app/limit_body.py`, `app/logging_mw.py`, `app/middleware_stack.py`, `app/rate_limit.py`, `app/metrics.py`
- **Issue:** Expo/Metro bundler may error on `.py` files in the app directory
- **Fix:** Move backend to a separate `backend/` or `server/` directory, or ensure `.py` excluded from bundler

---

## LOW (P3) — Nice to Have

### 20. 24+ Demo/Debug Screens Still in `app/`
- Files: `add-v2-demo.tsx`, `alerts-debug.tsx`, `analytics-metrics-debug.tsx`, `analytics-supabase-demo.tsx`, `backend-debug.tsx`, `calendar-add-event-demo.tsx`, `calendar-event-detail-demo.tsx`, `calendar-v1-demo.tsx`, `item-card-demo.tsx`, `item-detail-v2-demo.tsx`, `item-status-debug.tsx`, `items-supabase-demo.tsx`, `portfolio-hover-demo.tsx`, `portfolio-v2-demo.tsx`, `search-status.tsx`, `watchlist-v1-demo.tsx`, `wishlist-v1-demo.tsx`, `add-anti-fraud-debug.tsx`, etc.
- **Fix:** Move to `app/__dev__/` or delete; gate behind `__DEV__` flag

### 21. Backup Files in Version Control
- `app/_layout.tsx.bak`, `app/_layout.tsx.bak_20251213_180919`, `app/_layout.tsx.pre_fix_20251213_182150`, `app/build-paint-projects.tsx.bak`, `app/twitch.tsx.bak_20251213_201600`, etc.
- **Fix:** Delete all `.bak*` files, add `*.bak*` to `.gitignore`

### 22. TODO/FIXME Comments (15+ across codebase)
- Backend: `items_export_router.py`, `trends_and_deepdive_router.py`, `events_router.py`, `marketplace_trust_router.py`, `alerts_feature_router.py`, `insights_router.py`, `run_nightly.py`
- Frontend: `users/[userId].tsx`, `src/storage/objectStore.ts`, `src/screens/Settings.tsx`, `src/hooks/useAlertsFeed.ts`
- **Fix:** Triage each — resolve or convert to GitHub issues

### 23. Accessibility Gaps
- Only 22 `accessibilityLabel` props across 66+ screens
- Missing `accessibilityRole` on interactive elements
- **Fix:** Add labels to all Pressable, TextInput, and icon-only buttons

### 24. Dynamic `require()` Calls in React Screens
- **File:** `app/(tabs)/index.tsx` lines 44-60
- Uses `require()` wrapped in try/catch with `any` typing
- **Fix:** Use static imports with proper TypeScript types

### 25. mypy Config Too Permissive
- Disables: `no-untyped-def`, `no-untyped-call`, `no-any-return`, `type-arg`, `call-arg`, `return-value`, `misc`
- Large exclude list (tests, middleware, ML, providers, etc.)
- **Fix:** Gradually enable error codes, reduce exclude list

### 26. No Pre-commit Hooks
- **Fix:** Add `.pre-commit-config.yaml` with black, ruff, mypy checks

### 27. No CODEOWNERS File
- **Fix:** Create `.github/CODEOWNERS` for review routing

### 28. Workers Lack Retry/Dead-letter Handling (Known, Still Open)
- All 4 workers (alerts, valuation, signal, vision) have no retry logic
- **Fix:** Add exponential backoff + dead-letter queue for failed jobs

---

## Scoreboard

| Severity | Count | Category |
|----------|-------|----------|
| **P0 Critical** | 5 | Secrets, auth, error leaks |
| **P1 High** | 5 | File leaks, bare excepts, unpinned deps, untested endpoints, CI inconsistency |
| **P2 Medium** | 9 | Print cleanup, TypeScript quality, duplicate code, security scanning, coverage |
| **P3 Low** | 9 | Demo screens, backups, TODOs, accessibility, config |
| **Total** | **28** | |

---

## Suggested Execution Order

1. **Week 1:** P0 items 1-3 (secrets, HTTPS, error leaks) — security critical
2. **Week 2:** P1 items 6-8 (file leaks, bare excepts, pin deps) — reliability
3. **Week 3:** P1 item 9 (router tests, start with events_router) — coverage
4. **Week 4:** P2 items 11-14 (print/console cleanup) — observability
5. **Ongoing:** P2-P3 items as capacity allows

---

## ai.md Accuracy Notes

The `ai.md` doc's "Cumulative Stats" section claims:
- "0 remaining file handle leaks" → **FALSE** (8 found in scripts/ops/)
- "0 remaining silent except: pass blocks" → **FALSE** (12+ in scripts/ops/)
- "0 remaining print() in workers" → **PARTIALLY TRUE** (workers cleaned, but 260+ prints remain in scripts/ops/pipelines)
- "0 remaining f-string logger calls in routes.py" → **TRUE** for routes.py specifically
- "All middleware wired and active" → **TRUE** (fixed in Round 10)

The discrepancy is because ai.md rounds focused on `app/` and `main.py` but did not cover `scripts/`, `ops/`, `services/`, or the frontend codebase.
