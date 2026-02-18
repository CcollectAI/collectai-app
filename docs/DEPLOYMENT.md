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
```

## Beta Landing Page

The landing page at `web/index.html` (with `web/icon.png`) collects beta signups
at `collectai.app`. It posts to `POST /api/beta-signup` on the backend. Deploy the
entire `web/` directory — the page loads the icon image and Inter font from Google Fonts.

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

### iOS App Store Screenshots

Required sizes (use Simulator + Xcode screenshot tool or a service like [screenshots.pro](https://screenshots.pro)):

| Device | Resolution | Required? |
|--------|-----------|-----------|
| iPhone 6.9" (16 Pro Max) | 1320 x 2868 | Yes |
| iPhone 6.7" (15 Plus / 14 Pro Max) | 1290 x 2796 | Yes |
| iPhone 6.5" (11 Pro Max / Xs Max) | 1242 x 2688 | Yes (if supporting older) |
| iPhone 5.5" (8 Plus) | 1242 x 2208 | Only if supporting iPhone 8 |
| iPad Pro 13" | 2064 x 2752 | Yes (if `supportsTablet: true`) |
| iPad Pro 12.9" | 2048 x 2732 | Yes (if supporting older iPads) |

Recommended screenshots (6-10 per device):

1. **Collection Overview** — main portfolio grid showing items with values
2. **Item Detail** — single item with price evidence and provenance
3. **QuickScan** — camera scanning a barcode or item photo
4. **Price Intelligence** — price chart or valuation breakdown
5. **Deal Discovery** — purchase mandates with matched deals
6. **Events** — upcoming collector events calendar
7. **Categories** — browsing the 36 category taxonomy
8. **Analytics** — portfolio value trends and insights

### Google Play Store Screenshots

| Device Type | Resolution | Required? |
|-------------|-----------|-----------|
| Phone | 1080 x 1920 (min) | Yes (2-8 screenshots) |
| 7" Tablet | 1200 x 1920 | If targeting tablets |
| 10" Tablet | 1600 x 2560 | If targeting tablets |

Same recommended screenshots as iOS.

### App Store Metadata

| Field | Value |
|-------|-------|
| App Name | CollectAI |
| Subtitle | Smart Collectibles Tracker |
| Category | Lifestyle (primary), Shopping (secondary) |
| Keywords | collectibles, valuation, price tracker, collection manager, funko, pokemon, trading cards, barcode scanner |
| Description | See `docs/store-description.md` (to be written) |
| Privacy URL | `https://collectai.app/privacy` |
| Support URL | `https://collectai.app/support` |
| Marketing URL | `https://collectai.app` |

### Google Play Metadata

| Field | Value |
|-------|-------|
| App Name | CollectAI - Collectibles Tracker |
| Short Description | Track, value, and discover collectibles with AI |
| Category | Lifestyle |
| Content Rating | Everyone |
| Privacy Policy URL | `https://collectai.app/privacy` |

### Required Assets

| Asset | Size | Notes |
|-------|------|-------|
| App icon (iOS) | 1024 x 1024 | No transparency, no rounded corners |
| Feature graphic (Google Play) | 1024 x 500 | Shown at top of listing |
| Adaptive icon (Android) | 512 x 512 foreground + background | With safe zone |

## Production Checklist

Before going live:

- [ ] `DEV_MODE=false` in production `.env`
- [ ] All required env vars filled (see table above)
- [ ] CORS_ORIGINS set to production domains only
- [ ] TRUSTED_HOSTS set to your domain(s)
- [ ] SSL certificate installed (nginx + certbot)
- [ ] DNS A record pointing to EC2 IP
- [ ] Supabase keys rotated (if previously exposed)
- [ ] Database migrations applied (including `20260218_beta_signups.sql`)
- [ ] Health check passing: `curl https://api.collectai.app/healthz`
- [ ] Sentry DSN configured for error monitoring
- [ ] Rate limiting enabled
- [ ] Docker resource limits verified
