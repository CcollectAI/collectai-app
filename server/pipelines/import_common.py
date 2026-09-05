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
import random
import threading
from urllib.parse import urlparse
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
            # Send the dict, NOT json.dumps(dict).
            #
            # The batch is posted with httpx `json=batch` (see upsert_catalog),
            # so httpx serialises the whole payload itself. Pre-encoding this
            # value made PostgREST receive a JSON *string* and store a JSONB
            # string rather than a JSONB object — the "double-stringified"
            # corruption scripts/repair_attributes_json_types.py was written to
            # clean up (136K string rows + 4K array rows, 0 objects).
            #
            # Once category_items_attrs_is_object was added
            # (CHECK jsonb_typeof(attributes_json) = 'object') the repair held,
            # but this writer was never fixed, so every catalog upsert carrying
            # attributes was rejected 23514 — 597 per day, invisible because the
            # pipeline logs the count it *attempted*, not the count Postgres
            # accepted. Verified against the live REST endpoint 2026-07-25:
            # json.dumps(...) -> HTTP 400 23514, plain dict -> HTTP 201.
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


def parse_observed_at(raw: str | None) -> str | None:
    """Normalise an importer's `sold_at` into an ISO timestamp, or None.

    WHY (2026-08-30): `MarketHit` has carried a `sold_at` field since it was
    written, and `upsert_market_hits` never put it in the row dict -- captured
    and dropped. Three importers populate it with the SOURCE'S OWN price date:
    import_pokemon (TCGplayer `updatedAt` and Cardmarket `updatedAt`) and
    import_lorcana. All of it was discarded, so every row fell back to
    `seen_at` -- when WE happened to fetch, not when the price was computed.

    Returning None on anything unparseable is deliberate and load-bearing:
    valuation_worker selects `COALESCE(observed_at, seen_at)`, so a NULL keeps
    exactly today's behaviour. This can only make the timestamp more accurate,
    never less -- there is no input for which it degrades the current state.

    A bare date is widened to midnight UTC rather than bound as-is: the column
    is timestamptz and binding a bare `date` is the trap recorded in
    learning_items_paired_columns_trigger.
    """
    if not raw or not isinstance(raw, str):
        return None
    txt = raw.strip()
    if not txt:
        return None
    # pokemontcg.io uses "2026/08/29"; Cardmarket and Lorcast use ISO.
    txt = txt.replace("/", "-")
    if txt.endswith("Z"):
        txt = txt[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        try:
            dt = datetime.strptime(txt[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


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
_http_client_lock = threading.Lock()

# Set while an orchestrator (import_all) is running pipelines concurrently.
# See hold_http_client() below.
_http_client_held = False


def get_http_client() -> httpx.Client:
    """Return a shared httpx.Client for connection reuse across the pipeline."""
    global _shared_http_client
    # Locked: import_all runs pipelines in a ThreadPoolExecutor, so two threads
    # could both observe a closed/None client and each build one. The loser's
    # client is then never closed.
    with _http_client_lock:
        if _shared_http_client is None or _shared_http_client.is_closed:
            _shared_http_client = httpx.Client(timeout=30.0)
        return _shared_http_client


def hold_http_client() -> None:
    """Refuse sibling `close_http_client()` calls until release_http_client().

    THE BUG THIS FIXES (2026-09-05, and it is a REGRESSION of the 08-29 fix).

    At least six single-category pipelines call the MODULE-GLOBAL
    `close_http_client()` when they individually finish. `import_all` runs them
    concurrently, so a pipeline that finishes early closes the client every
    other thread is still writing through.

    2026-08-29 made `SupabaseIngest.client` a property that re-resolves per
    call, and the 08-30 run duly showed `client has been closed: 0`. But a
    property only narrows the window; it does not close it. The sequence

        thread A: self.client            -> returns a LIVE client
        thread B: close_http_client()    -> closes that very object
        thread A: client.post(...)       -> RuntimeError, 200 rows lost

    is still available, and it is what the 09-03/04/05 nightlies hit: 13
    failed batches, **2,254 rows lost**, exit 1, three nights running.

    A property cannot fix a time-of-check/time-of-use race. Ownership can:
    while the orchestrator holds the client, a sibling's close is a no-op, and
    only the holder's release actually closes it. One chokepoint instead of
    six call sites — none of those pipelines is wrong to want to tidy up, they
    are just not the owner.
    """
    global _http_client_held
    with _http_client_lock:
        _http_client_held = True


def release_http_client() -> None:
    """Release the hold taken by hold_http_client() and close for real."""
    global _http_client_held
    with _http_client_lock:
        _http_client_held = False
    close_http_client()


def close_http_client() -> None:
    """Close the shared HTTP client (call at pipeline shutdown).

    A no-op while an orchestrator holds it — see hold_http_client().
    """
    global _shared_http_client
    with _http_client_lock:
        if _http_client_held:
            logger.debug("[ingest] close_http_client() ignored — client is held "
                         "by the orchestrator while sibling pipelines still write")
            return
        if _shared_http_client is not None and not _shared_http_client.is_closed:
            _shared_http_client.close()
            _shared_http_client = None


# ---------------------------------------------------------------------------
# Write-loss accounting (the run must fail when it drops rows)
# ---------------------------------------------------------------------------
#
# `import_all` runs each pipeline in-process via importlib, and every pipeline
# builds its OWN IngestStats -- so nothing upstream could ever see a write
# failure. On 2026-08-28 the nightly dropped 107 catalog batches and exited 0.
# Three separate bugs hid behind that single green checkmark for weeks; the
# silence, not the bugs, is what made them expensive.
#
# This is a PROCESS-level tally rather than a parameter threaded through every
# pipeline, for the same reason `client` became a property: there are ~50
# pipelines and the next new one would have been the one that forgot. Every
# catalog and market-hit write already funnels through SupabaseIngest, so
# recording here cannot be bypassed by a caller.
#
# It counts ONLY rows we held and then failed to write. An upstream fetch
# failure (api.pokemontcg.io returned 500 twenty times in that same run) is not
# recorded and must not fail the nightly -- otherwise the signal drowns in
# third-party weather and gets ignored, which is the state we just left.
_write_losses: dict[str, int] = {"rows_lost": 0, "failed_batches": 0}
_write_loss_lock = threading.Lock()


def record_write_loss(rows_lost: int, failed_batches: int) -> None:
    """Record rows that were fetched, held, and then not written."""
    if rows_lost <= 0 and failed_batches <= 0:
        return
    with _write_loss_lock:
        _write_losses["rows_lost"] += max(0, rows_lost)
        _write_losses["failed_batches"] += max(0, failed_batches)


def write_loss_summary() -> dict[str, int]:
    with _write_loss_lock:
        return dict(_write_losses)


def reset_write_losses() -> None:
    """Clear the tally. Call at the START of a run, never at the end --
    `import_all --resume` starts a fresh process, and a tally that cleared
    itself on read would let the second reader see a clean run."""
    with _write_loss_lock:
        _write_losses["rows_lost"] = 0
        _write_losses["failed_batches"] = 0


def write_loss_exit_code() -> int:
    """0 if every row we fetched was written, 1 otherwise."""
    return 1 if write_loss_summary()["rows_lost"] > 0 else 0


# ---------------------------------------------------------------------------
# Supabase Ingest Client
# ---------------------------------------------------------------------------

# Transport-level failures worth retrying. httpx.TransportError is the base for
# ConnectError, ReadTimeout, RemoteProtocolError, PoolTimeout, ConnectTimeout
# and the SSL wrappers — i.e. every way the connection can fail WITHOUT the
# server having judged the request.
# Consecutive-5xx circuit breaker per upstream host — see fetch_json().
_host_failures: dict[str, int] = {}
_host_fail_lock = threading.Lock()
_HOST_FAIL_LIMIT = int(os.getenv("INGEST_HOST_FAIL_LIMIT", "8"))


def reset_host_circuit(host: str | None = None) -> None:
    """Clear the 5xx circuit for one host, or all of them."""
    with _host_fail_lock:
        if host is None:
            _host_failures.clear()
        else:
            _host_failures.pop(host, None)


_RETRYABLE_POST = (httpx.TransportError,)
# httpx's wording for a closed client; matched on the message because it
# raises a bare RuntimeError with no dedicated type.
_CLOSED_CLIENT_MSG = "client has been closed"
_POST_ATTEMPTS = int(os.getenv("INGEST_POST_ATTEMPTS", "3"))
_POST_BASE_DELAY_S = float(os.getenv("INGEST_POST_BASE_DELAY_S", "0.5"))


def _post_with_retry(client, url, *, headers, json, timeout=None):
    """POST a batch, retrying only TRANSPORT failures.

    The 2026-08-30 nightly — the first on the corrected default branch — lost
    2,412 rows across 14 batches. The three bugs fixed the day before were at
    zero (PGRST102: 0, "client has been closed": 0); every remaining failure
    was transport-level:

        12x  Server disconnected without sending a response
         1x  The read operation timed out
         1x  [SSL: WRONG_VERSION_NUMBER] wrong version number

    That is the classic stale keep-alive — Supabase closes an idle pooled
    connection, httpx reuses it, the write dies — and the writer had no retry,
    so one blip cost 200 rows permanently.

    ⚠️ Retrying is safe HERE and not in general. These upserts are
    `ON CONFLICT ... DO UPDATE`, so a replay is a no-op. `DATA_SCALING_PLAN.md`
    §10 records the opposite case: retrying a market_hits load duplicated 3,000
    rows because the conflict clause could not fire against a generated PK.
    Do not copy this into a writer whose replay is not idempotent.

    An HTTP RESPONSE is never retried, however bad. PGRST102 and 21000 are the
    server's judgement of this exact payload — they fail identically on replay,
    three times as slowly, and hide nothing. Only the absence of a response is
    retried.
    """
    last: Exception | None = None
    for attempt in range(_POST_ATTEMPTS):
        # Re-resolve a client that was closed under us. `hold_http_client()`
        # now prevents the usual cause, but this costs nothing and closes the
        # residual window for any caller that is not under the orchestrator.
        if getattr(client, "is_closed", False):
            client = get_http_client()
        try:
            return client.post(url, headers=headers, json=json, timeout=timeout) \
                if timeout is not None else client.post(url, headers=headers, json=json)
        except _RETRYABLE_POST as e:
            last = e
        except RuntimeError as e:
            # httpx raises a bare RuntimeError for a closed client. It is
            # retryable — and ONLY this one is: get_http_client() rebuilds, so
            # the next attempt has a live client. Any other RuntimeError is a
            # real bug and must not be swallowed into a retry loop.
            if _CLOSED_CLIENT_MSG not in str(e):
                raise
            last = e
            client = get_http_client()
        else:  # pragma: no cover - unreachable, the try returns
            pass

        if attempt == _POST_ATTEMPTS - 1:
            break
        delay = _POST_BASE_DELAY_S * (2 ** attempt)
        logger.warning(
            "[ingest] transport failure on attempt %d/%d (%s) — retrying in %.1fs",
            attempt + 1, _POST_ATTEMPTS, last, delay,
        )
        time.sleep(delay)
    raise last  # type: ignore[misc]


class SupabaseIngest:
    """Batch upsert helper for Supabase PostgREST API."""

    def __init__(self, batch_size: int = 200, stats: IngestStats | None = None):
        self.batch_size = batch_size
        self.stats = stats or IngestStats()
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            logger.warning("SUPABASE_URL / SUPABASE_SERVICE_KEY not set. "
                           "Data will only be written to local JSONL files.")
            self.enabled = False
        else:
            self.enabled = True

    @property
    def client(self) -> httpx.Client:
        """Resolve the shared client per call, never cache it on the instance.

        `import_all.py:288` runs pipelines in a ThreadPoolExecutor, and several
        of them call the MODULE-GLOBAL `close_http_client()` when they
        individually finish (`import_sneakers.py:3380` and :3402, and the same
        import in import_funko / import_mtg / import_retro_handhelds /
        import_jp_magazine). That closes the client every *other* thread is
        still writing through.

        Measured on the 2026-08-28 nightly run: the pipelines that finished
        last — Comic Books, Plush, Vintage Toys — lost roughly 50 batches to
        `Cannot send a request, as the client has been closed.`, and the job
        still reported success. Caching the client in __init__ is what made a
        sibling's shutdown fatal; `get_http_client()` already rebuilds a closed
        client, so asking it each time makes the close harmless.
        """
        return get_http_client()

    def upsert_catalog(self, items: list[CatalogItem]) -> int:
        """Upsert catalog items into category_items table. Returns count inserted."""
        if not self.enabled:
            return 0
        # Deduplicate by the conflict key BEFORE batching.
        #
        # The URL below sets on_conflict=category,item_key and the request
        # carries Prefer: resolution=merge-duplicates, so PostgREST compiles
        # each batch into a single INSERT ... ON CONFLICT (category, item_key)
        # DO UPDATE. If one batch contains the same (category, item_key) twice,
        # Postgres aborts the WHOLE statement with
        #   ON CONFLICT DO UPDATE command cannot affect row a second time
        # and all 200 rows in that batch are lost, not just the duplicate.
        # Pipelines legitimately emit repeats (pagination overlap, retries, the
        # same card in two sets), so dedupe here rather than trusting callers —
        # the same defence upsert_market_hits_batch needed after the 2026-05-02
        # incident. Last occurrence wins, so later/fresher data overwrites.
        deduped: dict[tuple, dict] = {}
        for item in items:
            row = item.to_row()
            deduped[(row.get("category"), row.get("item_key"))] = row
        dropped = len(items) - len(deduped)
        if dropped:
            logger.info(
                "[catalog] dropped %d within-batch duplicate row(s) before upsert "
                "(same category+item_key)", dropped,
            )
        rows = list(deduped.values())
        total = 0
        # PostgREST requires ?on_conflict=<columns> AND Prefer: resolution=merge-duplicates
        # for UPSERT behavior. Without this, unique constraint violations return 409.
        url = f"{SUPABASE_URL}/rest/v1/category_items?on_conflict=category,item_key"

        # Group by KEY SET before batching.
        #
        # PostgREST compiles a bulk insert into ONE statement with ONE column
        # list, so it rejects the whole array with
        #   400 {"code":"PGRST102","message":"All object keys must match"}
        # if the objects do not agree on their keys. `to_row()` adds image_url,
        # barcode and attributes_json CONDITIONALLY, and a real catalogue page
        # mixes rows that have an image with rows that do not — so a single
        # batch routinely carried two key sets. That cost 42 of the 107 failed
        # batches on the 2026-08-28 nightly run, silently: the loop below logs
        # the error and continues, so the job still reported success.
        #
        # Grouping rather than PADDING the rows to a common key set is
        # deliberate. The request carries Prefer: resolution=merge-duplicates,
        # which updates exactly the columns present in the payload and leaves
        # absent ones alone. Padding a row that simply has no image with
        # `image_url: None` would therefore BLANK an image the catalogue
        # already holds — a data-loss "fix" wearing a fix's clothes, the same
        # shape as the price/price_eur backfill trap in DATA_SCALING_PLAN.md
        # §10. Sending fewer columns is always safe; sending NULL is not.
        by_keyset: dict[frozenset, list[dict]] = {}
        for row in rows:
            by_keyset.setdefault(frozenset(row.keys()), []).append(row)
        if len(by_keyset) > 1:
            logger.info(
                "[catalog] %d rows span %d different column sets; posting as "
                "%d separate groups so PostgREST does not reject the batch",
                len(rows), len(by_keyset), len(by_keyset),
            )

        batches = [
            group[i:i + self.batch_size]
            for group in by_keyset.values()
            for i in range(0, len(group), self.batch_size)
        ]
        # `n` is a batch ORDINAL, not the row offset the old message printed --
        # grouping means batches are no longer contiguous slices of `rows`, so
        # an offset would name a position that does not exist. Say how many
        # rows went with it, since that is the number actually at risk.
        failed_batches = 0     # THIS call only. self.stats.catalog_errors is
                               # cumulative across every pipeline sharing one
                               # IngestStats (see SupabaseIngest(stats=stats)
                               # in crawl4ai_enrich / firecrawl_enrich), so
                               # reporting it here would describe the whole run
                               # while naming this call's row count.
        for n, batch in enumerate(batches, 1):
            try:
                resp = _post_with_retry(self.client, url, headers=_headers(), json=batch)
                if resp.status_code in (200, 201):
                    total += len(batch)
                else:
                    failed_batches += 1
                    self.stats.catalog_errors += 1
                    logger.error(f"Upsert catalog batch {n}/{len(batches)} "
                                 f"({len(batch)} rows LOST): {resp.status_code} "
                                 f"{resp.text[:200]}")
            except Exception as e:
                failed_batches += 1
                self.stats.catalog_errors += 1
                logger.error(f"Upsert catalog batch {n}/{len(batches)} "
                             f"({len(batch)} rows LOST) failed: {e}")
        self.stats.catalog_upserted += total
        if total < len(rows):
            # Say it once, in the writer's own voice. The caller reads a count
            # that EXCLUDES the failures, so a partial write is otherwise
            # indistinguishable from a small catalogue -- which is how 107
            # dropped batches passed as a green nightly run on 2026-08-28.
            logger.error(
                "[catalog] wrote %d of %d rows — %d LOST across %d failed batch(es)",
                total, len(rows), len(rows) - total, failed_batches,
            )
            record_write_loss(len(rows) - total, failed_batches)
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
        rows, dropped_bad_item_ref = self.build_market_hit_rows(hits)
        if dropped_bad_item_ref:
            self.stats.market_hits_errors += dropped_bad_item_ref
            logger.error(
                "upsert_market_hits dropped %d rows with malformed item_ref",
                dropped_bad_item_ref,
            )
        return self._post_market_hit_rows(rows)

    def build_market_hit_rows(self, hits: list[MarketHit]) -> tuple[list[dict], int]:
        """Turn MarketHits into PostgREST row dicts. Pure -- no I/O.

        Split out of `upsert_market_hits` on 2026-08-30 so it can actually be
        TESTED. The first version of the observed_at tests reimplemented this
        loop inside the test file, so mutating the real writer left them green:
        reverting the fix entirely and writing None instead of omitting the key
        BOTH passed. A test that pins its own copy of the logic pins nothing.
        """
        rows: list[dict] = []
        dropped_bad_item_ref = 0
        for h in hits:
            item_ref = f"{h.category}:{h.normalized_key}" if (h.category and h.normalized_key) else None
            # Post-write assertion per learnings.md root-cause essay:
            # item_ref must either be NULL or contain a ':' separator.
            if item_ref is not None and ":" not in item_ref:
                dropped_bad_item_ref += 1
                continue
            observed_at = parse_observed_at(h.sold_at)
            row = {
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
            }
            # The key is OMITTED, not set to None, when the source gave no
            # date. This upsert runs with `resolution=merge-duplicates`, so a
            # NULL in the payload would overwrite an observed_at a previous run
            # had correctly written -- the same reason this writer deliberately
            # does not pad rows to a common key set. Omission also keeps the
            # reader's COALESCE(observed_at, seen_at) fallback intact, so a row
            # without a source date behaves exactly as it does today.
            if observed_at:
                row["observed_at"] = observed_at
            rows.append(row)
        return rows, dropped_bad_item_ref

    def _post_market_hit_rows(self, rows: list[dict]) -> int:
        total = 0
        failed_batches = 0     # THIS call only -- self.stats is shared.
        for i in range(0, len(rows), self.batch_size):
            batch = rows[i:i + self.batch_size]
            try:
                resp = _post_with_retry(
                    self.client,
                    f"{SUPABASE_URL}/rest/v1/market_hits",
                    headers=_headers(),
                    json=batch,
                )
                if resp.status_code in (200, 201):
                    total += len(batch)
                else:
                    failed_batches += 1
                    self.stats.market_hits_errors += 1
                    logger.error(f"Upsert market_hits batch {i} "
                                 f"({len(batch)} rows LOST): {resp.status_code} "
                                 f"{resp.text[:200]}")
            except Exception as e:
                failed_batches += 1
                self.stats.market_hits_errors += 1
                logger.error(f"Upsert market_hits batch {i} "
                             f"({len(batch)} rows LOST) failed: {e}")
        self.stats.market_hits_upserted += total
        if total < len(rows):
            logger.error(
                "[market_hits] wrote %d of %d rows — %d LOST across %d failed batch(es)",
                total, len(rows), len(rows) - total, failed_batches,
            )
            record_write_loss(len(rows) - total, failed_batches)
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
    """GET JSON with retries, exponential backoff, and Retry-After support.

    ⚠️ This is the READ side, and its retry rule is deliberately the OPPOSITE
    of `_post_with_retry`'s. That function refuses to retry any HTTP response
    because PGRST102/21000 are Postgres's judgement of our exact payload and
    fail identically on replay. Here the response comes from a THIRD PARTY and
    the request is an idempotent GET, so a 5xx is weather, not a verdict —
    `api.pokemontcg.io` returned 500/502 on 10+ sets on each of the
    2026-09-03/04/05 nightlies. Retrying it is correct; retrying a 4xx is not,
    for exactly the reason the write path gives.

    Three defects fixed here on 2026-09-05:

    1. **Every status was retried, including 4xx.** A 404 or a malformed query
       burned three attempts and three seconds to arrive at the same answer.
       Only 5xx (and 429) are transient; a 4xx now raises on the first one.
    2. **The backoff was flat.** `time.sleep(delay)` with delay=1.0, three
       times, is three seconds — nothing to a real upstream incident, and
       synchronised across every worker. Now exponential with jitter.
    3. **A run of 429s returned `None`.** The rate-limit branch `continue`s,
       so if every attempt was rate-limited the loop fell out of the bottom
       and the function returned `None` implicitly — and every caller does
       `data.get("data", [])` on it, i.e. `AttributeError` far from the cause.
       Falling out now raises.
    """
    client = get_http_client()
    last_exc: Exception | None = None
    host = urlparse(url).netloc

    # OUTBOUND BUDGET. tcgcsv.com banned this application for overuse on
    # 2026-07-31 and that catalogue has been frozen ever since; the rule that
    # came out of it is "budget and count outbound calls to every third party".
    # Retrying harder into a struggling free API is how that happens twice.
    # After _HOST_FAIL_LIMIT consecutive 5xx from one host, every further call
    # to it fails fast for the rest of the process — no socket, no retry.
    # A successful response resets the count, so a blip costs nothing.
    with _host_fail_lock:
        if _host_failures.get(host, 0) >= _HOST_FAIL_LIMIT:
            raise RuntimeError(
                "circuit open for %s after %d consecutive 5xx — not calling it "
                "again this run (outbound budget; see docs/INGEST.md)"
                % (host, _host_failures[host])
            )

    def _backoff(attempt: int) -> float:
        # Exponential with jitter: synchronised retries from parallel
        # pipelines are how a struggling upstream is kept struggling.
        return delay * (2 ** attempt) * (0.5 + random.random())

    for attempt in range(retries):
        try:
            resp = client.get(url, params=params, headers=headers)
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait = int(retry_after)
                else:
                    wait = _backoff(attempt)
                logger.warning("Rate limited, waiting %.1fs: %s", wait, url)
                last_exc = RuntimeError("rate limited (429) on every attempt: %s" % url)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            with _host_fail_lock:
                _host_failures.pop(host, None)   # a good response clears the streak
            return resp.json()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status >= 500:
                with _host_fail_lock:
                    _host_failures[host] = _host_failures.get(host, 0) + 1
                    if _host_failures[host] == _HOST_FAIL_LIMIT:
                        logger.error(
                            "[ingest] %s has returned %d consecutive 5xx — "
                            "opening the circuit for the rest of this run",
                            host, _HOST_FAIL_LIMIT,
                        )
            if status < 500:
                # Deterministic. It will fail the same way three times.
                logger.warning("HTTP %d (not retryable): %s", status, url)
                raise
            last_exc = e
            logger.warning("HTTP %d on attempt %d/%d: %s", status, attempt + 1, retries, url)
            if attempt == retries - 1:
                raise
            time.sleep(_backoff(attempt))
        except httpx.TransportError as e:
            # Broader than the old ConnectError: "The read operation timed out"
            # and SSL errors are the same class of blip and were escaping
            # unretried.
            last_exc = e
            logger.warning("Transport error on attempt %d/%d (%s): %s",
                           attempt + 1, retries, e, url)
            if attempt == retries - 1:
                raise
            time.sleep(_backoff(attempt))

    # Only reachable when every attempt hit 429. Returning None here silently
    # handed callers a non-dict.
    raise last_exc if last_exc else RuntimeError("fetch_json exhausted retries: %s" % url)


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
