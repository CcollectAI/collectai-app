"""
Shared utilities for catalog + price data import pipelines.

Usage:
    from import_common import SupabaseIngest, write_training_jsonl, log_progress

All import scripts follow this pattern:
    1. Fetch from external API -> normalize to category_items rows
    2. Upsert into Supabase category_items table
    3. Fetch price data -> write to data/{category}/train.jsonl
    4. Optionally populate market_hits table
    5. Optionally cache images to S3 (--cache-images flag)
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Structured Logging (#17)
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    name: str = "collectai.pipeline",
    level: str | None = None,
    log_file: str | None = None,
) -> logging.Logger:
    """Configure structured logging for pipeline scripts.

    Args:
        name: Logger name (e.g. 'collectai.import_pokemon')
        level: Log level string. Reads PIPELINE_LOG_LEVEL env var if not set.
        log_file: Optional file path. Reads PIPELINE_LOG_FILE env var if not set.

    Returns:
        Configured logger instance.
    """
    if level is None:
        level = os.getenv("PIPELINE_LOG_LEVEL", "INFO")
    if log_file is None:
        log_file = os.getenv("PIPELINE_LOG_FILE", "")

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    logger.addHandler(console)

    # File handler (optional)
    if log_file:
        fh = logging.FileHandler(log_file, mode="a")
        fh.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
        logger.addHandler(fh)

    return logger


logger = setup_logging("collectai.pipeline")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


def _headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",  # upsert
    }


# ---------------------------------------------------------------------------
# Shared Rarity / Condition Score Maps (#8)
# ---------------------------------------------------------------------------

RARITY_SCORE_MAP: dict[str, float] = {
    # TCG universal tiers
    "Common": 0.1,
    "Uncommon": 0.3,
    "Rare": 0.5,
    "Rare Holo": 0.65,
    "Rare Holo EX": 0.7,
    "Rare Ultra": 0.8,
    "Rare Secret": 0.9,
    "Rare Holo V": 0.7,
    "Rare Holo VMAX": 0.75,
    "Rare Holo VSTAR": 0.75,
    "Amazing Rare": 0.8,
    "Illustration Rare": 0.85,
    "Special Art Rare": 0.9,
    "Hyper Rare": 0.95,
    "Rare Shiny": 0.8,
    "LEGEND": 0.85,
    "Promo": 0.4,
    # MTG
    "Mythic Rare": 0.9,
    "Mythic": 0.9,
    # Yu-Gi-Oh
    "Super Rare": 0.6,
    "Ultra Rare": 0.8,
    "Secret Rare": 0.9,
    "Ghost Rare": 0.95,
    "Starlight Rare": 0.98,
    "Quarter Century Secret Rare": 0.99,
    "Collector's Rare": 0.85,
    "Prismatic Secret Rare": 0.92,
    # Funko / General collectibles
    "Vaulted": 0.8,
    "Chase": 0.85,
    "Grail": 0.95,
    "Exclusive": 0.7,
    "Limited Edition": 0.75,
    "Standard": 0.3,
    # Warhammer / Model kits
    "Centerpiece": 0.8,
    "Character": 0.5,
    "Troops": 0.3,
    "Vehicle": 0.6,
    "Forge World": 0.85,
    # General
    "N/A": 0.3,
    "": 0.3,
}

CONDITION_SCORE_MAP: dict[str, float] = {
    "Mint": 1.0,
    "Near Mint": 0.9,
    "NM": 0.9,
    "Excellent": 0.8,
    "EX": 0.8,
    "Light Play": 0.7,
    "Lightly Played": 0.7,
    "LP": 0.7,
    "Good": 0.6,
    "GD": 0.6,
    "Moderate Play": 0.5,
    "Moderately Played": 0.5,
    "MP": 0.5,
    "Heavy Play": 0.3,
    "Heavily Played": 0.3,
    "HP": 0.3,
    "Damaged": 0.1,
    "DMG": 0.1,
    "Poor": 0.1,
    # PSA grades
    "PSA 10": 1.0,
    "PSA 9": 0.9,
    "PSA 8": 0.8,
    "PSA 7": 0.7,
    "PSA 6": 0.6,
    "PSA 5": 0.5,
    "PSA 4": 0.4,
    "PSA 3": 0.3,
    "PSA 2": 0.2,
    "PSA 1": 0.1,
    # Sealed
    "Sealed": 1.0,
    "New": 1.0,
}


def rarity_score(rarity: str) -> float:
    """Map a rarity string to a 0-1 score using the shared map."""
    return RARITY_SCORE_MAP.get(rarity, 0.3)


def condition_score(condition: str) -> float:
    """Map a condition string to a 0-1 score using the shared map."""
    return CONDITION_SCORE_MAP.get(condition, 0.5)


# ---------------------------------------------------------------------------
# Pydantic-style Validation Helpers (#23)
# ---------------------------------------------------------------------------

MAX_ITEM_KEY_LEN = 255
MAX_TITLE_LEN = 500
MIN_PRICE_EUR = 0.0
# Upper bound for a single collectible price (EUR).
# Raised from €1M to €20M in Round 50f to accommodate grail-tier collectibles:
# - Paul Newman Rolex Daytona sold for ~$17.8M
# - Action Comics #1 CGC 8.0 sold for ~$5.3M
# - Jaeger-LeCoultre Reverso Hybris Mechanica Quadriptyque retail ~€1.5M
# Anything above €20M is almost certainly a data entry error.
MAX_PRICE_EUR = 20_000_000.0


class ValidationError(Exception):
    """Raised when a data model fails validation."""
    pass


def _validate_item_key(key: str) -> str:
    if not key or not key.strip():
        raise ValidationError("item_key cannot be empty")
    if len(key) > MAX_ITEM_KEY_LEN:
        raise ValidationError(f"item_key too long ({len(key)} > {MAX_ITEM_KEY_LEN})")
    return key.strip()


def _validate_price(price: float, label: str = "price") -> float:
    if price < MIN_PRICE_EUR:
        raise ValidationError(f"{label} must be >= 0, got {price}")
    if price > MAX_PRICE_EUR:
        raise ValidationError(f"{label} exceeds max ({price} > {MAX_PRICE_EUR})")
    return price


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CatalogItem:
    """One row in the category_items table."""
    category: str
    item_key: str          # unique within category (e.g. "base-set-charizard-holo")
    title: str
    set_code: str = ""
    brand: str = ""
    rarity: str = ""
    notes: str = ""
    image_url: str = ""
    barcode: str = ""
    attributes_json: dict = field(default_factory=dict)

    def __post_init__(self):
        self.item_key = _validate_item_key(self.item_key)
        if not self.category:
            raise ValidationError("category cannot be empty")
        if not self.title:
            raise ValidationError("title cannot be empty")
        if len(self.title) > MAX_TITLE_LEN:
            self.title = self.title[:MAX_TITLE_LEN]

    def to_row(self) -> dict:
        # Auto-parse notes into attributes_json (idempotent — won't overwrite
        # explicit attributes_json keys set by the pipeline)
        self._parse_notes_into_attributes()

        row = {
            "category": self.category,
            "item_key": self.item_key,
            "title": self.title,
            "set_code": self.set_code,
            "brand": self.brand,
            "rarity": self.rarity,
            "notes": self.notes,
        }
        if self.image_url:
            row["image_url"] = self.image_url
        if self.barcode:
            row["barcode"] = self.barcode
        if self.attributes_json:
            # Pass the dict, NOT json.dumps(dict). PostgREST already serialises
            # the row as JSON, so dumping here produces a JSON *string* in a
            # jsonb column — `"{\"set\": \"base\"}"` instead of `{"set": ...}`.
            # `category_items` has CHECK (jsonb_typeof(attributes_json) =
            # 'object'), so Postgres rejects every attribute-bearing row while
            # the pipeline reports success: it logs rows ATTEMPTED, not rows
            # accepted.
            #
            # Fixed on the working branch 2026-07-25 and never reached this one.
            # This branch is the repo DEFAULT branch, and GitHub runs
            # `schedule:` workflows from the default branch — so nightly-ingest
            # has run this line every night since. Still 680 rejected writes/day
            # on 2026-08-12. See docs/DEPLOYMENT.md "Three places run code".
            row["attributes_json"] = self.attributes_json
        return row

    def _parse_notes_into_attributes(self) -> None:
        """Parse `notes` free-text into structured attributes_json keys.

        Existing keys are preserved (notes-derived values only fill gaps).
        Safe to call multiple times.
        """
        if not self.notes or not self.notes.strip():
            return
        try:
            from pipelines.notes_parser import parse_notes
            parsed = parse_notes(self.category, self.notes, self.brand)
        except Exception:
            return
        if not parsed:
            return
        if self.attributes_json is None:
            self.attributes_json = {}
        for k, v in parsed.items():
            if k not in self.attributes_json:
                self.attributes_json[k] = v


@dataclass
class PriceObservation:
    """One training sample: features + price."""
    features: dict
    price: float  # EUR

    def __post_init__(self):
        self.price = _validate_price(self.price)
        for key in ("condition_score", "rarity_score", "edition_score"):
            if key in self.features:
                val = self.features[key]
                if not isinstance(val, (int, float)):
                    raise ValidationError(f"Feature {key} must be numeric, got {type(val)}")

    def to_jsonl(self) -> str:
        return json.dumps({"features": self.features, "price": self.price})


@dataclass
class MarketHit:
    """One row in the market_hits table."""
    provider: str          # e.g. "ebay", "tcgplayer", "scryfall"
    listing_id: str
    title: str
    price: float
    currency: str = "EUR"
    condition: str = ""
    normalized_key: str = ""
    category: str = ""
    sold_at: str = ""
    url: str = ""
    image_url: str = ""


# ---------------------------------------------------------------------------
# Error Aggregation (#4)
# ---------------------------------------------------------------------------

class IngestStats:
    """Tracks error counts and warnings across a pipeline run."""

    def __init__(self):
        self.catalog_upserted: int = 0
        self.catalog_errors: int = 0
        self.market_hits_upserted: int = 0
        self.market_hits_errors: int = 0
        self.transform_errors: int = 0
        self.warnings: list[str] = []

    @property
    def total_errors(self) -> int:
        return self.catalog_errors + self.market_hits_errors + self.transform_errors

    @property
    def has_errors(self) -> bool:
        return self.total_errors > 0

    def record_warning(self, msg: str) -> None:
        self.warnings.append(msg)
        logger.warning(msg)

    def summary(self) -> str:
        lines = [
            f"  Catalog upserted:     {self.catalog_upserted}",
            f"  Catalog errors:       {self.catalog_errors}",
            f"  Market hits upserted: {self.market_hits_upserted}",
            f"  Market hits errors:   {self.market_hits_errors}",
            f"  Transform errors:     {self.transform_errors}",
        ]
        if self.warnings:
            lines.append(f"  Warnings:             {len(self.warnings)}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Shared HTTP Session (#16)
# ---------------------------------------------------------------------------

_shared_http_client: httpx.Client | None = None


def get_http_client() -> httpx.Client:
    """Return a shared httpx.Client for connection reuse across the pipeline."""
    global _shared_http_client
    if _shared_http_client is None or _shared_http_client.is_closed:
        _shared_http_client = httpx.Client(timeout=30.0)
    return _shared_http_client


def close_http_client() -> None:
    """Close the shared HTTP client (call at pipeline shutdown)."""
    global _shared_http_client
    if _shared_http_client is not None and not _shared_http_client.is_closed:
        _shared_http_client.close()
        _shared_http_client = None


# ---------------------------------------------------------------------------
# Supabase Ingest Client
# ---------------------------------------------------------------------------

class SupabaseIngest:
    """Batch upsert helper for Supabase PostgREST API."""

    def __init__(self, batch_size: int = 200, stats: IngestStats | None = None):
        self.batch_size = batch_size
        self.client = get_http_client()
        self.stats = stats or IngestStats()
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            logger.warning("SUPABASE_URL / SUPABASE_SERVICE_KEY not set. "
                           "Data will only be written to local JSONL files.")
            self.enabled = False
        else:
            self.enabled = True

    def upsert_catalog(self, items: list[CatalogItem]) -> int:
        """Upsert catalog items into category_items table. Returns count inserted."""
        if not self.enabled:
            return 0
        rows = [item.to_row() for item in items]
        total = 0
        # PostgREST requires ?on_conflict=<columns> AND Prefer: resolution=merge-duplicates
        # for UPSERT behavior. Without this, unique constraint violations return 409.
        url = f"{SUPABASE_URL}/rest/v1/category_items?on_conflict=category,item_key"
        for i in range(0, len(rows), self.batch_size):
            batch = rows[i:i + self.batch_size]
            try:
                resp = self.client.post(url, headers=_headers(), json=batch)
                if resp.status_code in (200, 201):
                    total += len(batch)
                else:
                    self.stats.catalog_errors += 1
                    logger.error(f"Upsert catalog batch {i}: {resp.status_code} "
                                 f"{resp.text[:200]}")
            except Exception as e:
                self.stats.catalog_errors += 1
                logger.error(f"Upsert catalog batch {i} failed: {e}")
        self.stats.catalog_upserted += total
        return total

    def upsert_market_hits(self, hits: list[MarketHit]) -> int:
        """Upsert market hits. Returns count inserted.

        Writer contract (see learnings.md §22, §64, §65 and the root-cause
        essay's post-write-assertion rule):
          - item_ref is `{category}:{normalized_key}` — downstream readers
            (valuation, calibration, price_predictions join) require this
            exact format. Was silently dropped from this writer until
            2026-04-21, leaving 133k rows with NULL item_ref invisible to
            valuation. Bulk-backfilled via UPDATE WHERE item_ref IS NULL.
          - price_eur mirrors `price` because all callers in the pipeline
            pre-convert to EUR via to_eur() / Frankfurter FX; the schema
            drift check (scripts/schema_drift_check.py) declares price_eur
            as an expected column.
        """
        if not self.enabled:
            return 0
        rows = []
        dropped_bad_item_ref = 0
        for h in hits:
            item_ref = f"{h.category}:{h.normalized_key}" if (h.category and h.normalized_key) else None
            # Post-write assertion per learnings.md root-cause essay:
            # item_ref must either be NULL or contain a ':' separator.
            if item_ref is not None and ":" not in item_ref:
                dropped_bad_item_ref += 1
                continue
            rows.append({
                "provider": h.provider,
                "listing_id": h.listing_id,
                "title": h.title,
                "price": h.price,
                "price_eur": h.price,
                "currency": h.currency,
                "condition": h.condition,
                "normalized_key": h.normalized_key,
                "category": h.category,
                "item_ref": item_ref,
            })
        if dropped_bad_item_ref:
            self.stats.market_hits_errors += dropped_bad_item_ref
            logger.error(
                "upsert_market_hits dropped %d rows with malformed item_ref",
                dropped_bad_item_ref,
            )
        total = 0
        for i in range(0, len(rows), self.batch_size):
            batch = rows[i:i + self.batch_size]
            try:
                resp = self.client.post(
                    f"{SUPABASE_URL}/rest/v1/market_hits",
                    headers=_headers(),
                    json=batch,
                )
                if resp.status_code in (200, 201):
                    total += len(batch)
                else:
                    self.stats.market_hits_errors += 1
                    logger.error(f"Upsert market_hits batch {i}: {resp.status_code} "
                                 f"{resp.text[:200]}")
            except Exception as e:
                self.stats.market_hits_errors += 1
                logger.error(f"Upsert market_hits batch {i} failed: {e}")
        self.stats.market_hits_upserted += total
        return total

    def close(self):
        # Don't close shared client here; let close_http_client() handle it
        pass


# ---------------------------------------------------------------------------
# Local file writers
# ---------------------------------------------------------------------------

def write_training_jsonl(category: str, observations: list[PriceObservation]) -> Path:
    """Write price observations to data/{category}/train.jsonl (append mode)."""
    out_dir = DATA_DIR / category
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "train.jsonl"
    with open(out_path, "a") as f:
        for obs in observations:
            f.write(obs.to_jsonl() + "\n")
    return out_path


def write_catalog_sql(category: str, items: list[CatalogItem]) -> Path:
    """Write catalog items as SQL INSERT statements (backup/review)."""
    out_dir = DATA_DIR / category
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "catalog_seed.sql"
    with open(out_path, "w") as f:
        f.write(f"-- Auto-generated catalog seed for {category}\n")
        f.write(f"-- Generated: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"-- Items: {len(items)}\n\n")
        for batch_start in range(0, len(items), 50):
            batch = items[batch_start:batch_start + 50]
            f.write("INSERT INTO public.category_items (category, set_code, item_key, title, brand, rarity, notes) VALUES\n")
            values = []
            for item in batch:
                vals = (
                    f"  ('{_esc(item.category)}', '{_esc(item.set_code)}', "
                    f"'{_esc(item.item_key)}', '{_esc(item.title)}', "
                    f"'{_esc(item.brand)}', '{_esc(item.rarity)}', '{_esc(item.notes)}')"
                )
                values.append(vals)
            f.write(",\n".join(values))
            f.write("\nON CONFLICT (category, item_key) DO NOTHING;\n\n")
    return out_path


def _esc(s: str) -> str:
    """Escape single quotes for SQL."""
    return s.replace("'", "''")


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def fetch_json(url: str, params: dict | None = None, headers: dict | None = None,
               retries: int = 3, delay: float = 1.0) -> Any:
    """GET JSON with retries, rate-limit backoff, and Retry-After support."""
    client = get_http_client()
    for attempt in range(retries):
        try:
            resp = client.get(url, params=params, headers=headers)
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait = int(retry_after)
                else:
                    wait = delay * (2 ** attempt)
                logger.warning(f"Rate limited, waiting {wait:.1f}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP {e.response.status_code} on attempt {attempt+1}/{retries}: {url}")
            if attempt == retries - 1:
                raise
            time.sleep(delay)
        except httpx.ConnectError:
            logger.warning(f"Connection error on attempt {attempt+1}/{retries}: {url}")
            if attempt == retries - 1:
                raise
            time.sleep(delay)


# ---------------------------------------------------------------------------
# Progress logging
# ---------------------------------------------------------------------------

def log_progress(category: str, phase: str, count: int, total: int = 0):
    pct = f" ({count}/{total} = {100*count/total:.0f}%)" if total else f" ({count})"
    logger.info(f"{category:20s} | {phase:20s} |{pct}")


# ---------------------------------------------------------------------------
# Slug normalization
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert text to URL-safe slug for item_key."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


# ---------------------------------------------------------------------------
# EUR conversion with live FX rates (#5)
# ---------------------------------------------------------------------------

# Fallback rates (updated 2026-02)
_FALLBACK_FX: dict[str, float] = {
    "USD": 0.92,
    "GBP": 1.17,
    "JPY": 0.0061,
    "CAD": 0.68,
    "AUD": 0.60,
    "CHF": 1.05,
}

_live_fx_rates: dict[str, float] | None = None


def fetch_fx_rates() -> dict[str, float]:
    """Fetch live EUR exchange rates from a free API.

    Returns a dict mapping currency codes to EUR multipliers.
    Falls back to hardcoded rates on any error.
    """
    global _live_fx_rates
    if _live_fx_rates is not None:
        return _live_fx_rates

    try:
        client = get_http_client()
        resp = client.get(
            "https://api.exchangerate.host/latest",
            params={"base": "EUR", "symbols": "USD,GBP,JPY,CAD,AUD,CHF"},
            timeout=5.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            rates = data.get("rates", {})
            if rates:
                # API returns EUR->X, we need X->EUR (inverse)
                _live_fx_rates = {
                    code: round(1.0 / rate, 6) if rate else _FALLBACK_FX.get(code, 1.0)
                    for code, rate in rates.items()
                }
                logger.info(f"Loaded live FX rates: {_live_fx_rates}")
                return _live_fx_rates
    except Exception as e:
        logger.warning(f"Failed to fetch live FX rates, using fallback: {e}")

    _live_fx_rates = _FALLBACK_FX.copy()
    return _live_fx_rates


def to_eur(price: float, currency: str) -> float:
    """Convert a price to EUR using live rates (with fallback)."""
    currency = currency.upper()
    if currency == "EUR":
        return price
    rates = fetch_fx_rates()
    rate = rates.get(currency, _FALLBACK_FX.get(currency))
    if rate:
        return round(price * rate, 2)
    logger.warning(f"Unknown currency '{currency}', returning price as-is")
    return price


# Legacy aliases for backward compat
USD_TO_EUR = _FALLBACK_FX["USD"]
JPY_TO_EUR = _FALLBACK_FX["JPY"]


# ---------------------------------------------------------------------------
# Image caching
# ---------------------------------------------------------------------------

def cache_catalog_images(
    items: list[CatalogItem],
    dry_run: bool = False,
    rate_limit: float = 0.1,
) -> list[CatalogItem]:
    """
    Cache external image URLs to S3 for all catalog items.

    Replaces image_url with CDN/S3 URL when successful.
    Skips items without image_url. Falls back gracefully.

    Args:
        items: List of CatalogItem with external image_url values
        dry_run: If True, don't actually upload
        rate_limit: Seconds between downloads

    Returns:
        Same list with image_url fields updated to S3/CDN URLs
    """
    from pipelines.s3_image_cache import S3ImageCache

    cache = S3ImageCache(dry_run=dry_run)
    if not cache.enabled and not dry_run:
        return items

    batch = [
        (item.image_url, item.category, item.item_key)
        for item in items
        if item.image_url
    ]

    if not batch:
        cache.close()
        return items

    logger.info(f"Caching {len(batch)} images to S3...")
    url_map = cache.cache_batch(batch, rate_limit=rate_limit)

    # Update items with cached URLs
    for item in items:
        if item.image_url and item.image_url in url_map:
            item.image_url = url_map[item.image_url]

    cache.print_stats()
    cache.close()
    return items
