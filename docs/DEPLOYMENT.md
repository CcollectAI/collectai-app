# Deployment Guide

## Prerequisites

- Python 3.12+
- Node.js 20+
- Docker (for containerized deployment)
- Supabase project with PostgreSQL
- AWS account (for S3 image storage and EC2 hosting)
- Domain name pointing to EC2 (e.g. `api.collectai.app`)

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
| `CORS_ORIGINS` | `https://app.collectai.io,https://collectai.app` | Comma-separated allowed origins |
| `TRUSTED_HOSTS` | `api.collectai.app,collectai.app` | Comma-separated trusted host headers |

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
sudo certbot --nginx -d api.collectai.app

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
curl -sf https://api.collectai.app/healthz
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
```

## Beta Landing Page

The landing page at `web/index.html` (with `web/icon.png`) collects beta signups
at `collectai.app`. It posts to `POST /api/beta-signup` on the backend. Deploy the
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
2. Set the domain to `collectai.app`
3. Edit the `API_BASE` variable in the HTML to point to the backend:
   ```javascript
   var API_BASE = "https://api.collectai.app";
   ```

### Beta Signup API

| Endpoint | Auth | Description |
|----------|------|-------------|
| `POST /api/beta-signup` | None (public) | Collect email signup |
| `GET /ops/beta-signups` | Ops key | Paginated signup list |

Rate limited to 5 signups per IP per hour (in-memory).

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

### Step 1: Developer Account Setup

**Apple Developer Program (required for iOS):**

1. Enroll at [developer.apple.com](https://developer.apple.com) — USD 99/year
2. After enrollment, note your **Team ID** (10 chars) from Membership Details
3. Go to [App Store Connect](https://appstoreconnect.apple.com) > My Apps > + New App
   - Platform: iOS
   - Name: CollectAI
   - Bundle ID: `com.collectai.app`
   - SKU: `collectai-ios-1`
4. Note the numeric **App Store Connect App ID** from the URL or General > App Information

**Google Play Console (required for Android):**

1. Register at [play.google.com/console](https://play.google.com/console) — USD 25 one-time
2. Create app: set language (English), title (CollectAI), declaration checkboxes
3. Create a Service Account for API-based submissions:
   - Google Cloud Console > IAM > Service Accounts > Create
   - Grant "Service Account User" role
   - Download JSON key to `./google-play-service-account.json` (gitignored)
   - In Play Console > API access > link the service account

### Step 2: Fill EAS Credentials

Update `eas.json` submit section with real values:

```json
"submit": {
  "production": {
    "ios": {
      "appleId": "your@email.com",
      "ascAppId": "1234567890",
      "appleTeamId": "ABCDE12345"
    },
    "android": {
      "serviceAccountKeyPath": "./google-play-service-account.json",
      "track": "internal",
      "releaseStatus": "draft"
    }
  }
}
```

For iOS submissions, generate an App-Specific Password:
- Go to [appleid.apple.com](https://appleid.apple.com) > Security > App-Specific Passwords
- Set as env var: `EXPO_APPLE_APP_SPECIFIC_PASSWORD=xxxx-xxxx-xxxx-xxxx`

### Step 3: Initialize EAS Project

```bash
# Install EAS CLI
npm install -g eas-cli

# Login to Expo
eas login

# Initialize project (auto-generates projectId + owner in app.json)
eas init
```

This populates `expo.owner` and `expo.extra.eas.projectId` in app.json.

### Step 4: Build for Production

```bash
# iOS production build
eas build --platform ios --profile production

# Android production build
eas build --platform android --profile production

# Build both simultaneously
eas build --platform all --profile production
```

EAS will walk through certificate/provisioning setup on first build:
- **iOS**: Creates Distribution Certificate + Provisioning Profile (let EAS manage)
- **Android**: Generates upload keystore (EAS stores it securely)

### Step 5: Prepare Store Listings

Store listing text is in `docs/store-description.md`. Key metadata:

**iOS App Store:**

| Field | Value |
|-------|-------|
| App Name | CollectAI |
| Subtitle | Track, Value & Grow Your Hobby |
| Category | Lifestyle (primary), Shopping (secondary) |
| Keywords | collectibles,price guide,valuation,pokemon,funko,trading cards,collection,tracker,deals,portfolio |
| Description | See `docs/store-description.md` |
| Privacy URL | `https://collectai.app/privacy` |
| Support URL | `https://collectai.app/support` |
| Marketing URL | `https://collectai.app` |

**Google Play:**

| Field | Value |
|-------|-------|
| App Name | CollectAI - Collectibles Tracker |
| Short Description | Track, value, and discover collectibles with AI-powered market intelligence |
| Category | Lifestyle |
| Content Rating | Everyone |
| Privacy Policy URL | `https://collectai.app/privacy` |

### Step 6: Screenshots

**iOS Required Sizes:**

| Device | Resolution | Required? |
|--------|-----------|-----------|
| iPhone 6.9" (16 Pro Max) | 1320 x 2868 | Yes |
| iPhone 6.7" (15 Plus / 14 Pro Max) | 1290 x 2796 | Yes |
| iPhone 6.5" (11 Pro Max / Xs Max) | 1242 x 2688 | Yes (if supporting older) |
| iPhone 5.5" (8 Plus) | 1242 x 2208 | Only if supporting iPhone 8 |
| iPad Pro 13" | 2064 x 2752 | Yes (`supportsTablet: true`) |
| iPad Pro 12.9" | 2048 x 2732 | Yes (if supporting older iPads) |

**Google Play Required Sizes:**

| Device Type | Resolution | Required? |
|-------------|-----------|-----------|
| Phone | 1080 x 1920 (min) | Yes (2-8 screenshots) |
| 7" Tablet | 1200 x 1920 | If targeting tablets |
| 10" Tablet | 1600 x 2560 | If targeting tablets |

**Recommended screenshot scenes (6-10 per device):**

1. **Collection Overview** — portfolio grid with items and values
2. **Item Detail** — single item with valuation and provenance
3. **QuickScan** — camera scanning a barcode or collectible
4. **Price Intelligence** — price chart or valuation breakdown
5. **Deal Discovery** — purchase mandates with matched deals
6. **Events** — collector events calendar
7. **Categories** — browsing the 36 category taxonomy
8. **Analytics** — portfolio value trends and insights

**Capturing screenshots:**
- Use Xcode Simulator for iOS (Cmd+S to save screenshot)
- Use Android Studio emulator for Google Play
- Or use a tool like [screenshots.pro](https://screenshots.pro) or Fastlane snapshot

### Step 7: Required Assets

| Asset | Size | Status |
|-------|------|--------|
| App icon (iOS) | 1024 x 1024 | Ready (`assets/icon.png`) |
| Adaptive icon (Android) | 1024 x 1024 | Ready (`assets/adaptive-icon.png`) |
| Splash screen | 1284 x 2778 | Ready (`assets/splash.png`) |
| Notification icon | 96 x 96 | Ready (`assets/images/notification-icon.png`) |
| Feature graphic (Google Play) | 1024 x 500 | **TODO** — create with Tiffany Blue (#81D8D0) background |

### Step 8: Deep Link Verification

Before App Store review, host verification files on `collectai.app`:

**iOS — Apple App Site Association:**

Host at `https://collectai.app/.well-known/apple-app-site-association`:

```json
{
  "applinks": {
    "apps": [],
    "details": [
      {
        "appIDs": ["TEAM_ID.com.collectai.app"],
        "paths": ["/item/*", "/events/*", "/categories/*", "/purchase/*", "/users/*"]
      }
    ]
  }
}
```

**Android — Digital Asset Links:**

Host at `https://collectai.app/.well-known/assetlinks.json`:

```json
[{
  "relation": ["delegate_permission/common.handle_all_urls"],
  "target": {
    "namespace": "android_app",
    "package_name": "com.collectai.app",
    "sha256_cert_fingerprints": ["YOUR_SHA256_FINGERPRINT"]
  }
}]
```

Get your SHA-256 fingerprint: `eas credentials --platform android`

### Step 9: Submit to Stores

```bash
# Submit iOS build to App Store Connect
eas submit --platform ios --profile production

# Submit Android build to Google Play
eas submit --platform android --profile production
```

**Important for Android:** The first AAB upload MUST be done manually via Play Console.
Download the AAB from EAS (`eas build:list`) and upload to the internal testing track.
Subsequent submissions can use `eas submit`.

### Step 10: App Review Preparation

**iOS App Review Info:**
- Provide a demo account (email + password) for the review team
- Fill in "Notes for Reviewer" explaining how to test key features
- Respond promptly to any reviewer questions (App Store Connect notifications)

**Google Play Data Safety:**
- Complete the Data Safety questionnaire in Play Console
- Declare: email collection, photos access, camera usage, analytics (Sentry)
- Mark data as encrypted in transit (HTTPS)

### App Store Submission Checklist

- [ ] Apple Developer Program enrolled (USD 99/year)
- [ ] Google Play Console enrolled (USD 25 one-time)
- [ ] App created in App Store Connect + Play Console
- [ ] `eas.json` credentials filled (appleId, ascAppId, appleTeamId, service account)
- [ ] `eas init` run (projectId populated in app.json)
- [ ] App-specific password generated for iOS submissions
- [ ] Production builds created via `eas build --profile production`
- [ ] Store listing text uploaded (from `docs/store-description.md`)
- [ ] Screenshots captured for all required device sizes
- [ ] Feature graphic created for Google Play (1024 x 500)
- [ ] `collectai.app` domain active with HTTPS
- [ ] `.well-known/apple-app-site-association` hosted
- [ ] `.well-known/assetlinks.json` hosted
- [ ] Privacy policy accessible at `https://collectai.app/privacy`
- [ ] Demo account created for App Review
- [ ] Data Safety questionnaire completed (Google Play)
- [ ] Age rating questionnaire completed (both stores)
- [ ] First Android AAB uploaded manually to Play Console
- [ ] Backend deployed and healthy (`/healthz` returning OK)
- [ ] Database migrations applied (all files in `supabase/migrations/`)

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
- [ ] Health check passing: `curl https://api.collectai.app/healthz`
- [ ] Sentry DSN configured for error monitoring
- [ ] Rate limiting enabled
- [ ] Docker resource limits verified
