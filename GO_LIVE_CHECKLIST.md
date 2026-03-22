================================================================================
  COLLECTAI — GO-LIVE CHECKLIST
  Generated: 2026-02-18
================================================================================

Use this file as a step-by-step checklist. Work through each section in order.
Mark items [x] as you complete them.

Current state: All code is written and tested (1653 backend + 104 frontend tests
passing, 0 TypeScript errors). Age verification (COPPA/GDPR), expo-store-review,
and OTA updates (expo-updates) are code-complete. Everything below is
configuration, credentials, assets, and manual setup needed to take the app from
dev to production.


================================================================================
 1. DOMAIN & DNS
================================================================================

[ ] Buy domain (collectai.app or your chosen domain)
[ ] Create DNS A record pointing to EC2 IP (3.75.182.41)
    - api.collectai.app -> EC2 IP (for backend API)
    - collectai.app -> your website/landing page (optional)
    - www.collectai.app -> same as above
[ ] Create CNAME for www -> collectai.app (if using www)
[ ] Wait for DNS propagation (check with: dig api.collectai.app)


================================================================================
 2. SUPABASE PROJECT SETUP
================================================================================

[ ] Create Supabase project (if not already done)
    - Region: eu-central-1 (Frankfurt) recommended for EU users
[ ] Collect these values from Supabase Dashboard > Settings > API:
    - SUPABASE_URL (e.g. https://xxxx.supabase.co)
    - SUPABASE_KEY (anon key)
    - SUPABASE_SERVICE_KEY (service_role key)
    - SUPABASE_JWT_SECRET
    - SUPABASE_JWT_ISSUER (e.g. https://xxxx.supabase.co/auth/v1)
[ ] Collect database connection string from Settings > Database:
    - DB_DSN (e.g. postgresql://postgres:password@db.xxxx.supabase.co:5432/postgres)

--- Run Migrations ---

Apply all SQL migrations in order. Use Supabase SQL Editor or psql:

[ ] 2025-10-01_collectors_core.sql        (core tables)
[ ] 2025-10-01_rls_policies.sql           (row-level security)
[ ] 2025-10-02_alert_rules_fix.sql
[ ] All 20250919_* and 20250920_* migrations (label events, UUID, training items)
[ ] All 20250921_* migrations (metrics, market cache, model registry, feature flags)
[ ] 20260202_category_completion.sql
[ ] 20260202_ingest_pipeline_tables.sql
[ ] 20260202_user_price_alerts.sql
[ ] 20260206_model_registry_expand.sql
[ ] 20260206_beta_tables.sql
[ ] 20260206_events_system.sql
[ ] 20260206_events_enhance.sql
[ ] 20260209_canary_and_matviews.sql
[ ] 20260209_missing_indexes.sql
[ ] 20260210_evidence_native.sql          (evidence layer: 9 schema additions)
[ ] 20260210_taxonomy_registry.sql        (taxonomy tables)
[ ] 20260210_object_pointers.sql          (S3 object pointers)
[ ] 20260211_push_tokens.sql              (push notification tokens)
[ ] 20260212_performance_indexes_and_user_settings.sql
[ ] 20260212_alert_history_batch_index.sql
[ ] 20260212_vision_queue_status_index.sql
[ ] 20260212_rls_enforcement.sql
[ ] 20260212_canonical_item_registry.sql
[ ] 20260213_smart_deal_agent.sql         (purchase mandates + deals)
[ ] 20260218_subscriptions.sql            (Stripe subscription tracking)
[ ] 20260218_beta_signups.sql             (beta signup table)
[ ] 20260219_portfolio_attributes.sql     (portfolio attributes)
[ ] 20260219_bugfix_audit.sql             (bugfix audit)
[ ] 20260220_catalog_learning.sql         (catalog suggestions + candidates)
[ ] 20260221_user_blocks.sql              (user blocks + RLS)
[ ] 20260222_currency_geo_shipping.sql    (currencies, geo, shipping)
[ ] 20260222_events_improvements.sql      (event templates, sponsors, RSVP)
[ ] 20260222_build_paint_improvements.sql (build & paint projects)
[ ] 20260223_add_performance_indexes.sql  (performance indexes)
[ ] 20260322_build_paint_status_pipeline.sql (category-specific status pipelines)
[ ] 20260224_user_privacy_settings.sql    (privacy settings + RLS)
[ ] 20260224_add_indexes_v2.sql           (category_follows + events indexes)

--- Supabase Auth Configuration ---

[ ] Enable email/password sign-up (Authentication > Providers > Email)
[ ] Set email confirmation to REQUIRED
[ ] Customize email templates (confirm signup, reset password, magic link)
    - Templates at: Authentication > Email Templates
    - Use your branding (Atlantis, Tiffany Blue #81D8D0)
[ ] Set redirect URLs in Authentication > URL Configuration:
    - Site URL: https://collectai.app (or your domain)
    - Redirect URLs: collectai://reset-password, collectai://subscription
[ ] Enable Apple OAuth provider:
    - Authentication > Providers > Apple > Enable
    - Requires Apple Developer account (see Section 7)
[ ] Enable Google OAuth provider:
    - Authentication > Providers > Google > Enable
    - Requires Google Cloud OAuth credentials (see Section 8)


================================================================================
 3. EC2 / SERVER SETUP
================================================================================

[ ] Ensure EC2 instance is running (current: 3.75.182.41)
[ ] SSH into EC2 and install Docker + Docker Compose:
    sudo apt update && sudo apt install -y docker.io docker-compose-plugin
    sudo systemctl enable docker && sudo systemctl start docker
    sudo usermod -aG docker $USER
[ ] Install nginx and certbot:
    sudo apt install -y nginx certbot python3-certbot-nginx
[ ] Copy nginx config:
    sudo cp deploy/nginx.conf /etc/nginx/sites-available/collectai
    sudo ln -s /etc/nginx/sites-available/collectai /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default
[ ] Get SSL certificate (DNS must be pointing to EC2 first!):
    sudo certbot --nginx -d api.collectai.app
[ ] Verify nginx:
    sudo nginx -t && sudo systemctl reload nginx
[ ] Verify auto-renewal:
    sudo certbot renew --dry-run
[ ] Create app directory:
    sudo mkdir -p /opt/collectai && cd /opt/collectai
[ ] Copy docker-compose.yml to /opt/collectai/
[ ] Create production .env file (see Section 4)


================================================================================
 4. PRODUCTION .ENV FILE
================================================================================

Create /opt/collectai/.env on the EC2 instance with these values.
Generate secrets with: openssl rand -hex 32

--- REQUIRED (app will not start without these) ---

[ ] DEV_MODE=false
[ ] DB_ENABLED=true
[ ] DB_DSN=postgresql://postgres:<password>@db.<project>.supabase.co:5432/postgres
[ ] SUPABASE_URL=https://<project>.supabase.co
[ ] SUPABASE_KEY=<anon-key>
[ ] SUPABASE_SERVICE_KEY=<service-role-key>
[ ] SUPABASE_JWT_SECRET=<jwt-secret>
[ ] SUPABASE_JWT_ISSUER=https://<project>.supabase.co/auth/v1
[ ] OPS_API_KEY=<generate-with-openssl-rand-hex-32>
[ ] API_SHARED_SECRET=<generate-with-openssl-rand-hex-32>

--- SECURITY ---

[ ] CORS_ORIGINS=https://collectai.app,https://www.collectai.app,https://api.collectai.app
[ ] TRUSTED_HOSTS=api.collectai.app,collectai.app,www.collectai.app
[ ] RATE_LIMIT_ENABLED=true
[ ] RATE_LIMIT_RPM=60
[ ] DEBUG=false
[ ] DB_SSL_ALLOW_SELF_SIGNED=0

--- STRIPE (required for subscriptions) ---

[ ] STRIPE_SECRET_KEY=sk_live_...          (from stripe.com/dashboard/apikeys)
[ ] STRIPE_WEBHOOK_SECRET=whsec_...        (from Stripe webhook setup)
[ ] STRIPE_PRICE_ID_PRO=price_...          (from Stripe product setup)
[ ] STRIPE_PRICE_ID_PREMIUM=price_...      (from Stripe product setup)

--- AWS / S3 (required for image storage) ---

[ ] AWS_ACCESS_KEY_ID=AKIA...
[ ] AWS_SECRET_ACCESS_KEY=...
[ ] AWS_REGION=eu-west-1
[ ] CATALOG_IMAGES_S3_BUCKET=collectai-artifacts
[ ] USER_UPLOADS_S3_BUCKET=collectai-artifacts
[ ] ML_MODELS_S3_BUCKET=collectai-ml-models

--- SENTRY (strongly recommended) ---

[ ] SENTRY_DSN=https://...@sentry.io/...   (from sentry.io project)
[ ] SENTRY_ENV=production
[ ] SENTRY_TRACES_RATE=0.1

--- ML / VISION (optional — features degrade gracefully without) ---

[ ] OPENAI_API_KEY=sk-...                   (for vision classification fallback)
[ ] FAL_KEY=...                             (for CLIP image embeddings)

--- MARKETPLACE APIs (optional — marketplace features degrade without) ---

[ ] EBAY_CLIENT_ID=...
[ ] EBAY_CLIENT_SECRET=...
[ ] TCGPLAYER_BEARER_TOKEN=...
[ ] EBAY_AFFILIATE_CAMPAIGN_ID=...
[ ] TCGPLAYER_AFFILIATE_ID=...
[ ] CARDMARKET_AFFILIATE_ID=...

--- FIRECRAWL (optional — URL import degrades without) ---

[ ] FIRECRAWL_API_KEY=...

--- WORKERS (enable when ready) ---

[ ] MONITOR_ENABLED=false                   (set true to enable price monitor)
[ ] DEAL_DISCOVERY_ENABLED=false            (set true to enable deal scanner)
[ ] AUCTION_ALERT_ENABLED=false             (set true to enable auction end-time alerts)


================================================================================
 5. STRIPE SETUP
================================================================================

[ ] Create Stripe account at stripe.com (if not already done)
[ ] Switch to Live Mode (toggle in Stripe Dashboard top-right)
[ ] Create Products & Prices:
    - Product 1: "Atlantis Pro"
      - Price: EUR 4.99/month, recurring
      - Copy the price_id -> STRIPE_PRICE_ID_PRO
    - Product 2: "Atlantis Premium"
      - Price: EUR 9.99/month, recurring
      - Copy the price_id -> STRIPE_PRICE_ID_PREMIUM
[ ] Set up Webhook endpoint:
    - URL: https://api.collectai.app/billing/webhook
    - Events to listen for:
      * checkout.session.completed
      * customer.subscription.updated
      * customer.subscription.deleted
      * invoice.payment_failed
    - Copy the Signing secret -> STRIPE_WEBHOOK_SECRET
[ ] Configure Customer Portal:
    - Settings > Billing > Customer Portal
    - Enable: Cancel subscription, Switch plans, Update payment method
    - Set return URL: collectai://settings
[ ] Test with Stripe test mode first (sk_test_...) before going live


================================================================================
 6. AWS SETUP
================================================================================

[ ] Create IAM user with S3 access:
    - Policy: AmazonS3FullAccess (or scoped to collectai-* buckets)
    - Save Access Key ID + Secret
[ ] Create S3 buckets:
    - collectai-artifacts (for images, exports)
    - collectai-ml-models (for ML model files)
    - Region: eu-west-1
    - Block all public access (use presigned URLs)
[ ] Optional: Create CloudFront distribution for collectai-artifacts
    - Origin: collectai-artifacts.s3.eu-west-1.amazonaws.com
    - Copy distribution URL -> CATALOG_IMAGES_CDN_URL, USER_UPLOADS_CDN_URL


================================================================================
 7. APPLE DEVELOPER SETUP
================================================================================

[ ] Enroll in Apple Developer Program ($99/year) at developer.apple.com
[ ] Create App ID:
    - Identifier: com.collectai.app
    - Capabilities: Sign In with Apple, Push Notifications, Associated Domains
[ ] Configure Sign In with Apple:
    - Service IDs > Create new > identifier: com.collectai.app.auth
    - Enable Sign In with Apple
    - Return URL: https://<project>.supabase.co/auth/v1/callback
[ ] Set up in Supabase:
    - Authentication > Providers > Apple
    - Enter Service ID, Team ID, Key ID, and private key (.p8)
[ ] Create App Store Connect record:
    - App name: Atlantis
    - Primary language: English
    - Bundle ID: com.collectai.app
    - SKU: collectai-1
[ ] Fill in eas.json submit credentials:
    - appleId: your Apple ID email
    - ascAppId: App Store Connect app ID (numeric)
    - appleTeamId: your Team ID


================================================================================
 8. GOOGLE CLOUD / PLAY SETUP
================================================================================

--- Google OAuth (for Google Sign In) ---

[ ] Go to console.cloud.google.com > APIs & Services > Credentials
[ ] Create OAuth 2.0 Client IDs:
    - Web application:
      * Authorized redirect URIs: https://<project>.supabase.co/auth/v1/callback
      * Copy Client ID -> EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID
    - iOS:
      * Bundle ID: com.collectai.app
      * Copy Client ID -> EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID
    - Android:
      * Package name: com.collectai.app
      * SHA-1 fingerprint (from your signing key)
      * Copy Client ID -> EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID
[ ] Set up in Supabase:
    - Authentication > Providers > Google
    - Enter Web Client ID and Client Secret

--- Google Play Console ---

[ ] Enroll in Google Play Developer Program ($25 one-time) at play.google.com/console
[ ] Create app: Atlantis - Collectibles Tracker
[ ] Create service account for EAS Submit:
    - Google Cloud Console > IAM > Service Accounts
    - Grant "Service Account User" role
    - Create JSON key -> save path for eas.json serviceAccountKeyPath
[ ] Fill eas.json Android submit credentials:
    - serviceAccountKeyPath: path to service account JSON key
    - track: "internal" (for testing), then "production" for release


================================================================================
 9. SENTRY SETUP
================================================================================

[ ] Create Sentry account at sentry.io (free tier: 5K events/month)
[ ] Create two projects:
    - collectai-backend (Python / FastAPI)
      * Copy DSN -> SENTRY_DSN (backend .env)
    - collectai-mobile (React Native)
      * Copy DSN -> EXPO_PUBLIC_SENTRY_DSN (frontend .env / EAS secrets)
[ ] Install @sentry/react-native in the project:
    npm install @sentry/react-native
[ ] Set SENTRY_ENV=production in backend .env


================================================================================
 10. DEPLOY BACKEND
================================================================================

[ ] Copy .env and docker-compose.yml to EC2 /opt/collectai/
[ ] Build and start Docker containers:
    cd /opt/collectai
    docker compose up -d --build
[ ] Verify health check:
    curl -sf https://api.collectai.app/healthz
    Expected: {"ok":true,"db_configured":true,"db":"up","db_ms":...}
[ ] Verify version:
    curl https://api.collectai.app/version
[ ] Check admin dashboard:
    curl -H "X-Ops-Key: <your-ops-key>" https://api.collectai.app/ops/dashboard/stats
[ ] Check logs for errors:
    docker compose logs -f api
[ ] Test Stripe webhook (use Stripe CLI):
    stripe listen --forward-to https://api.collectai.app/billing/webhook


================================================================================
 11. MOBILE APP — FRONTEND .ENV
================================================================================

Create a local .env for the frontend (or use EAS Secrets for builds):

[ ] EXPO_PUBLIC_API_URL=https://api.collectai.app
[ ] EXPO_PUBLIC_API_BASE_URL=https://api.collectai.app
[ ] EXPO_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
[ ] EXPO_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
[ ] EXPO_PUBLIC_SUPABASE_MODE=strict
[ ] EXPO_PUBLIC_SENTRY_DSN=<sentry-dsn-for-mobile>
[ ] EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=<google-web-client-id>
[ ] EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID=<google-ios-client-id>
[ ] EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID=<google-android-client-id>


================================================================================
 12. APP ASSETS (DESIGN)
================================================================================

Replace placeholder assets before submitting to stores:

[ ] App icon: assets/icon.png (1024x1024, no transparency, no rounded corners)
[ ] Splash screen: assets/splash.png (use Tiffany Blue #81D8D0 background)
[ ] Adaptive icon: assets/adaptive-icon.png (512x512 foreground, safe zone)
[ ] Feature graphic (Google Play): 1024x500 banner image
[ ] App Store screenshots (6-10 per device size):
    - iPhone 6.9" (1320x2868)  — required
    - iPhone 6.7" (1290x2796)  — required
    - iPhone 6.5" (1242x2688)  — if supporting older devices
    - iPad Pro 13" (2064x2752) — if supportsTablet: true

    Recommended screenshots:
    1. Collection overview (portfolio grid with values)
    2. Item detail (price evidence + provenance)
    3. QuickScan (camera scanning)
    4. Price intelligence (valuation breakdown)
    5. Deal discovery (mandates + matched deals)
    6. Events calendar
    7. Category browser (36 categories)
    8. Analytics dashboard


================================================================================
 13. APP STORE METADATA
================================================================================

[ ] Write App Store description (store in docs/store-description.md)
[ ] Prepare metadata:
    - App Name: Atlantis
    - Subtitle: Smart Collectibles Tracker
    - Category: Lifestyle (primary), Shopping (secondary)
    - Keywords: collectibles, valuation, price tracker, collection manager,
                funko, pokemon, trading cards, barcode scanner
    - Privacy URL: https://collectai.app/privacy
    - Support URL: https://collectai.app/support
    - Marketing URL: https://collectai.app
    - Content Rating: Everyone / 4+
[ ] Google Play specific:
    - Short description: Track, value, and discover collectibles with AI
    - Full description: same as iOS but can be longer
    - Category: Lifestyle
    - Content rating questionnaire: complete in Play Console


================================================================================
 14. BUILD & SUBMIT
================================================================================

[ ] Install EAS CLI: npm install -g eas-cli
[ ] Login: eas login
[ ] Set EAS Secrets (env vars for build):
    eas secret:create --name EXPO_PUBLIC_API_URL --value https://api.collectai.app
    eas secret:create --name EXPO_PUBLIC_SUPABASE_URL --value https://<project>.supabase.co
    eas secret:create --name EXPO_PUBLIC_SUPABASE_ANON_KEY --value <anon-key>
    eas secret:create --name EXPO_PUBLIC_SUPABASE_MODE --value strict
    (... repeat for all EXPO_PUBLIC_* vars)

[ ] Build iOS:
    eas build --platform ios --profile production

[ ] Build Android:
    eas build --platform android --profile production

[ ] Test builds on real devices before submitting!

[ ] Submit iOS:
    eas submit --platform ios --profile production

[ ] Submit Android:
    eas submit --platform android --profile production

[ ] Monitor review status in App Store Connect and Google Play Console


================================================================================
 15. POST-LAUNCH
================================================================================

[ ] Verify Stripe webhooks are firing correctly (Stripe Dashboard > Webhooks > logs)
[ ] Monitor Sentry for errors (both backend and mobile)
[ ] Monitor health check: set up uptime monitoring (e.g. UptimeRobot, Better Uptime)
    - URL: https://api.collectai.app/healthz
    - Interval: 5 minutes
    - Alert: email/Slack on failure
[ ] Set up log rotation on EC2 (Docker logs can grow large)
[ ] Schedule database backups (Supabase does daily backups on Pro plan)
[ ] Secret rotation: rotate all exposed tokens (see docs/DEPLOYMENT.md > Secret Rotation)
    - Run git filter-repo to remove .env from git history
    - Rotate Supabase keys if they were ever committed
    - Generate new OPS_API_KEY and API_SHARED_SECRET
[ ] Enable workers when ready:
    - MONITOR_ENABLED=true  (price monitoring)
    - DEAL_DISCOVERY_ENABLED=true  (deal scanning)
[ ] Set up CI/CD auto-deploy:
    - Add GitHub Secrets: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
      ECR_REGISTRY, EC2_HOST, EC2_USER, EC2_SSH_KEY
    - Create GitHub Environment "production" with required reviewers
    - In ci.yml: change `if: false && github.ref == ...` to `if: github.ref == ...`
[ ] Landing page / website at collectai.app with:
    - Privacy Policy (must match in-app version)
    - Terms of Service (must match in-app version)
    - Support / Contact page
    - App Store & Google Play download badges


================================================================================
 QUICK REFERENCE — SECRETS TO GENERATE
================================================================================

  openssl rand -hex 32    # OPS_API_KEY
  openssl rand -hex 32    # API_SHARED_SECRET

  From Supabase Dashboard: SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY,
                           SUPABASE_JWT_SECRET, DB_DSN
  From Stripe Dashboard:   STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET,
                           STRIPE_PRICE_ID_PRO, STRIPE_PRICE_ID_PREMIUM
  From AWS Console:        AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
  From Google Cloud:       GOOGLE_WEB/IOS/ANDROID_CLIENT_ID
  From Sentry:             SENTRY_DSN (backend), EXPO_PUBLIC_SENTRY_DSN (mobile)
  From Apple Developer:    Team ID, Key ID, .p8 key (for Sign In with Apple)


================================================================================
 END OF CHECKLIST
================================================================================
