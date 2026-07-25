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

## CI/CD

GitHub Actions workflows in `.github/workflows/`:

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | Push/PR | Backend tests, frontend tests, Docker build, Trivy scan |

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
