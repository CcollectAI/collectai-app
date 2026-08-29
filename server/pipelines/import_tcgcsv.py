#!/usr/bin/env python3
"""
tcgcsv.com pipeline — free daily TCGPlayer public-price dump.

Fills the TCG data gap created by TCGPlayer closing registrations and
Cardmarket restricting scraping. tcgcsv.com is a community service that
republishes TCGPlayer's public price pages as clean JSON daily.

What this writes:
  market_hits rows with provider='tcgcsv'. Unique key (provider, listing_id)
  where listing_id = TCGPlayer productId. Upserts so re-runs update prices.

Covers: MTG, Pokemon, YuGiOh, Lorcana, One Piece TCG, Digimon. Other
games that tcgcsv indexes (Flesh and Blood, Star Wars Unlimited, etc.)
are skipped unless we add them to CATEGORY_MAP.

Schedule: run_once() daily.

Usage:
  python pipelines/import_tcgcsv.py             # all supported games
  python pipelines/import_tcgcsv.py --game mtg  # single game
  python pipelines/import_tcgcsv.py --dry-run   # fetch but don't upsert
  python pipelines/import_tcgcsv.py --catalog --dry-run --game lorcana
                                                # ALSO derive category_items rows
                                                # keyed to match price item_refs
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from typing import Optional

import httpx

# Add server/ so imports work both as script and as module
REPO_SERVER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_SERVER not in sys.path:
    sys.path.insert(0, REPO_SERVER)

from pipelines.import_common import (
    MarketHit,
    IngestStats,
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY,
    _headers,
    get_http_client,
    record_write_loss,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [import_tcgcsv] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer"

# Map tcgcsv "name" field → our internal category name.
# Discovered via GET /tcgplayer/categories. Names on tcgcsv are canonical
# ("Magic" not "Magic: The Gathering") so we match by name, case-sensitive.
CATEGORY_MAP: dict[str, str] = {
    "Magic": "mtg",
    "YuGiOh": "yugioh",
    "Pokemon": "pokemon",
    "Disney Lorcana TCG": "lorcana",
    "Lorcana TCG": "lorcana",          # in case they rename
    "One Piece Card Game": "one_piece_tcg",
    "Digimon Card Game": "digimon",
}

# Upstream requests — conservative timeouts. Some group payloads are large.
# Categories whose catalog is DERIVED from tcgcsv (see build_catalog_rows).
# Only these: mtg/pokemon already sit at 98-99% coverage on their own slug keys,
# so deriving them would add ~250k redundant rows for no gain. yugioh IS derived
# because its seed catalog is per-printing while its passcode prices are
# per-card — a 545x error on the worst card.
CATALOG_CATEGORIES = {"lorcana", "digimon", "one_piece_tcg", "yugioh"}

HTTP_TIMEOUT = 60.0
PER_REQUEST_SLEEP = 0.5  # be polite to tcgcsv.com — 2/s, was 0.25 (4/s)
# Raised 2026-07-31 after tcgcsv.com blocked the application for overuse.
# A full run is ~1,800 requests, so this costs ~7 extra minutes on a job
# that already takes ~20 and now runs genuinely once a day.


# ---------------------------------------------------------------------------
# tcgcsv fetch helpers
# ---------------------------------------------------------------------------


# Last transport-level failure, so the worker can report WHY it got nothing.
# `_get_json` returns None on failure and only logs — which meant an HTTP 403
# ("flagged for overuse", ongoing since 2026-07-29) surfaced in worker_runs as
# "None market_hits errors, None hits, None upserted": three Nones and no cause.
# The operator then has to go read bake.log to learn anything at all.
_LAST_HTTP_ERROR: dict[str, str | int | None] = {"url": None, "status": None, "detail": None}


def _get_json(client: httpx.Client, url: str):
    """GET a tcgcsv endpoint. Returns None on failure (non-fatal)."""
    try:
        r = client.get(url, timeout=HTTP_TIMEOUT)
    except httpx.HTTPError as e:
        logger.warning("GET %s failed: %s", url, e)
        _LAST_HTTP_ERROR.update(url=url, status=None, detail=repr(e)[:200])
        return None
    if r.status_code != 200:
        logger.warning("GET %s -> HTTP %d", url, r.status_code)
        _LAST_HTTP_ERROR.update(
            url=url, status=r.status_code, detail=(r.text or "")[:200].strip() or None
        )
        return None
    try:
        body = r.json()
    except Exception as e:
        logger.warning("GET %s -> non-JSON body: %s", url, e)
        return None
    # tcgcsv wraps lists in {"results": [...]} but occasionally returns the
    # raw list — handle both.
    if isinstance(body, dict) and "results" in body:
        return body["results"]
    return body


def _describe_last_http_error(fallback: str) -> str:
    """Turn the last transport failure into an actionable one-liner."""
    status = _LAST_HTTP_ERROR.get("status")
    if status is None and not _LAST_HTTP_ERROR.get("detail"):
        return fallback
    parts = [fallback]
    if status is not None:
        parts.append(f"HTTP {status}")
    if _LAST_HTTP_ERROR.get("url"):
        parts.append(f"on {_LAST_HTTP_ERROR['url']}")
    if _LAST_HTTP_ERROR.get("detail"):
        parts.append(f"— {_LAST_HTTP_ERROR['detail']}")
    return " ".join(str(x) for x in parts)


def list_supported_categories(client: httpx.Client) -> list[dict]:
    """Return [{categoryId, name, our_category}] for games we care about."""
    cats = _get_json(client, f"{TCGCSV_BASE}/categories") or []
    out: list[dict] = []
    for c in cats:
        name = c.get("name")
        if name in CATEGORY_MAP:
            out.append({
                "categoryId": c["categoryId"],
                "name": name,
                "our_category": CATEGORY_MAP[name],
            })
    return out


def list_groups(client: httpx.Client, category_id: int) -> list[dict]:
    return _get_json(client, f"{TCGCSV_BASE}/{category_id}/groups") or []


def list_products(client: httpx.Client, category_id: int, group_id: int) -> list[dict]:
    return _get_json(
        client, f"{TCGCSV_BASE}/{category_id}/{group_id}/products",
    ) or []


def list_prices(client: httpx.Client, category_id: int, group_id: int) -> list[dict]:
    return _get_json(
        client, f"{TCGCSV_BASE}/{category_id}/{group_id}/prices",
    ) or []


# ---------------------------------------------------------------------------
# Transform tcgcsv rows → MarketHit
# ---------------------------------------------------------------------------


def build_hits(
    products: list[dict],
    prices: list[dict],
    our_category: str,
    group_abbreviation: Optional[str] = None,
) -> list[MarketHit]:
    """Join products + prices on productId and materialise MarketHit rows.

    We keep only rows with a non-null marketPrice (real signal). Variants
    with distinct subTypeName (e.g. Normal vs Holofoil) are separate hits
    because their prices diverge.
    """
    # Index products for O(1) join
    by_pid: dict[int, dict] = {p["productId"]: p for p in products if p.get("productId")}

    hits: list[MarketHit] = []
    for price in prices:
        pid = price.get("productId")
        if pid is None:
            continue
        market = price.get("marketPrice")
        if market is None or float(market) <= 0:
            continue  # skip cards with no market signal
        prod = by_pid.get(pid)
        if not prod:
            continue

        subtype = (price.get("subTypeName") or "").strip()
        listing_id = f"{pid}:{subtype}" if subtype else str(pid)
        title = prod.get("name") or prod.get("cleanName") or f"tcgplayer:{pid}"
        if group_abbreviation:
            title = f"{title} [{group_abbreviation}]"
        if subtype:
            title = f"{title} ({subtype})"

        normalized_key = f"{our_category}:tcgplayer:{pid}"
        if subtype:
            normalized_key += f":{subtype.lower().replace(' ', '_')}"

        hits.append(MarketHit(
            provider="tcgcsv",
            listing_id=listing_id,
            title=title[:500],
            price=float(market),
            currency="USD",
            condition="NM",  # tcgplayer market prices are NM baseline
            normalized_key=normalized_key,
            category=our_category,
            url=prod.get("url") or "",
            image_url=prod.get("imageUrl") or "",
        ))
    return hits


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


def upsert_hits_batched(
    hits: list[MarketHit],
    stats: IngestStats,
    batch_size: int = 200,
) -> int:
    """POST hits to market_hits via the upsert_market_hits_batch RPC.

    Background: PostgREST `?on_conflict=provider,listing_id` stopped
    working after market_hits was partitioned (2026-04-19) — Postgres
    requires unique constraints on partitioned tables to include the
    partition key (seen_at), but seen_at = now() defeats dedup. The RPC
    does INSERT ... WHERE NOT EXISTS server-side using the
    (provider, listing_id, seen_at) composite index. See
    supabase/migrations/20260426_upsert_market_hits_batch_rpc.sql.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.warning("SUPABASE env not set — skipping upsert")
        return 0
    if not hits:
        return 0

    client = get_http_client()
    url = f"{SUPABASE_URL}/rest/v1/rpc/upsert_market_hits_batch"
    headers = {**_headers(), "Content-Type": "application/json"}

    total = 0
    # R50l: FX conversion — all tcgcsv prices are USD. Mixed-currency rows in
    # market_hits corrupt training (learning #23). Convert USD → EUR via the
    # fx_service; fall back to storing price unchanged if FX lookup fails.
    try:
        from app.lib.fx_service import convert_to_eur_sync
    except Exception:
        convert_to_eur_sync = None

    for i in range(0, len(hits), batch_size):
        batch = hits[i:i + batch_size]
        rows = []
        for h in batch:
            if convert_to_eur_sync and h.currency and h.currency != "EUR":
                try:
                    price_eur = convert_to_eur_sync(float(h.price), h.currency)
                except Exception:
                    price_eur = h.price
            else:
                price_eur = h.price
            # item_ref must be canonical `{category}:{normalized_key}` so
            # valuation joins (learnings.md §22, §64, §957). The R50l fix
            # that originally added item_ref used bare normalized_key, then
            # R50m's backfill re-prefixed all rows. Updated 2026-04-21 to
            # emit the prefixed form at the writer so re-enabling this
            # pipeline doesn't reintroduce the bug.
            if h.normalized_key and ":" in h.normalized_key:
                item_ref = h.normalized_key
            elif h.category and h.normalized_key:
                item_ref = f"{h.category}:{h.normalized_key}"
            else:
                item_ref = None
            rows.append({
                "provider": h.provider,
                "listing_id": h.listing_id,
                "title": h.title,
                "price": h.price,
                "currency": h.currency,
                "price_eur": price_eur,
                "condition": h.condition,
                "normalized_key": h.normalized_key,
                "item_ref": item_ref,
                "category": h.category,
                "url": h.url,
                "image_url": h.image_url,
            })
        try:
            # RPC body shape: {"rows": [...]}  (the function takes one jsonb arg
            # named `rows`). Returns the count of newly-inserted rows as an int.
            resp = client.post(url, headers=headers, json={"rows": rows})
        except Exception as e:
            stats.market_hits_errors += 1
            logger.error("Batch %d-%d upsert RPC failed: %s", i, i + len(batch), e)
            continue
        if resp.status_code in (200, 201, 204):
            try:
                inserted = int(resp.text or "0")
            except (TypeError, ValueError):
                inserted = len(batch)
            total += inserted
            if inserted < len(batch):
                logger.debug(
                    "Batch %d-%d: %d/%d new (rest deduped)",
                    i, i + len(batch), inserted, len(batch),
                )
        else:
            stats.market_hits_errors += 1
            logger.error(
                "Batch %d-%d HTTP %d: %s",
                i, i + len(batch), resp.status_code, resp.text[:300],
            )
    stats.market_hits_upserted += total
    return total


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def build_catalog_rows(
    hits: list["MarketHit"],
    our_category: str,
    group_name: Optional[str] = None,
    group_abbreviation: Optional[str] = None,
) -> list[dict]:
    """Derive `category_items` rows from the SAME hits that produce prices.

    Why this exists (2026-07-25)
    ----------------------------
    lorcana / digimon / one_piece_tcg had ~0% price coverage: their catalog rows
    are hand-seeded slugs (`azu-abu-tricky-monkey`) while their predictions are
    keyed by TCGplayer product id (`lorcana:tcgplayer:702699:normal`). Two
    disjoint namespaces.

    Crosswalking them was measured and REJECTED: matching on card name alone was
    224-of-226 ambiguous for lorcana, and adding the set as a tiebreak gave 8.2%
    / 1.3% / 0.0% unique matches for one_piece / digimon / lorcana, because the
    set vocabularies barely overlap (lorcana prices bracket sets as NUMBERS,
    `[13]`, while the catalog uses letter codes, `AZU`). A matcher at those rates
    would ship wrong prices for almost no coverage.

    So instead of bridging two namespaces, derive the catalog from the SAME
    source as the prices. `item_key` is the hit's normalized_key minus the
    leading `{category}:`, which makes

        category_items.category || ':' || category_items.item_key
          ==  price_predictions.item_ref

    true BY CONSTRUCTION — the same reason pokemon and mtg already sit at 97-99%
    coverage. No matching, nothing to drift.

    Rows are marked `source='tcgcsv'` so they stay distinguishable from the
    existing `source='seed'` rows, which remain untouched.
    """
    prefix = f"{our_category}:"
    rows: list[dict] = []
    seen: set[str] = set()
    for h in hits:
        nk = h.normalized_key or ""
        if not nk.startswith(prefix):
            continue
        item_key = nk[len(prefix):]
        if not item_key or item_key in seen:
            continue
        seen.add(item_key)
        rows.append({
            "category": our_category,
            "item_key": item_key,
            "title": (h.title or item_key)[:500],
            "set_code": (group_abbreviation or "")[:64] or None,
            "image_url": h.image_url or None,
            "source": "tcgcsv",
            "attributes_json": {
                "set_name": group_name,
                "set_abbreviation": group_abbreviation,
                "tcgplayer_product_id": item_key.split(":")[1] if ":" in item_key else None,
            },
        })
    return rows


def upsert_catalog_rows(rows: list[dict], batch_size: int = 200) -> int:
    """Upsert into category_items on its UNIQUE (category, item_key).

    Idempotent: re-running refreshes title/image/set without duplicating. Does
    NOT touch source='seed' rows, because those have different item_keys.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.warning("SUPABASE env not set — skipping catalog upsert")
        return 0
    if not rows:
        return 0
    import json as _json
    written = 0
    failed_batches = 0
    client = get_http_client()
    url = f"{SUPABASE_URL}/rest/v1/category_items?on_conflict=category,item_key"
    headers = {**_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"}
    for i in range(0, len(rows), batch_size):
        chunk = rows[i:i + batch_size]
        # attributes_json must be posted as an OBJECT, not a pre-serialised
        # string — httpx json= serialises the whole body, and double-encoding it
        # is exactly what produced 598 rejected upserts/day in the 2026-07-25
        # catalog bug (category_items_attrs_is_object).
        try:
            r = client.post(url, headers=headers, json=chunk, timeout=60.0)
            if r.status_code >= 300:
                failed_batches += 1
                logger.error("catalog upsert HTTP %d (%d rows LOST): %s",
                             r.status_code, len(chunk), r.text[:200])
                continue
            written += len(chunk)
        except Exception as e:
            failed_batches += 1
            logger.error("catalog upsert failed (%d rows LOST): %s", len(chunk), e)
    if written < len(rows):
        # This writer is not reachable from import_all (tcgcsv is absent from
        # its tier lists), so it does not gate the nightly. It is recorded
        # anyway: it is the same silent-partial-write class as upsert_catalog,
        # and leaving a known instance of a class I just fixed is how the class
        # comes back. It was also logging losses at WARNING, one level below
        # the errors anyone greps for.
        logger.error(
            "[tcgcsv catalog] wrote %d of %d rows — %d LOST across %d failed batch(es)",
            written, len(rows), len(rows) - written, failed_batches,
        )
        record_write_loss(len(rows) - written, failed_batches)
    return written


def run_game(
    client: httpx.Client,
    category_id: int,
    category_name: str,
    our_category: str,
    dry_run: bool,
    stats: IngestStats,
    catalog: bool = False,
) -> dict:
    """Import all groups for a single tcgcsv category. Returns per-game stats."""
    groups = list_groups(client, category_id)
    logger.info("%s (our=%s): %d groups", category_name, our_category, len(groups))

    total_hits = 0
    total_upserted = 0
    total_catalog = 0
    total_catalog_written = 0
    groups_processed = 0

    for g in groups:
        gid = g.get("groupId")
        if gid is None:
            continue
        group_name = g.get("name") or f"group:{gid}"
        group_abbr = g.get("abbreviation") or None
        time.sleep(PER_REQUEST_SLEEP)
        products = list_products(client, category_id, gid)
        time.sleep(PER_REQUEST_SLEEP)
        prices = list_prices(client, category_id, gid)
        if not products or not prices:
            logger.debug("  skip empty: %s (products=%d prices=%d)",
                         group_name, len(products), len(prices))
            continue
        hits = build_hits(products, prices, our_category, group_abbr)
        if not hits:
            continue
        total_hits += len(hits)
        groups_processed += 1

        do_catalog = catalog and our_category in CATALOG_CATEGORIES
        cat_rows = build_catalog_rows(hits, our_category, group_name, group_abbr) if do_catalog else []
        total_catalog += len(cat_rows)

        if dry_run:
            logger.info("  [dry] %s: %d hits%s (sample: %s @ $%.2f)",
                        group_name[:40], len(hits),
                        ", %d catalog rows" % len(cat_rows) if catalog else "",
                        hits[0].title[:40], hits[0].price)
            if catalog and cat_rows:
                logger.info("        [dry] sample catalog key: %s:%s",
                            our_category, cat_rows[0]["item_key"])
            continue
        upserted = upsert_hits_batched(hits, stats)
        total_upserted += upserted
        cat_written = upsert_catalog_rows(cat_rows) if cat_rows else 0
        total_catalog_written += cat_written
        logger.info("  %s: %d hits, %d upserted%s", group_name[:40], len(hits), upserted,
                    ", %d catalog rows" % cat_written if catalog else "")

    return {
        "category": our_category,
        "groups_processed": groups_processed,
        "total_groups": len(groups),
        "total_hits": total_hits,
        "total_upserted": total_upserted,
        "catalog_rows_seen": total_catalog,
        "catalog_rows_written": total_catalog_written,
    }


def run_pipeline(only_game: Optional[str] = None, dry_run: bool = False,
                 catalog: bool = False) -> dict:
    """Top-level entry point — orchestrates fetch + upsert for all games."""
    stats = IngestStats()
    results: list[dict] = []
    started = time.monotonic()

    with httpx.Client(
        headers={"User-Agent": "CollectAI-tcgcsv-importer/1.0"},
        timeout=HTTP_TIMEOUT,
    ) as client:
        supported = list_supported_categories(client)
        if not supported:
            logger.error("No supported categories returned by tcgcsv")
            return {"ok": False, "reason": _describe_last_http_error("no categories")}

        if only_game:
            supported = [s for s in supported if s["our_category"] == only_game]
            if not supported:
                logger.error("Unknown game '%s' — valid: %s",
                             only_game, sorted(set(CATEGORY_MAP.values())))
                return {"ok": False, "reason": "unknown game"}

        for cat in supported:
            logger.info("─" * 60)
            r = run_game(
                client,
                cat["categoryId"],
                cat["name"],
                cat["our_category"],
                dry_run,
                stats,
                catalog=catalog,
            )
            results.append(r)

    elapsed = time.monotonic() - started
    summary = {
        "ok": stats.market_hits_errors == 0,
        "elapsed_s": round(elapsed, 1),
        "dry_run": dry_run,
        "per_game": results,
        "total_hits": sum(r["total_hits"] for r in results),
        "total_upserted": sum(r["total_upserted"] for r in results),
        "errors": stats.market_hits_errors,
    }
    logger.info("─" * 60)
    logger.info(
        "DONE: %d hits, %d upserted, %d errors in %.0fs",
        summary["total_hits"], summary["total_upserted"],
        summary["errors"], elapsed,
    )
    return summary


# ---------------------------------------------------------------------------
# Worker entry point (for bake_orchestrator)
# ---------------------------------------------------------------------------


async def run_once() -> None:
    """Async wrapper so bake_orchestrator can call this like a worker."""
    import asyncio
    # run_pipeline is sync + uses httpx.Client; delegate to a thread so we
    # don't block the orchestrator's event loop.
    try:
        from app.worker_registry import record_run
    except Exception:
        def record_run(*_a, **_kw):  # fallback if registry missing
            pass

    # Cadence guard. SCHEDULES already says 24h, but _run_worker_loop runs a
    # worker immediately on start and the interval is in-memory only, so every
    # bake restart re-triggered this. On 2026-07-27/28 the service restarted
    # 9 and 12 times, so a "daily" import ran 9-12x — ~1,800 requests each,
    # ~14k/day — and tcgcsv.com blocked the application for overuse on 07-29.
    # 20h (not 24h) so a restart near the usual slot does not push the run to
    # the following day.
    try:
        from app.worker_registry import should_skip_recent_run
        if await should_skip_recent_run("tcgcsv_worker", 20 * 3600):
            return
    except ImportError:
        pass

    loop = asyncio.get_running_loop()
    t0 = time.monotonic()
    try:
        # catalog=True so newly-released products get a category_items row on
        # the same run that first prices them. Without this the derivation is a
        # one-shot: prices would keep flowing for new cards while they stayed
        # unsearchable and un-addable. Only CATALOG_CATEGORIES are derived —
        # mtg/pokemon already sit at 98-99% on their own slug keys and deriving
        # them would add ~250k redundant rows.
        summary = await loop.run_in_executor(
            None, lambda: run_pipeline(catalog=True))
        duration = time.monotonic() - t0
        if not summary.get("ok"):
            # Raise instead of recording our own "error" row. bake_orchestrator
            # already records every worker run, so recording here too wrote TWO
            # rows per cycle (ours "error", the orchestrator's "ok" because we
            # returned normally) — which made 3-of-3 failures read as
            # "3 errors / 6 runs" in the watchdog, i.e. 50% instead of 100%.
            # Raising gives the orchestrator the real status AND populates
            # worker_runs.metadata.error_repr, which was `{}` for two days
            # while the actual cause — an HTTP 403 "flagged for overuse" — sat
            # in bake.log unread.
            # Lead with the REASON. The counters are absent on an early bail
            # (the summary is just {"ok": False, "reason": ...}), so a
            # counters-only message read "None ... None ... None".
            reason = summary.get("reason") or "unknown"
            raise RuntimeError(
                f"tcgcsv import failed: {reason} "
                f"[{summary.get('errors')} market_hits errors, "
                f"{summary.get('total_hits')} hits, "
                f"{summary.get('total_upserted')} upserted]"
            )
        record_run("tcgcsv_worker", "ok", duration_s=duration)
    except Exception as e:
        logger.exception("tcgcsv run_once failed: %s", e)
        raise


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser(description="tcgcsv.com import pipeline")
    p.add_argument("--game", type=str, default=None,
                   help="only run one game (mtg, pokemon, yugioh, lorcana, one_piece_tcg, digimon)")
    p.add_argument("--dry-run", action="store_true",
                   help="fetch but do not upsert")
    p.add_argument("--catalog", action="store_true",
                   help="ALSO derive category_items rows from the same products, keyed so "
                        "category||':'||item_key equals the prediction item_ref (fixes the "
                        "lorcana/digimon/one_piece 0%% price coverage without fuzzy matching)")
    args = p.parse_args()
    summary = run_pipeline(only_game=args.game, dry_run=args.dry_run, catalog=args.catalog)
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
