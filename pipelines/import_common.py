"""
Shared utilities for catalog + price data import pipelines.

Usage:
    from import_common import SupabaseIngest, write_training_jsonl, log_progress

All import scripts follow this pattern:
    1. Fetch from external API → normalize to category_items rows
    2. Upsert into Supabase category_items table
    3. Fetch price data → write to data/{category}/train.jsonl
    4. Optionally populate market_hits table
    5. Optionally cache images to S3 (--cache-images flag)
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

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

    def to_row(self) -> dict:
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
            row["attributes_json"] = json.dumps(self.attributes_json)
        return row


@dataclass
class PriceObservation:
    """One training sample: features + price."""
    features: dict
    price: float  # EUR

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
# Supabase Ingest Client
# ---------------------------------------------------------------------------

class SupabaseIngest:
    """Batch upsert helper for Supabase PostgREST API."""

    def __init__(self, batch_size: int = 200):
        self.batch_size = batch_size
        self.client = httpx.Client(timeout=30.0)
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            print("WARNING: SUPABASE_URL / SUPABASE_SERVICE_KEY not set.")
            print("         Data will only be written to local JSONL files.")
            self.enabled = False
        else:
            self.enabled = True

    def upsert_catalog(self, items: list[CatalogItem]) -> int:
        """Upsert catalog items into category_items table. Returns count inserted."""
        if not self.enabled:
            return 0
        rows = [item.to_row() for item in items]
        total = 0
        for i in range(0, len(rows), self.batch_size):
            batch = rows[i:i + self.batch_size]
            resp = self.client.post(
                f"{SUPABASE_URL}/rest/v1/category_items",
                headers=_headers(),
                json=batch,
            )
            if resp.status_code in (200, 201):
                total += len(batch)
            else:
                print(f"  ERROR upserting batch {i}: {resp.status_code} {resp.text[:200]}")
        return total

    def upsert_market_hits(self, hits: list[MarketHit]) -> int:
        """Upsert market hits. Returns count inserted."""
        if not self.enabled:
            return 0
        rows = [
            {
                "provider": h.provider,
                "listing_id": h.listing_id,
                "title": h.title,
                "price": h.price,
                "currency": h.currency,
                "condition": h.condition,
                "normalized_key": h.normalized_key,
                "category": h.category,
            }
            for h in hits
        ]
        total = 0
        for i in range(0, len(rows), self.batch_size):
            batch = rows[i:i + self.batch_size]
            resp = self.client.post(
                f"{SUPABASE_URL}/rest/v1/market_hits",
                headers=_headers(),
                json=batch,
            )
            if resp.status_code in (200, 201):
                total += len(batch)
            else:
                print(f"  ERROR upserting market_hits batch: {resp.status_code} {resp.text[:200]}")
        return total

    def close(self):
        self.client.close()


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
    """GET JSON with retries and rate-limit backoff."""
    client = httpx.Client(timeout=30.0)
    for attempt in range(retries):
        try:
            resp = client.get(url, params=params, headers=headers)
            if resp.status_code == 429:
                wait = delay * (2 ** attempt)
                print(f"  Rate limited, waiting {wait:.1f}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
        except httpx.ConnectError:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
    client.close()


# ---------------------------------------------------------------------------
# Progress logging
# ---------------------------------------------------------------------------

def log_progress(category: str, phase: str, count: int, total: int = 0):
    ts = datetime.now().strftime("%H:%M:%S")
    pct = f" ({count}/{total} = {100*count/total:.0f}%)" if total else f" ({count})"
    print(f"[{ts}] {category:20s} | {phase:20s} |{pct}")


# ---------------------------------------------------------------------------
# Slug normalization
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert text to URL-safe slug for item_key."""
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


# ---------------------------------------------------------------------------
# EUR conversion (approximate, for seeding only)
# ---------------------------------------------------------------------------

USD_TO_EUR = 0.92
JPY_TO_EUR = 0.0061


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

    print(f"  Caching {len(batch)} images to S3...")
    url_map = cache.cache_batch(batch, rate_limit=rate_limit)

    # Update items with cached URLs
    for item in items:
        if item.image_url and item.image_url in url_map:
            item.image_url = url_map[item.image_url]

    cache.print_stats()
    cache.close()
    return items


# ---------------------------------------------------------------------------
# EUR conversion (approximate, for seeding only)
# ---------------------------------------------------------------------------

def to_eur(price: float, currency: str) -> float:
    currency = currency.upper()
    if currency == "EUR":
        return price
    if currency == "USD":
        return round(price * USD_TO_EUR, 2)
    if currency == "JPY":
        return round(price * JPY_TO_EUR, 2)
    if currency == "GBP":
        return round(price * 1.17, 2)
    return price  # fallback: assume EUR
