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
DEV_MODE: bool = os.getenv("DEV_MODE", "false").lower() in ("true", "1", "yes")
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Database (asyncpg)
# ---------------------------------------------------------------------------

DB_ENABLED: bool = os.getenv("DB_ENABLED", "false").lower() == "true"
DB_DSN: str = os.getenv("DB_DSN", "")
DB_POOL_MIN: int = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
DB_POOL_MAX: int = int(os.getenv("DB_POOL_MAX_SIZE", "10"))
DB_COMMAND_TIMEOUT: float = float(os.getenv("DB_COMMAND_TIMEOUT", "30"))
DB_CONNECT_TIMEOUT: float = float(os.getenv("DB_CONNECT_TIMEOUT", "10"))
DB_IDLE_LIFETIME: float = float(os.getenv("DB_MAX_IDLE_LIFETIME", "300"))

# ---------------------------------------------------------------------------
# Auth / JWT
# ---------------------------------------------------------------------------

DEV_USER_ID: str = os.getenv("DEV_USER_ID", "")
JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")

# ---------------------------------------------------------------------------
# API authentication (inter-service shared secret)
# ---------------------------------------------------------------------------

API_SHARED_SECRET: str | None = os.environ.get("API_SHARED_SECRET")
SIGNALS_BASE_URL: str = os.getenv("SIGNALS_BASE_URL", "http://127.0.0.1:8082")

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
    "exp://localhost:*,exp://192.168.*:*,exp://10.*:*,"
    "https://app.collectai.io",
).split(",")

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

# Catalog images bucket (used by s3_client, photo_upload_router)
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
# FX rates (shared across marketplace adapters)
# ---------------------------------------------------------------------------

USD_TO_EUR: float = float(os.getenv("USD_TO_EUR", "0.92"))
JPY_TO_EUR: float = float(os.getenv("JPY_TO_EUR", "0.0061"))

# ---------------------------------------------------------------------------
# Marketplace API credentials
# ---------------------------------------------------------------------------

EBAY_CLIENT_ID: str = os.getenv("EBAY_CLIENT_ID", "")
EBAY_CLIENT_SECRET: str = os.getenv("EBAY_CLIENT_SECRET", "")
TCGPLAYER_BEARER_TOKEN: str = os.getenv("TCGPLAYER_BEARER_TOKEN", "")

# ---------------------------------------------------------------------------
# Price monitor
# ---------------------------------------------------------------------------

MONITOR_ENABLED: bool = os.getenv("MONITOR_ENABLED", "false").lower() in ("1", "true", "yes")
