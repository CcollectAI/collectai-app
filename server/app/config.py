"""
Central configuration for the CollectAI backend (``app/`` package).

Every environment-variable-backed setting used by the FastAPI app should be
defined **here** and imported by the module that needs it.  This avoids
duplicate ``os.getenv`` calls scattered across the codebase and makes it
trivial to see the full list of knobs at a glance.

Standalone scripts, pipelines, and workers that do NOT import the ``app``
package may still read env vars directly (they run in separate processes).
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# General / service
# ---------------------------------------------------------------------------

SERVICE_VERSION: str = os.getenv("SERVICE_VERSION", "0.1.0")
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
DEV_MODE: bool = os.getenv("DEV_MODE", "false").lower() in ("true", "1", "yes")
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

# Safety: DEV_MODE must NEVER be active in production
if DEV_MODE and ENVIRONMENT == "production":
    raise RuntimeError(
        "FATAL: DEV_MODE=true is forbidden when ENVIRONMENT=production. "
        "This would bypass JWT authentication. Refusing to start."
    )

# ---------------------------------------------------------------------------
# Database (asyncpg)
# ---------------------------------------------------------------------------

DB_ENABLED: bool = os.getenv("DB_ENABLED", "false").lower() == "true"
DB_DSN: str = os.getenv("DB_DSN", "")
# Direct DSN (session-mode Postgres, not the pooler) for bulk-write workers
# like datalake_export_worker or one-shot migrations. Pooler transaction mode
# has a 30s statement_timeout that kills long INSERTs; a direct connection
# side-steps it. Falls back to DB_DSN when not set — see
# docs/DATA_SCALING_PLAN.md §6 (governance rule on pooler vs direct).
DB_DSN_DIRECT: str = os.getenv("DB_DSN_DIRECT", "") or DB_DSN
DB_POOL_MIN: int = int(os.getenv("DB_POOL_MIN_SIZE", "5"))
DB_POOL_MAX: int = int(os.getenv("DB_POOL_MAX_SIZE", "20"))
DB_COMMAND_TIMEOUT: float = float(os.getenv("DB_COMMAND_TIMEOUT", "30"))
DB_CONNECT_TIMEOUT: float = float(os.getenv("DB_CONNECT_TIMEOUT", "10"))
DB_IDLE_LIFETIME: float = float(os.getenv("DB_MAX_IDLE_LIFETIME", "300"))

# ---------------------------------------------------------------------------
# Auth / JWT
# ---------------------------------------------------------------------------

DEV_USER_ID: str = os.getenv("DEV_USER_ID", "")
JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")
JWT_ISSUER: str = os.getenv("SUPABASE_JWT_ISSUER", "")  # e.g. "https://<project>.supabase.co/auth/v1"
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

# ---------------------------------------------------------------------------
# API authentication (inter-service shared secret)
# ---------------------------------------------------------------------------

API_SHARED_SECRET: str | None = os.environ.get("API_SHARED_SECRET")
SIGNALS_BASE_URL: str = os.getenv("SIGNALS_BASE_URL", "http://127.0.0.1:8082")

# ---------------------------------------------------------------------------
# Ops endpoint authentication
# ---------------------------------------------------------------------------

OPS_API_KEY: str = os.getenv("OPS_API_KEY", "")

# ---------------------------------------------------------------------------
# Sentry
# ---------------------------------------------------------------------------

SENTRY_DSN: str | None = os.getenv("SENTRY_DSN")
SENTRY_TRACES_RATE: float = float(os.getenv("SENTRY_TRACES_RATE", "0.1"))
SENTRY_ENV: str = os.getenv("SENTRY_ENV", "development")

# ---------------------------------------------------------------------------
# CORS / trusted hosts
# ---------------------------------------------------------------------------

CORS_ORIGINS: list[str] = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:8080,http://localhost:8081,"
    "http://127.0.0.1:3000,http://127.0.0.1:8080,http://127.0.0.1:8081,"
    "exp://localhost:*,"
    "https://app.collectai.io,https://collectai.app,https://www.collectai.app,"
    "https://api.collectai.app",
).split(",")

# Extra Expo dev origins — set via env for your local IP, e.g.
# EXPO_DEV_ORIGINS="exp://192.168.1.42:*"
_expo_dev = os.getenv("EXPO_DEV_ORIGINS", "")
if _expo_dev:
    CORS_ORIGINS.extend(o.strip() for o in _expo_dev.split(",") if o.strip())

TRUSTED_HOSTS: list[str] = (
    os.getenv("TRUSTED_HOSTS", "").split(",") if os.getenv("TRUSTED_HOSTS") else []
)

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

RATE_LIMIT_RPM: int = int(os.getenv("RATE_LIMIT_RPM", "60"))
RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("1", "true", "yes")
PER_USER_RATE_LIMIT_ENABLED: bool = os.getenv(
    "PER_USER_RATE_LIMIT_ENABLED", "true"
).lower() in ("1", "true", "yes")

# ---------------------------------------------------------------------------
# Body size limit
# ---------------------------------------------------------------------------

MAX_BODY_BYTES: int = int(os.getenv("MAX_BODY_BYTES", str(10 * 1024 * 1024)))  # 10 MB

# ---------------------------------------------------------------------------
# AWS / S3
# ---------------------------------------------------------------------------

AWS_REGION: str = os.environ.get("AWS_REGION", "eu-west-1")
# General-purpose S3 bucket alias (defaults to catalog images bucket)
AWS_S3_BUCKET: str = os.environ.get("AWS_S3_BUCKET", "")

# Catalog images bucket (used by s3_client, photo_upload_router)
# NOTE: Enable S3 Intelligent-Tiering on these buckets for 30-50% storage
# savings on infrequently accessed images:
#   aws s3api put-bucket-intelligent-tiering-configuration \
#     --bucket collectai-artifacts --id "auto-tier" \
#     --intelligent-tiering-configuration '{"Id":"auto-tier","Status":"Enabled",...}'
CATALOG_IMAGES_S3_BUCKET: str = os.environ.get("CATALOG_IMAGES_S3_BUCKET", "collectai-artifacts")
CATALOG_IMAGES_CDN_URL: str = os.environ.get("CATALOG_IMAGES_CDN_URL", "")

# User uploads (photo_upload_router)
USER_UPLOADS_S3_BUCKET: str = os.environ.get("USER_UPLOADS_S3_BUCKET", "collectai-artifacts")
USER_UPLOADS_CDN_URL: str = os.environ.get("USER_UPLOADS_CDN_URL", "")
USER_UPLOADS_MAX_SIZE: int = int(os.environ.get("USER_UPLOADS_MAX_SIZE", "2097152"))  # 2 MB

# ML model S3
ML_MODELS_S3_BUCKET: str = os.getenv("ML_MODELS_S3_BUCKET", "collectai-ml-models")

# ---------------------------------------------------------------------------
# ML / Vision
# ---------------------------------------------------------------------------

MODEL_CANARY_TRAFFIC_PCT: float = float(os.getenv("MODEL_CANARY_TRAFFIC_PCT", "5"))
VISION_MAX_IMAGE_BYTES: int = int(os.getenv("VISION_MAX_IMAGE_BYTES", str(20 * 1024 * 1024)))
INTAKE_MAX_IMAGE_BYTES: int = int(os.getenv("INTAKE_MAX_IMAGE_BYTES", str(20 * 1024 * 1024)))

FAL_KEY: str = os.getenv("FAL_KEY", "")
FAL_CLIP_URL: str = os.getenv("FAL_CLIP_URL", "https://fal.run/fal-ai/clip")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_VISION_MODEL: str = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")

# ---------------------------------------------------------------------------
# Firecrawl
# ---------------------------------------------------------------------------

FIRECRAWL_API_KEY: str = os.getenv("FIRECRAWL_API_KEY", "")
FIRECRAWL_BASE_URL: str = os.getenv("FIRECRAWL_BASE_URL", "https://api.firecrawl.dev/v1")

# ---------------------------------------------------------------------------
# Crawl4AI (local web crawler)
# ---------------------------------------------------------------------------

CRAWL4AI_ENABLED: bool = os.getenv("CRAWL4AI_ENABLED", "true").lower() in ("1", "true", "yes")
CRAWL4AI_MAX_CONCURRENT: int = int(os.getenv("CRAWL4AI_MAX_CONCURRENT", "3"))
CRAWL4AI_TIMEOUT: int = int(os.getenv("CRAWL4AI_TIMEOUT", "30"))
CRAWL4AI_HEADLESS: bool = os.getenv("CRAWL4AI_HEADLESS", "true").lower() in ("1", "true", "yes")

# ---------------------------------------------------------------------------
# Scrape.do (managed proxy scraping service)
# ---------------------------------------------------------------------------

SCRAPEDO_API_KEY: str = os.getenv("SCRAPEDO_API_KEY", "")

# ---------------------------------------------------------------------------
# SerpAPI (Google Shopping)
# ---------------------------------------------------------------------------

SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "")

# ---------------------------------------------------------------------------
# FX rates (shared across marketplace adapters)
# ---------------------------------------------------------------------------
# These are fallback rates used when the live FX API is unavailable.
# The frontend (src/lib/settings.tsx) stores rates as EUR→foreign:
#   { USD: 1.08, GBP: 0.86, JPY: 164.0 }
# The backend stores the inverse (foreign→EUR) for price normalisation.
# Keep both sides in sync when updating defaults.

USD_TO_EUR: float = float(os.getenv("USD_TO_EUR", "0.92"))
GBP_TO_EUR: float = float(os.getenv("GBP_TO_EUR", "1.16"))
JPY_TO_EUR: float = float(os.getenv("JPY_TO_EUR", "0.0061"))
KRW_TO_EUR: float = float(os.getenv("KRW_TO_EUR", "0.00067"))
AUD_TO_EUR: float = float(os.getenv("AUD_TO_EUR", "0.60"))
CAD_TO_EUR: float = float(os.getenv("CAD_TO_EUR", "0.66"))

# ---------------------------------------------------------------------------
# Marketplace API credentials
# ---------------------------------------------------------------------------

# eBay: EBAY_CLIENT_ID/SECRET are sandbox; EBAY_APP_ID is the production Finding API key
# Get from https://developer.ebay.com/my/keys (Production column)
EBAY_CLIENT_ID: str = os.getenv("EBAY_CLIENT_ID", "")
EBAY_CLIENT_SECRET: str = os.getenv("EBAY_CLIENT_SECRET", "")
EBAY_APP_ID: str = os.getenv("EBAY_APP_ID", "")  # Production App ID (Finding/Browse API)

# TCGPlayer: BEARER_TOKEN is the legacy token; PUBLIC/PRIVATE keys are for OAuth flow
# Get from https://developer.tcgplayer.com/developer-applications
TCGPLAYER_BEARER_TOKEN: str = os.getenv("TCGPLAYER_BEARER_TOKEN", "")
TCGPLAYER_PUBLIC_KEY: str = os.getenv("TCGPLAYER_PUBLIC_KEY", "")
TCGPLAYER_PRIVATE_KEY: str = os.getenv("TCGPLAYER_PRIVATE_KEY", "")
CARDMARKET_APP_TOKEN: str = os.getenv("CARDMARKET_APP_TOKEN", "")
CARDMARKET_APP_SECRET: str = os.getenv("CARDMARKET_APP_SECRET", "")
DISCOGS_PERSONAL_TOKEN: str = os.getenv("DISCOGS_PERSONAL_TOKEN", "")
PRICECHARTING_API_KEY: str = os.getenv("PRICECHARTING_API_KEY", "")
STOCKX_API_KEY: str = os.getenv("STOCKX_API_KEY", "")
ETSY_API_KEY: str = os.getenv("ETSY_API_KEY", "")
BRICKLINK_CONSUMER_KEY: str = os.getenv("BRICKLINK_CONSUMER_KEY", "")
BRICKLINK_CONSUMER_SECRET: str = os.getenv("BRICKLINK_CONSUMER_SECRET", "")
BRICKLINK_TOKEN: str = os.getenv("BRICKLINK_TOKEN", "")
BRICKLINK_TOKEN_SECRET: str = os.getenv("BRICKLINK_TOKEN_SECRET", "")

# ---------------------------------------------------------------------------
# Price monitor
# ---------------------------------------------------------------------------

MONITOR_ENABLED: bool = os.getenv("MONITOR_ENABLED", "false").lower() in ("1", "true", "yes")

# ---------------------------------------------------------------------------
# Catalog Learning
# ---------------------------------------------------------------------------

CATALOG_LEARNING_ENABLED: bool = os.getenv("CATALOG_LEARNING_ENABLED", "false").lower() in ("1", "true", "yes")
CATALOG_LEARNING_INTERVAL_SECS: int = int(os.getenv("CATALOG_LEARNING_INTERVAL_SECS", "86400"))  # daily
CATALOG_AUTO_MAP_THRESHOLD: int = int(os.getenv("CATALOG_AUTO_MAP_THRESHOLD", "3"))
CATALOG_NEW_CATEGORY_THRESHOLD: int = int(os.getenv("CATALOG_NEW_CATEGORY_THRESHOLD", "25"))

# ---------------------------------------------------------------------------
# Deal Discovery (Smart Deal Agent)
# ---------------------------------------------------------------------------

DEAL_DISCOVERY_ENABLED: bool = os.getenv("DEAL_DISCOVERY_ENABLED", "false").lower() in ("1", "true", "yes")
DEAL_SCAN_INTERVAL_SECS: int = int(os.getenv("DEAL_SCAN_INTERVAL_SECS", "1800"))
EBAY_AFFILIATE_CAMPAIGN_ID: str = os.getenv("EBAY_AFFILIATE_CAMPAIGN_ID", "")
TCGPLAYER_AFFILIATE_ID: str = os.getenv("TCGPLAYER_AFFILIATE_ID", "")
CARDMARKET_AFFILIATE_ID: str = os.getenv("CARDMARKET_AFFILIATE_ID", "")
MERCARI_AFFILIATE_ID: str = os.getenv("MERCARI_AFFILIATE_ID", "")
DISCOGS_AFFILIATE_TOKEN: str = os.getenv("DISCOGS_AFFILIATE_TOKEN", "")
STOCKX_AFFILIATE_ID: str = os.getenv("STOCKX_AFFILIATE_ID", "")
BRICKLINK_AFFILIATE_ID: str = os.getenv("BRICKLINK_AFFILIATE_ID", "")
WHATNOT_AFFILIATE_ID: str = os.getenv("WHATNOT_AFFILIATE_ID", "")  # Impact.com, 1-3.5%
CATAWIKI_AFFILIATE_ID: str = os.getenv("CATAWIKI_AFFILIATE_ID", "")  # Partnerize, ~7-10%
KEH_AFFILIATE_ID: str = os.getenv("KEH_AFFILIATE_ID", "")  # ShareASale, 1.6-3.2%
MPB_AFFILIATE_ID: str = os.getenv("MPB_AFFILIATE_ID", "")  # FlexOffers/Sovrn, 2%
MASTEROFMALT_AFFILIATE_ID: str = os.getenv("MASTEROFMALT_AFFILIATE_ID", "")  # Affiliate Future, 5-7.66%
POPMART_AFFILIATE_ID: str = os.getenv("POPMART_AFFILIATE_ID", "")  # Yeesshh/Digidip, 1-8%
DROP_AFFILIATE_ID: str = os.getenv("DROP_AFFILIATE_ID", "")  # FlexOffers, 1.6-2.4%
CHRONO24_AFFILIATE_ID: str = os.getenv("CHRONO24_AFFILIATE_ID", "")  # Direct partnership
AMIAMI_AFFILIATE_ID: str = os.getenv("AMIAMI_AFFILIATE_ID", "")  # Sovrn Commerce

# ---------------------------------------------------------------------------
# Task Queue Worker
# ---------------------------------------------------------------------------

TASK_WORKER_ENABLED: bool = os.getenv("TASK_WORKER_ENABLED", "false").lower() in ("1", "true", "yes")
TASK_WORKER_POLL_INTERVAL: float = float(os.getenv("TASK_WORKER_POLL_INTERVAL", "5.0"))

# ---------------------------------------------------------------------------
# Stripe (Payments / Subscriptions)
# ---------------------------------------------------------------------------

STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Plan subscription price IDs (create in Stripe Dashboard → Products → Prices)
# Pro plan
STRIPE_PRICE_ID_PRO: str = os.getenv("STRIPE_PRICE_ID_PRO", "")  # legacy/default
STRIPE_PRICE_PRO_MONTHLY: str = os.getenv("STRIPE_PRICE_PRO_MONTHLY", "")  # e.g. price_xxx
STRIPE_PRICE_PRO_YEARLY: str = os.getenv("STRIPE_PRICE_PRO_YEARLY", "")   # e.g. price_yyy
# Premium plan
STRIPE_PRICE_ID_PREMIUM: str = os.getenv("STRIPE_PRICE_ID_PREMIUM", "")  # legacy/default
STRIPE_PRICE_PREMIUM_MONTHLY: str = os.getenv("STRIPE_PRICE_PREMIUM_MONTHLY", "")  # e.g. price_xxx
STRIPE_PRICE_PREMIUM_YEARLY: str = os.getenv("STRIPE_PRICE_PREMIUM_YEARLY", "")   # e.g. price_yyy

# Sponsored events tiers (one-time payments)
STRIPE_PRICE_ID_SPONSOR_FEATURED: str = os.getenv("STRIPE_PRICE_ID_SPONSOR_FEATURED", "")
STRIPE_PRICE_ID_SPONSOR_PROMOTED: str = os.getenv("STRIPE_PRICE_ID_SPONSOR_PROMOTED", "")
STRIPE_PRICE_ID_SPONSOR_SPOTLIGHT: str = os.getenv("STRIPE_PRICE_ID_SPONSOR_SPOTLIGHT", "")

# Sponsor monthly subscription price IDs (recurring)
STRIPE_PRICE_ID_SPONSOR_SUB_FEATURED: str = os.getenv("STRIPE_PRICE_ID_SPONSOR_SUB_FEATURED", "")
STRIPE_PRICE_ID_SPONSOR_SUB_PROMOTED: str = os.getenv("STRIPE_PRICE_ID_SPONSOR_SUB_PROMOTED", "")
STRIPE_PRICE_ID_SPONSOR_SUB_SPOTLIGHT: str = os.getenv("STRIPE_PRICE_ID_SPONSOR_SUB_SPOTLIGHT", "")

# ---------------------------------------------------------------------------
# Redis (optional — falls back to in-memory cache when absent)
# ---------------------------------------------------------------------------

REDIS_URL: str | None = os.environ.get("REDIS_URL")

# ---------------------------------------------------------------------------
# Cache TTLs & thresholds
# ---------------------------------------------------------------------------

CACHE_TTL: int = int(os.environ.get("CACHE_TTL", "600"))
PRESIGN_EXPIRY: int = int(os.environ.get("PRESIGN_EXPIRY", "300"))
FX_CACHE_TTL: int = int(os.environ.get("FX_CACHE_TTL", "28800"))
GEO_CACHE_TTL: int = int(os.environ.get("GEO_CACHE_TTL", "86400"))
BARCODE_CACHE_TTL: int = int(os.environ.get("BARCODE_CACHE_TTL", "86400"))

# Sponsor tier prices (EUR cents)
SPONSOR_TIER_BASIC: int = int(os.environ.get("SPONSOR_TIER_BASIC", "2900"))
SPONSOR_TIER_PRO: int = int(os.environ.get("SPONSOR_TIER_PRO", "7900"))
SPONSOR_TIER_PREMIUM: int = int(os.environ.get("SPONSOR_TIER_PREMIUM", "19900"))

# Portfolio insight thresholds
OVEREXPOSURE_THRESHOLD: float = float(os.environ.get("OVEREXPOSURE_THRESHOLD", "0.40"))
HIGH_RISK_THRESHOLD: float = float(os.environ.get("HIGH_RISK_THRESHOLD", "0.50"))


# ---------------------------------------------------------------------------
# Spend budget (monthly cap for paid API calls)
# ---------------------------------------------------------------------------

MONTHLY_BUDGET_EUR: float = float(os.getenv("MONTHLY_BUDGET_EUR", "150.0"))

# ---------------------------------------------------------------------------
# Telegram Ops Alerts
# ---------------------------------------------------------------------------

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# ---------------------------------------------------------------------------
# Startup validation
# ---------------------------------------------------------------------------

def validate_config() -> None:
    """Validate configuration at startup. Call from main.py _startup().

    * In production (DEV_MODE=false): fail fast if critical keys are missing.
    * Always: warn about optional-but-important keys that are empty.
    """
    import logging
    import socket

    _log = logging.getLogger("collectai.config")

    # --- R15-1: DEV_MODE production guard ---
    if DEV_MODE:
        hostname = socket.gethostname().lower()
        is_ci = os.getenv("CI", "").lower() in ("true", "1")
        is_local = is_ci or any(
            hostname.startswith(prefix)
            for prefix in ("localhost", "127.")
        ) or hostname.endswith((".local", ".home"))

        if not is_local:
            _log.critical(
                "DEV_MODE=true on non-local host '%s'. "
                "This bypasses JWT auth! Disable DEV_MODE for production.",
                hostname,
            )
            raise SystemExit(1)
        _log.warning("DEV_MODE is active — JWT auth is bypassed for requests without Bearer tokens")

    # --- R15-2: Required keys (non-DEV only) ---
    if not DEV_MODE:
        missing: list[str] = []
        if DB_ENABLED and not DB_DSN:
            missing.append("DB_DSN")
        if not JWT_SECRET:
            missing.append("SUPABASE_JWT_SECRET")
        if not SUPABASE_URL:
            missing.append("SUPABASE_URL")
        if not OPS_API_KEY:
            missing.append("OPS_API_KEY")
        if not STRIPE_WEBHOOK_SECRET:
            missing.append("STRIPE_WEBHOOK_SECRET")
        if missing:
            _log.critical("Missing required env vars for production: %s", ", ".join(missing))
            raise SystemExit(1)

        # --- Bake-critical: alerting dead silence is a known footgun (L44, L46) ---
        # If the orchestrator's alert paths aren't wired, failures go unnoticed
        # until someone checks logs manually. Warn loudly but don't exit.
        if not os.getenv("TELEGRAM_BOT_TOKEN") or not os.getenv("TELEGRAM_CHAT_ID"):
            _log.warning(
                "TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set — bake worker "
                "failure alerts will be dropped. Set both to enable paging."
            )

        # CORS: warn if still using only localhost origins
        localhost_only = all(
            "localhost" in o or "127.0.0.1" in o or "192.168." in o or "10." in o
            for o in CORS_ORIGINS
        )
        if localhost_only:
            _log.warning(
                "CORS_ORIGINS contains only localhost origins. "
                "Set production origins (e.g. https://app.collectai.io) in CORS_ORIGINS."
            )

        # TRUSTED_HOSTS: warn if not configured
        if not TRUSTED_HOSTS or TRUSTED_HOSTS == [""]:
            _log.warning(
                "TRUSTED_HOSTS is not configured. "
                "Set to your domain (e.g. api.collectai.app,collectai.app) to prevent host header attacks."
            )

    # --- Stripe price ID validation ---
    # At least one price ID per plan should be set for billing to work.
    if STRIPE_SECRET_KEY:
        stripe_warnings: list[str] = []
        # Pro: check monthly/yearly or legacy fallback
        if not STRIPE_PRICE_PRO_MONTHLY and not STRIPE_PRICE_PRO_YEARLY and not STRIPE_PRICE_ID_PRO:
            stripe_warnings.append(
                "No Stripe Price ID for Pro plan. "
                "Set STRIPE_PRICE_PRO_MONTHLY/STRIPE_PRICE_PRO_YEARLY or STRIPE_PRICE_ID_PRO."
            )
        # Premium: check monthly/yearly or legacy fallback
        if not STRIPE_PRICE_PREMIUM_MONTHLY and not STRIPE_PRICE_PREMIUM_YEARLY and not STRIPE_PRICE_ID_PREMIUM:
            stripe_warnings.append(
                "No Stripe Price ID for Premium plan. "
                "Set STRIPE_PRICE_PREMIUM_MONTHLY/STRIPE_PRICE_PREMIUM_YEARLY or STRIPE_PRICE_ID_PREMIUM."
            )
        for w in stripe_warnings:
            _log.warning(w)

    # --- Warn about optional-but-important keys ---
    warn_keys = {
        "EBAY_CLIENT_ID": EBAY_CLIENT_ID,
        "EBAY_CLIENT_SECRET": EBAY_CLIENT_SECRET,
        "EBAY_APP_ID": EBAY_APP_ID,
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "FAL_KEY": FAL_KEY,
        "TCGPLAYER_BEARER_TOKEN": TCGPLAYER_BEARER_TOKEN,
        "TCGPLAYER_PUBLIC_KEY": TCGPLAYER_PUBLIC_KEY,
        "TCGPLAYER_PRIVATE_KEY": TCGPLAYER_PRIVATE_KEY,
        "SUPABASE_SERVICE_KEY": SUPABASE_SERVICE_KEY,
        "SENTRY_DSN": SENTRY_DSN or "",
        "STRIPE_SECRET_KEY": STRIPE_SECRET_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
    }
    empty = [k for k, v in warn_keys.items() if not v]
    if empty:
        _log.warning("Optional API keys not set (features will be degraded): %s", ", ".join(empty))
