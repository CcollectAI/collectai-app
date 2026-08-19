# Deployment Guide

## Prerequisites

- Python 3.12+
- Node.js 20+
- Docker (for containerized deployment)
- Supabase project with PostgreSQL
- AWS account (for S3 image storage and EC2 hosting)
- Domain name pointing to EC2 (e.g. `api.sparrowcollect.com`)

## Environment Variables

Copy `.env.example` to `.env` and fill in all values:

```bash
cp .env.example .env
```

### Required Variables (Production)

| Variable | Description | How to get |
|----------|-------------|------------|
| `DB_DSN` | PostgreSQL connection string | Supabase Dashboard > Settings > Database > Connection string |
| `SUPABASE_URL` | Supabase project URL | Supabase Dashboard > Settings > API > URL |
| `SUPABASE_KEY` | Supabase anonymous key | Supabase Dashboard > Settings > API > anon key |
| `SUPABASE_SERVICE_KEY` | Supabase service role key | Supabase Dashboard > Settings > API > service_role key |
| `SUPABASE_JWT_SECRET` | JWT secret for token validation | Supabase Dashboard > Settings > API > JWT Secret |
| `SUPABASE_JWT_ISSUER` | JWT issuer (e.g. `https://<project>.supabase.co/auth/v1`) | Your Supabase auth URL |
| `OPS_API_KEY` | Ops endpoint access key | Generate: `openssl rand -hex 32` |
| `API_SHARED_SECRET` | Inter-service API key | Generate: `openssl rand -hex 32` |
| `AWS_ACCESS_KEY_ID` | AWS access key for S3 | AWS IAM console |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for S3 | AWS IAM console |

### Required for Production Security

| Variable | Example | Description |
|----------|---------|-------------|
| `DEV_MODE` | `false` | **Must be false in production** |
| `DB_ENABLED` | `true` | Enable database connections |
| `CORS_ORIGINS` | `https://app.sparrowcollect.com,https://sparrowcollect.com` | Comma-separated allowed origins |
| `TRUSTED_HOSTS` | `api.sparrowcollect.com,sparrowcollect.com` | Comma-separated trusted host headers |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_ENABLED` | `true` | Enable rate limiting |
| `DEAL_DISCOVERY_ENABLED` | `false` | Enable deal discovery worker |
| `SENTRY_DSN` | — | Sentry error tracking DSN |
| `SENTRY_ENV` | `development` | Sentry environment tag |

## Local Development

### Backend

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start the server
cd server
DEV_MODE=true DB_ENABLED=false uvicorn main:app --reload --port 8000

# Run tests
python -m pytest tests/ --ignore=tests/test_inference.py -x -q
```

### Frontend

```bash
# Install Node dependencies
npm install

# Start Expo dev server
npx expo start

# Run tests
npx jest

# Type check
npx tsc --noEmit
```

## Production Deployment

### 0. Deploying server-code changes (rsync flow)

> ⚠️ **The bake's systemd unit has `WorkingDirectory=/opt/collectors/server`.**
> Python imports `app.*` resolve to `/opt/collectors/server/app/*` — NOT to
> `/opt/collectors/app/*`. Always rsync to `/opt/collectors/server/`.

**Use the wrapper script.** Don't rsync by hand:

```bash
scripts/deploy_to_ec2.sh                    # diff vs HEAD~1, dry-run preview, no restart
scripts/deploy_to_ec2.sh --restart          # rsync + restart bake + tail journal
scripts/deploy_to_ec2.sh --files paths.txt --restart   # explicit file list
```

The script:
1. Refuses to run if `server/` has uncommitted changes (override with `--dirty`).
2. Computes the file list from `git diff HEAD~1 HEAD -- server/` if `--files` not given.
3. Shows a dry-run preview, requires interactive `y` confirmation.
4. rsyncs to `collectai:/opt/collectors/server/`.
5. With `--restart`: triggers `systemctl restart collectai-bake.service`,
   waits up to 20s for `is-active`, dumps recent journal warnings.

**Manual rsync fallback** (only when the script can't be used):

```bash
# CORRECT — note both trailing slashes and the /server/ at the end
rsync -av --files-from=files.txt /Users/me/repo/server/ collectai:/opt/collectors/server/

# WRONG — files end up in a parallel tree the bake never imports from
rsync -av --files-from=files.txt /Users/me/repo/server/ collectai:/opt/collectors/
```

**Incident memo (2026-05-02)**: a full day of "successful" deploys went to
`/opt/collectors/` (one level too high). All preflight gates passed,
postflight smoke passed, the bake came up cleanly — but it kept running
old code because every `import app.*` resolved against the canonical
`/opt/collectors/server/app/*` while my new files sat in a parallel
`/opt/collectors/app/*` tree. Surfaced only by a live E2E that exercised
a freshly-added paywall gate and got HTTP 200 instead of 403. Cleanup
removed the parallel `/opt/collectors/{app,workers,tests}/` trees
(backed up to `/tmp/duplicate_trees_20260502_173101.tar.gz` on EC2 in
case revert is needed).

### 0b. Run the NINE preflight gates BY HAND before restarting (2026-08-15, corrected 2026-08-17)

`collectai-bake.service` has **nine** blocking `ExecStartPre=` gates:

```
preflight_deps · preflight_env · preflight_worker_imports
schema_drift_check · preflight_rls_check · preflight_models
preflight_router_drift · preflight_schema_lock · preflight_rpc_lock
```

This section said **six** until 2026-08-17 and omitted the first three, so
following it verbatim left `preflight_deps`, `preflight_env` and
`preflight_worker_imports` untested before a restart — exactly the gates that
catch a missing dependency or an unset env var, which are the ones most likely
to break after a deploy. **Read the list off the unit, not off this file:**

```bash
ssh collectai 'systemctl cat collectai-bake.service | grep ExecStartPre'
```

A blocking `ExecStartPre` that exits non-zero means the unit **does not come
up**. Since the bake serves the API *and* every worker, discovering a failing
gate during a restart takes production down rather than merely failing a
deploy. Run them first, while the old process is still serving:

```bash
ssh collectai 'cd /opt/collectors/server && set -a; . /opt/collectors/.env; set +a
for s in preflight_deps preflight_env preflight_worker_imports \
         schema_drift_check preflight_rls_check preflight_models \
         preflight_router_drift preflight_schema_lock preflight_rpc_lock; do
  printf "%s: " "$s"
  /opt/collectors/.venv/bin/python /opt/collectors/scripts/$s.py >/tmp/pf.log 2>&1 \
    && echo PASS || { echo FAIL; tail -12 /tmp/pf.log; }
done'
```

**This is not theoretical.** On 2026-08-15 a commit redefined
`mv_catalog_item_price` to use `percentile_cont`, which changes `price_eur`
from `numeric` to `double precision`. The DDL was applied to prod;
`schema.lock.json` was not regenerated. The bake kept serving happily —
**because the lock only bites on the next restart** — so for about an hour the
service was in a state where any restart, reboot or OOM kill would have failed
to come back up, with nothing in any dashboard saying so.

**After any DDL, regenerate the lock and DIFF it — do not just regenerate:**

```bash
ssh collectai 'cd /opt/collectors && cp scripts/schema.lock.json /tmp/lock.before.json
  set -a; . .env; set +a; .venv/bin/python scripts/regen_schema_lock.py'
# then diff tables / column_meta / uniques / checks between the two files
```

A regen blesses whatever is live. The one on 2026-08-15 picked up 6 tables,
34 columns, 11 uniques and 12 checks that had accumulated since 2026-08-09 —
all of them legitimate, but you only know that by *reading the diff*. Copy the
regenerated lock back into the repo (`scripts/schema.lock.json`) or the next
person starts from a stale one.

**Order matters: rsync FIRST, then run the gates, then restart.** The gates
import from `/opt/collectors/server/`, so running them before the rsync tests
the code you are replacing rather than the code you are shipping. Staging the
files does not disturb the running process — it has already loaded its modules
into memory and is unaffected until the restart.

Worked example (2026-08-17, the `/social/users/{id}/categories` deploy):

```bash
scripts/deploy_to_ec2.sh --files list.txt --dirty     # stage, no restart
ssh collectai '...nine gates...'                       # all PASS
ssh collectai 'sudo systemctl restart collectai-bake.service'
ssh collectai 'curl -s -H "Host: api.sparrowcollect.com" http://127.0.0.1:8000/healthz'
# then a real authed request against the NEW endpoint — is-active is not proof
# it works, only that it started.
```

### 0c. A committed query is not a tested query (2026-08-15)

`p2p_offers_router.py` selected `l.image_url`, where `l` is
`marketplace_listings`. **That column has never existed** and no migration ever
added it. It passed review, `tsc`, `jest` and the router's own 30 tests — all
of which read SQL as *text* — and sat in `main` looking fine because the router
had not been deployed. The first deploy after that turned every
`GET /p2p/offers` into a 500 and took the Open bids screen down.

The gate that closes this is **`npm run check:sql-columns`**
(`server/scripts/check_sql_columns.py`, wired into `verify:prebuild`). It maps
`FROM|JOIN <table> <alias>` to `alias.column` references and checks each one
against `scripts/schema.lock.json`.

Two false-greens were found while writing it, both worth knowing because they
are the same mistake in different clothes:

1. **Alias scope.** Aliases were first resolved per SQL string. `_OFFER_COLUMNS`
   is a bare column list with no `FROM` in it, so `l` resolved to nothing and
   the reference was skipped as unresolvable. Aliases are now resolved
   **per file** (an alias bound to two tables in one file is skipped as
   ambiguous rather than guessed at).
2. **Block filter.** Blocks were first filtered to "contains SELECT/INSERT/
   UPDATE/DELETE". `_OFFER_COLUMNS` contains none of those words — so the one
   block holding the bug was the one block skipped.

Both versions reported a clean bill of health on the very bug they were written
for. **Prove a new gate fails on the real defect before trusting it.**

### 1. HTTPS Setup with nginx

The backend runs behind nginx with SSL termination via Let's Encrypt.

```bash
# On EC2 instance:
# Install nginx and certbot
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx

# Copy nginx config
sudo cp deploy/nginx.conf /etc/nginx/sites-available/collectai
sudo ln -s /etc/nginx/sites-available/collectai /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Get SSL certificate (ensure DNS A record points to this server first)
sudo certbot --nginx -d api.sparrowcollect.com

# Verify and reload
sudo nginx -t && sudo systemctl reload nginx

# Verify auto-renewal
sudo certbot renew --dry-run
```

The nginx config is at `deploy/nginx.conf`. It:
- Redirects HTTP to HTTPS
- Terminates SSL with Let's Encrypt certificates
- Proxies to the Docker container on port 8080
- Sets security headers (HSTS, X-Frame-Options, etc.)
- Limits request body to 20MB

### 2. Docker Deployment

```bash
# Build image
docker build -t collectai .

# Run with docker-compose
docker compose up -d

# Check health
curl -sf https://api.sparrowcollect.com/healthz
```

### 3. Deploy to EC2

**First-time setup:**

```bash
# On EC2:
sudo mkdir -p /opt/collectai
cd /opt/collectai

# Copy docker-compose.yml and .env
scp docker-compose.yml ec2-user@<host>:/opt/collectai/
scp .env ec2-user@<host>:/opt/collectai/

# Pull and start
docker compose up -d
```

**Subsequent deploys (via CI/CD or manual):**

```bash
cd /opt/collectai
docker compose pull
docker compose up -d --remove-orphans

# Verify health
curl -sf http://localhost:8080/healthz
docker compose logs -f api
```

### Resource Limits

The `docker-compose.yml` enforces these limits:

| Service | CPU | Memory |
|---------|-----|--------|
| API | 1.0 | 1 GB |
| Price Monitor | 0.5 | 512 MB |
| Deal Discovery | 0.5 | 512 MB |

## Secret Rotation

### Rotate Supabase Keys

If keys were exposed in git history:

```bash
# 1. Rotate keys in Supabase Dashboard > Settings > API
# 2. Update .env on EC2 with new keys
# 3. Restart services
docker compose restart

# 4. Scrub from git history (if committed)
pip install git-filter-repo
git filter-repo --path .env --invert-paths
git push --force-with-lease
```

### Generate New API Secrets

```bash
# Generate new OPS_API_KEY
openssl rand -hex 32

# Generate new API_SHARED_SECRET
openssl rand -hex 32
```

### Rotate JWT Secret

1. Go to Supabase Dashboard > Settings > API
2. Note: rotating the JWT secret will invalidate ALL existing user sessions
3. Update `SUPABASE_JWT_SECRET` in `.env` on EC2
4. Restart backend: `docker compose restart api`

## Database Migrations

Migrations are in `supabase/migrations/`. Apply them via:

```bash
# Using Supabase CLI
supabase db push

# Or manually via psql
psql $DATABASE_URL -f supabase/migrations/20260210_evidence_native.sql
psql $DATABASE_URL -f supabase/migrations/20260210_taxonomy_registry.sql
psql $DATABASE_URL -f supabase/migrations/20260210_object_pointers.sql
psql $DATABASE_URL -f supabase/migrations/20260213_smart_deal_agent.sql
psql $DATABASE_URL -f supabase/migrations/20260218_subscriptions.sql
psql $DATABASE_URL -f supabase/migrations/20260218_beta_signups.sql
psql $DATABASE_URL -f supabase/migrations/20260219_portfolio_attributes.sql
psql $DATABASE_URL -f supabase/migrations/20260219_bugfix_audit.sql
psql $DATABASE_URL -f supabase/migrations/20260220_catalog_learning.sql
psql $DATABASE_URL -f supabase/migrations/20260221_user_blocks.sql
psql $DATABASE_URL -f supabase/migrations/20260222_currency_geo_shipping.sql
psql $DATABASE_URL -f supabase/migrations/20260222_events_improvements.sql
psql $DATABASE_URL -f supabase/migrations/20260222_build_paint_improvements.sql
psql $DATABASE_URL -f supabase/migrations/20260223_add_performance_indexes.sql
psql $DATABASE_URL -f supabase/migrations/20260224_user_privacy_settings.sql
psql $DATABASE_URL -f supabase/migrations/20260224_add_indexes_v2.sql
psql $DATABASE_URL -f supabase/migrations/20260322_build_paint_status_pipeline.sql
```

### Round 36 Migration Notes (2026-03-22)

**`20260322_build_paint_status_pipeline.sql`** — Category-specific project status pipelines:
- Migrates existing data: `Active` → `in_progress`, `Backlog` → `wishlist`, `Completed` → `finished`
- Changes default status from `'Active'` to `'wishlist'`
- Adds CHECK constraint for 25 valid statuses across all category pipelines
- Updates RPCs: `rpc_create_build_paint_project_v1`, `rpc_mark_build_paint_project_complete_v1`, `rpc_set_build_paint_progress_v1`

**New worker: `auction_alert_worker`** — Enable with `AUCTION_ALERT_ENABLED=true`. Runs every 5 minutes, scans for eBay/Yahoo/Catawiki auctions ending within 15 minutes that match watchlist items.

**Notification system overhaul** — All workers now route through `app/lib/notify.py` for preference-aware, frequency-capped push delivery. No migration needed; uses existing `notification_history` and `user_push_tokens` tables.

**Catalog expansion** — Run `cd server && python -m pipelines.import_all` on EC2 to populate 46,500+ curated items across 45 pipelines.

### Round 36b Migration Notes (2026-03-23)

**`20260323_events_enrich.sql`** — Adds `franchise_id`, `latitude`, `longitude` columns to `events` table with partial indexes for franchise and geo queries.

**New automated workers (both run as long-lived scheduler processes):**
- `python -m workers.event_scraper_scheduler` — Runs every 6 hours. Crawls 41 brand/convention web targets, runs newsletter scraper, deduplicates cross-source, enriches with franchise tags + geocoding.
- `python -m workers.auction_alert_worker` — Runs every 5 minutes. Alerts users when watched auctions are ending soon.

**New pipelines:**
- `pipelines/event_dedup.py` — Cross-source event deduplication (title similarity + date matching)
- `pipelines/event_enrich.py` — Franchise tagging (13 franchises) + Nominatim geocoding

## Beta Landing Page

The landing page at `web/index.html` (with `web/icon.png`) collects beta signups
at `sparrowcollect.com`. It posts to `POST /api/beta-signup` on the backend. Deploy the
entire `web/` directory — the page loads the icon image and Roboto font from Google Fonts.

### Deploying the Landing Page

**Option A: Serve via nginx (same server as API)**

Add to your nginx config:

```nginx
# Serve landing page at root
location = / {
    root /opt/collectai/web;
    try_files /index.html =404;
}

# Serve legal pages (if hosting static versions)
location /legal/ {
    root /opt/collectai/web;
    try_files $uri $uri.html =404;
}
```

**Option B: Serve via CDN (Cloudflare Pages, Netlify, etc.)**

1. Upload `web/index.html` and `web/icon.png` to the static hosting provider
2. Set the domain to `sparrowcollect.com`
3. Edit the `API_BASE` variable in the HTML to point to the backend:
   ```javascript
   var API_BASE = "https://api.sparrowcollect.com";
   ```

### Beta Signup API

| Endpoint | Auth | Description |
|----------|------|-------------|
| `POST /api/beta-signup` | None (public) | Collect email signup |
| `GET /ops/beta-signups` | Ops key | Paginated signup list |

Rate limited to 5 signups per IP per hour (in-memory).

## OTA Updates (expo-updates)

Sparrow Collect supports over-the-air updates via `expo-updates`. This allows pushing
JavaScript/asset changes without a full store resubmission.

### Configuration

The update URL is set in `app.json` under `expo.updates`:

```json
{
  "updates": {
    "enabled": true,
    "fallbackToCacheTimeout": 0,
    "url": "https://u.expo.dev/YOUR_PROJECT_ID",
    "checkAutomatically": "ON_LOAD"
  }
}
```

Replace `YOUR_PROJECT_ID` with the actual EAS project ID (set after `eas init`).

### How it works

1. On app launch, `_layout.tsx` calls `Updates.checkForUpdateAsync()` (non-blocking)
2. If an update is available, it is fetched in the background
3. The update applies on the next app restart

### Publishing an OTA update

```bash
# Publish to all users on the default branch
eas update --branch production --message "Fix: marketplace price display"
```

### Limitations

OTA updates can only change JavaScript and assets. Native module changes
(new permissions, new native libraries) require a full store build.

## Store Review Prompt

The app includes a store review prompt (`src/hooks/useStoreReview.ts`) that uses
the native iOS/Android review dialog. It triggers when:

- User has 10+ items in their collection
- App has been used on 3+ separate days
- Haven't been prompted in the last 90 days

This is non-intrusive and uses `expo-store-review` (wraps StoreKit/Play In-App Review).

## Mobile App Build

### Development (Expo Go)

```bash
npx expo start
```

### EAS Build (Production)

```bash
# Install EAS CLI
npm install -g eas-cli

# Login to Expo
eas login

# iOS build
eas build --platform ios --profile production

# Android build
eas build --platform android --profile production

# Submit to stores
eas submit --platform ios --profile production
eas submit --platform android --profile production
```

### EAS Build Profiles

| Profile | Use case | Distribution |
|---------|----------|--------------|
| `development` | Local testing with dev client | Internal (simulator) |
| `preview` | TestFlight / Internal testing | Internal |
| `production` | App Store / Google Play | Store |

## Monitoring

- **Daily watchdog** — `server/scripts/watchdog.py`, cron `0 9 * * *`
  (Europe/Paris) via `/opt/collectors/scripts/watchdog_daily.sh`. Reports user
  activity, healthy loops and silent failures to Telegram; JSON kept 30 days in
  `/opt/collectors/logs/`. **Reads Supabase Logflare logs**, which is the only
  place DB rejections and PostgREST failures appear — the EC2 journal cannot see
  them. See [`docs/WATCHDOG.md`](./WATCHDOG.md).


- **Health check**: `GET /healthz` returns `{"status": "ok", "version": "...", "db": "ok"}`
- **Pipeline status**: `GET /pipeline/status` reports model freshness and ingest health
- **Ops dashboard**: `GET /ops/status` (requires `X-Ops-Key` header)
- **Beta signups**: `GET /ops/beta-signups` (requires `X-Ops-Key` header)
- **Worker status**: `GET /ops/worker-status` (requires `X-Ops-Key` header)
- **Catalog suggestions**: `GET /ops/catalog-suggestions` (requires `X-Ops-Key` header)
- **Category candidates**: `GET /ops/category-candidates` (requires `X-Ops-Key` header)
- **Logs**: `docker compose logs -f api` or CloudWatch if configured
- **Sentry**: Set `SENTRY_DSN` for error tracking

## ⚠️ Three places run code, and they drift independently

This is the single easiest thing to get wrong here. **Deploying to EC2 does not
update GitHub Actions, and committing does not update EC2.**

| Where | Gets its code from | How to check what it's running |
|-------|--------------------|-------------------------------|
| **EC2** — API + bake workers | `scripts/deploy_to_ec2.sh`, which **rsyncs your local working tree** (not a git ref) | `md5sum server/<file>` vs `ssh collectai 'md5sum /opt/collectors/server/<file>'` |
| **GitHub Actions** — `nightly-ingest`, `ingest-ebay`, `nightly-*` | **the branch the workflow runs on** | `gh run list --workflow=nightly-ingest.yml` — the ref is in the output |
| **Your working branch** | local commits, frequently unpushed | `git branch --show-current` |

A fix can therefore be **live in the API and completely absent from the nightly
pipeline** at the same time.

**Worked example (2026-07-29).** The watchdog reported 662 rejected writes/day:
`category_items violates check constraint category_items_attrs_is_object`.
Everything on EC2 checked out — `import_common.py` md5 matched the repo, both
catalog writers posted a JSON object, `category_items` had **zero** corrupt
rows, and `bake.log` had **zero** occurrences of the error.

The writer wasn't on EC2. `nightly-ingest.yml` (cron `0 3 * * *`) runs from
`feature/all-enhancements`, which was still at **2026-07-02** and carried the
pre-fix line:

```python
row["attributes_json"] = json.dumps(self.attributes_json)   # → JSONB string → 23514
```

The 2026-07-25 fix (`row["attributes_json"] = self.attributes_json`) had never
reached that branch, so the ingest silently discarded every attribute-bearing
catalog row, nightly, for weeks.

> **Diagnostic:** an error Postgres reports that your **application log does not
> contain** means the writer is not the app. Check GitHub Actions next — and
> check *which ref* the workflow runs, not just that it ran.

**Still live on 2026-08-12 — 680 rejections/day, two weeks later.** Re-verified
end to end:

```bash
gh repo view --json defaultBranchRef        # -> feature/all-enhancements
gh run list --workflow=nightly-ingest.yml   # -> ran feature/all-enhancements, "success", 04:41Z
git show origin/feature/all-enhancements:server/pipelines/import_common.py | grep attributes_json
#   284:  row["attributes_json"] = json.dumps(self.attributes_json)   <- pre-fix
grep -n attributes_json server/pipelines/import_common.py
#   300:  row["attributes_json"] = self.attributes_json               <- fixed here
```

**The root cause is one repo setting, not a stale checkout.** GitHub runs
`schedule:` workflows from the **default branch**, and this repo's default
branch *is* `feature/all-enhancements`. So the nightly pipeline does not lag
behind the default branch — it faithfully runs it, and the default branch has
been the stale one since 2026-07-02. Nothing merged into `main` or into a
working branch can ever reach the nightly ingest while that is true, and the
workflow will keep reporting **success** because it logs rows attempted, not
rows Postgres accepted.

Two ways out, both requiring a decision rather than a deploy:

1. **Point the default branch at current code** (repo Settings → Branches).
   Fixes every scheduled workflow at once; also changes the default PR base.
2. **Merge the fix into `feature/all-enhancements`** and keep it as default.
   Fixes tonight's run; the drift returns with the next fix.

Until one is done, treat `category_items_attrs_is_object` in the watchdog as
**expected daily noise from a known cause** — which is its own hazard, and the
reason this is written down rather than muted.

After merging a server fix, ask: does this need to reach EC2 (rsync), the
scheduled pipelines (branch), or both?

## CI/CD

GitHub Actions workflows in `.github/workflows/`:

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | Push/PR | Backend tests, frontend tests, Docker build, Trivy scan |
| `nightly-ingest.yml` | cron `0 3 * * *` | Catalog import (`pipelines.import_all`). **Runs the workflow's branch, NOT what is on EC2.** |

### Enabling CD

1. Configure GitHub secrets:
   - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
   - `ECR_REGISTRY` (e.g. `123456789.dkr.ecr.eu-central-1.amazonaws.com`)
   - `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`

2. Create a GitHub Environment called `production` with required reviewers

3. In `ci.yml`, change `if: false && github.ref == ...` to `if: github.ref == ...`

4. Push to `main` — the deploy job will run after tests pass

## App Store Submission

Full app store submission guide (EAS setup, screenshots, deep links, review prep) has been moved to:

- **[`docs/APP_STORE_SUBMISSION.md`](./APP_STORE_SUBMISSION.md)** — Full 10-step submission guide, EAS credentials, screenshots, deep links, checklist
- **[`docs/APP_REVIEW_NOTES.md`](./APP_REVIEW_NOTES.md)** — Demo account, feature walkthrough, affiliate link explanation

## Production Checklist

Before going live:

- [ ] `DEV_MODE=false` in production `.env`
- [ ] All required env vars filled (see table above)
- [ ] CORS_ORIGINS set to production domains only
- [ ] TRUSTED_HOSTS set to your domain(s)
- [ ] SSL certificate installed (nginx + certbot)
- [ ] DNS A record pointing to EC2 IP
- [ ] Supabase keys rotated (if previously exposed)
- [ ] Database migrations applied (all files in `supabase/migrations/`)
- [ ] Health check passing: `curl https://api.sparrowcollect.com/healthz`
- [ ] Sentry DSN configured for error monitoring
- [ ] Rate limiting enabled
- [ ] Docker resource limits verified
