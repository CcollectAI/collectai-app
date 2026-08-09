#!/usr/bin/env python3
"""Marketplace scrape scheduler — systematically scrapes catalog items via free adapters.

Iterates through category_items in the catalog and calls MarketplaceAgent.find_sold_comps()
for items that lack recent market_hits. Uses ONLY free adapters (no Firecrawl,
Scrape.do, SerpAPI) to avoid cost — enforced by passing `exclude_adapters=
PAID_ADAPTERS` to find_sold_comps. That enforcement was a silent no-op until
2026-08-06 (see the comment in run_once), so this sentence was aspirational
rather than true for months.

Configuration via environment variables:
  MARKETPLACE_SCRAPE_ENABLED   — must be 'true' to start
  MARKETPLACE_SCRAPE_INTERVAL  — seconds between batches (default 300 = 5 min)
  MARKETPLACE_SCRAPE_BATCH     — items per batch (default 10)
  MARKETPLACE_SCRAPE_MAX_DAYS  — auto-shutdown after N days (default 5)
  DB_DSN                       — database connection string (required)

The scheduler auto-disables after MARKETPLACE_SCRAPE_MAX_DAYS days to prevent
ongoing cost from paid adapters post-launch. Set to 0 to disable auto-shutdown.
"""

import asyncio
import datetime
import logging
import os
import re
import signal
import sys
import time

import asyncpg
from app.worker_registry import record_run
from workers.retry import log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [marketplace_scrape] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

INTERVAL = int(os.getenv("MARKETPLACE_SCRAPE_INTERVAL", "300"))  # 5 min
BATCH_SIZE = int(os.getenv("MARKETPLACE_SCRAPE_BATCH", "10"))
MAX_DAYS = int(os.getenv("MARKETPLACE_SCRAPE_MAX_DAYS", "5"))

# Adapters to SKIP (paid per-call)
PAID_ADAPTERS = {"firecrawl", "scrape_do", "serpapi", "google_shopping"}

# Categories that already have >100% coverage via dedicated bulk feeds
# (tcgcsv + scryfall). Including them in this worker's SELECT just means
# 80K+ TCG card items hog the queue and starve thin cats (disney, funko,
# hot_toys etc. were at <2% attempt rate despite running for days).
#
# Coverage snapshot (2026-04-18): pokemon 311%, yugioh 189%, mtg 728%,
# lorcana 651%, one_piece_tcg 817%, digimon 1233%.
#
# ⚠️ 2026-08-06: lorcana / one_piece_tcg / digimon REMOVED from this set.
# Their place here rested on the April coverage snapshot above, and that claim
# is void. Measured 2026-08-06:
#
#   category       catalog_items   ever_scrape_attempted   market_hits EVER
#   lorcana              6,967               7                    0
#   digimon              9,762               7                    0
#   one_piece_tcg        7,675              12                    0
#
# The chain: those three were fed by tcgcsv, tcgcsv has 403'd us since
# 2026-08-01 (see the bake manifest), `market_hits` retention is 1 day, so the
# old rows aged out and nothing replaced them. Meanwhile this skip list kept
# the marketplace scraper away from 24,404 catalog items on the strength of a
# four-month-old number. Silent total outage.
#
# mtg/pokemon/yugioh stay skipped: their feeds (scryfall, cardmarket,
# tcgplayer) are still alive — 331k/229k/167k rows in the last 30 days — so the
# original starvation argument still holds for them. They get buyable coverage
# from the TCG listings pass below instead.
SKIP_CATEGORIES = {
    "pokemon",
    "yugioh",
    "mtg",
}

# Boost list — thin categories with <1,500 market_hits/30d as of 2026-04-24.
# A share of every batch goes to these so 48 non-TCG cats don't starve the
# worst 8. Tuning: this is the "attention quota". If hits_30d climbs above
# the threshold, remove from this set at the next quarterly audit.
BOOST_CATEGORIES = {
    "ghibli",
    "pens",
    "whiskey",
    "pop_fandom",
    "action_figures",
    "keycaps",
    "blind_box",
    "taylor_swift",
}
BOOST_SHARE = 0.25  # 25% of each batch reserved for BOOST_CATEGORIES

# TCG listings pass — items per cycle, ON TOP of BATCH_SIZE.
#
# Sized as a trickle on purpose. At the default 5-minute interval this is
# 3 items/cycle = ~864 eBay calls/day, one adapter each. That is the entire
# outbound cost of giving mtg/pokemon/yugioh buyable rows, and it is bounded by
# a constant rather than by how big the catalog grows — which is the mistake
# that got tcgcsv.com to block us (see
# learning_third_party_rate_bans_and_schedule_drift: enforce the rate IN the
# worker, never trust a docstring's idea of a schedule).
#
# Set TCG_LISTINGS_BATCH=0 to switch the pass off without a deploy.
TCG_LISTINGS_BATCH = int(os.getenv("TCG_LISTINGS_BATCH", "3"))

# Cardmarket-via-Firecrawl legs per cycle. PAID: 1 Firecrawl credit each,
# against a 1,000/month allocation that resets on the 4th.
#
# Restricted to WATCHED items (a watchlist row with a target price) on purpose.
# Cardmarket is the only source of buyable TCG listings in Europe — Crawl4AI is
# Cloudflare-blocked on it and eBay's TCG results are US-skewed — but at 1
# credit per page the catalog is unaffordable (25k mtg items alone). A watched
# item with a target price is the only row that can actually produce a Target
# Hit today, so every credit spent here has a chance of converting. There is
# currently ~1 such item, so real spend is a trickle.
#
# 2/cycle * 288 cycles = 576/day IF that many watched items existed; they do
# not, and the selector naturally starves this leg when demand is low. Set
# FIRECRAWL_TCG_PER_CYCLE=0 to stop paid spend without a deploy.
# DEFAULT 0 — the leg is built and proven to REACH Cardmarket, but its output
# is not fit for purpose yet. Measured 2026-08-06: 8 hits, 2 survived the gates,
# and both were product INDEX PAGES, not offers:
#   "Bayou - MTG Cards"            EUR 21000  /Magic/Cards/Bayou
#   "Bayou (all ver.) - MTG Cards" EUR 22499  /Magic/Cards/Bayou/Versions
# They persist with is_listing=TRUE, so Target Hit would treat a product page
# as a buyable offer and land the user somewhere they cannot buy. Firecrawl's
# `search` returns web pages; Cardmarket's actual offers live in a table on the
# product page and need a dedicated scrape+parse (`/v1/scrape` on the product
# URL, then parse the seller rows) before this is worth a credit.
# Cost note: measured ~6 credits per call, not 1.
FIRECRAWL_TCG_PER_CYCLE = int(os.getenv("FIRECRAWL_TCG_PER_CYCLE", "0"))

# ── Thin-category Firecrawl leg (PAID, ~6 credits/call) ──────────────────────
#
# Supersedes the Cardmarket leg above. Rationale: mtg/pokemon/yugioh already
# hold 331k/229k/167k market_hits per 30 days, so a paid credit spent there buys
# the least of anywhere in the catalog. The starved end is where a paid scrape
# is the ONLY way in. Measured 2026-08-06 (items -> hits/30d):
#
#   one_piece_tcg 7,675 ->   0      comic_books      799 ->   0
#   lorcana       6,967 ->  47      retro_handhelds 1,111 ->  67
#   plush_collect 1,104 ->  73      sportscards      914 ->  82
#
# Set FIRECRAWL_THIN_PER_CYCLE=0 to stop all paid spend without a deploy.
FIRECRAWL_THIN_PER_CYCLE = int(os.getenv("FIRECRAWL_THIN_PER_CYCLE", "2"))

# A category above this many market_hits/30d is NOT thin and is excluded from
# the paid leg entirely. Matches BOOST_CATEGORIES' existing "<1,500/30d"
# definition so the two notions of "thin" cannot drift apart.
THIN_CATEGORY_MAX_HITS = int(os.getenv("THIN_CATEGORY_MAX_HITS", "1500"))

# DAILY cap on paid Firecrawl items — the control that actually matters.
#
# Per-cycle budgets are the wrong unit here: this worker runs every 5 minutes
# (288 cycles/day), so even 1 item/cycle at a MEASURED ~11 credits/call is
# ~3,200 credits/day against a 1,000/month allocation. Anything per-cycle
# exhausts the month in hours.
#
# 3 items/day * ~11 credits = ~33/day * 29 days = ~950, i.e. the allocation
# lasts exactly to the 2026-09-04 reset. Enforced by counting rows actually
# written in the last 24h, so a restart cannot reset the budget.
FIRECRAWL_THIN_PER_DAY = int(os.getenv("FIRECRAWL_THIN_PER_DAY", "3"))


async def _firecrawl_items_today(conn) -> int:
    """Distinct items given a paid Firecrawl scrape in the last 24h."""
    return await conn.fetchval(
        """
        SELECT count(DISTINCT item_ref)
        FROM public.market_hits
        WHERE provider = 'firecrawl'
          AND seen_at > now() - interval '24 hours'
        """
    ) or 0


def _thin_eligible_categories() -> set:
    """Categories where Firecrawl reaches a site the free adapters cannot.

    Eligibility is derived from CATEGORY_SITE_TARGETS at call time rather than
    hardcoded, so this cannot drift from the adapter config. A category whose
    only targets are eBay domains is excluded: the free eBay adapter already
    covers those, and paying to re-scrape them buys nothing.

    This is also what keeps the populated TCG categories out — their targets
    are tcgplayer/scryfall/cardmarket, which is why the check is "has a
    non-eBay site" AND the selector orders by scarcity.
    """
    try:
        from app.agents.adapters.firecrawl_caller import CATEGORY_SITE_TARGETS
    except Exception:
        return set()
    return {
        cat for cat, sites in CATEGORY_SITE_TARGETS.items()
        if any("ebay" not in (site or "").lower() for site in (sites or []))
    }

# Query qualifier + accept-tokens per TCG category.
#
# MEASURED THE HARD WAY 2026-08-06: searching eBay for the bare card title
# "Bayou" (a real MTG dual land) returned 20 listings, persisted them all as
# buyable `mtg` rows, and every single one was junk — "Midnight Bayou -
# Hardcover By Roberts", "Flags on the Bayou: A Novel", "The Adventures of
# Bayou Billy - Nintendo". Books and a NES cartridge.
#
# That is not cosmetic. Those rows land with
# `item_ref = 'mtg:sum-283-bayou'`, which is the snipe's EXACT-identity arm, so
# a €3.20 novel would have fired a Target Hit against an €8015 watchlist target
# — precisely the bug removed on 2026-08-04, reintroduced through the back
# door. Rows were deleted; the guards below exist so it cannot recur.
#
# `qualifier` is appended to the search query. `accept` are lowercase tokens,
# at least one of which MUST appear in a listing title for the hit to be kept
# (see _is_plausible_tcg_listing). Per
# learning_keyword_filters_need_per_category_false_positive_audit: read every
# match per category, never the total.
_TCG_QUERY_RULES: dict[str, dict] = {
    "mtg": {
        "qualifier": "MTG Magic the Gathering card",
        "accept": ("mtg", "magic the gathering", "magic:"),
    },
    "pokemon": {
        "qualifier": "Pokemon TCG card",
        "accept": ("pokemon", "pokémon"),
    },
    "yugioh": {
        "qualifier": "Yugioh YuGiOh card",
        "accept": ("yugioh", "yu-gi-oh", "yu gi oh"),
    },
    "lorcana": {
        "qualifier": "Disney Lorcana TCG card",
        "accept": ("lorcana",),
    },
    "digimon": {
        "qualifier": "Digimon TCG card",
        "accept": ("digimon",),
    },
    "one_piece_tcg": {
        "qualifier": "One Piece TCG card",
        "accept": ("one piece", "op-", "opcg"),
    },
}


# Titles that are demonstrably not the card itself. All observed in real eBay
# results for "Bayou MTG" on 2026-08-06.
_TCG_REJECT_TOKENS = (
    # Not a card at all
    "custom", "proxy", "playmat", "sleeve", "token", "alter", "altered",
    "sticker", "poster", "art print", "hand-painted", "hand painted",
    "digital", "code card", "empty box", "binder",
    # Sealed product / multi-card, not the single card. Added 2026-08-06 after
    # "2 Pokemon TCG Mega Moonlit ex Tin Bundle Clefable & Gengar Sealed New"
    # (€45.05) was persisted against `pokemon:base2-base2-1` (Base Set 2
    # Clefable). It passed the category marker, the name token AND the price
    # band — a sealed tin costs about what a rare single costs, so price cannot
    # separate them. Product type is the only discriminator.
    "tin", "bundle", "booster", " pack", "packs", "sealed", "lot of",
    "collection box", "elite trainer", "blister", "display",
)

# Price band around the item's known reference price, as a fraction.
#
# WHY THIS EXISTS — measured 2026-08-06. After the title gate below was added,
# an eBay search for the MTG dual land "Bayou" still returned, and persisted:
# "Bayou Dragonfly" (€1.20, a different card), "Bayou Groff" (€1.55, a
# different card), "Bayou Token" (€1.73), "MTG Card Sleeves - Bayou" (€19.49)
# and two "Custom Magic card" proxies. Every one contains both "Bayou" and
# "MTG", so no keyword rule can separate them from the real thing.
#
# A €1.20 row under `item_ref = 'mtg:sum-283-bayou'` would fire a Target Hit
# against that item's €8015 target reading "100% below your target" — the
# identical bug removed on 2026-08-04.
#
# Price is the discriminator that works: a different card, a token or a sleeve
# is orders of magnitude cheaper than the card it is named after. The band is
# asymmetric — generous upside (graded/sealed copies legitimately go high),
# strict downside, because the downside is where the harm is.
_TCG_PRICE_FLOOR_RATIO = 0.35
_TCG_PRICE_CEIL_RATIO = 4.0

# ── KNOWN LIMITATION: printing precision ─────────────────────────────────────
#
# These three gates make the pass SAFE. They do not make it exact.
#
# Measured 2026-08-06 with all gates on:
#   * mtg `sum-283-bayou` (Summer Magic Bayou, ref EUR 8015) → **0 rows**.
#     eBay only surfaced Revised Bayou at EUR 256-476, the price band rejected
#     every one, and the pass wrote nothing. Correct: a wrong printing is a
#     wrong item, and failing closed is the whole design.
#   * pokemon `swsh45sv-...-sv058` (Shining Fates SV058, ref ~EUR 5) → 8 rows,
#     all genuine Alcremie cards, but from Stellar Crown / Brilliant Stars /
#     Journey Together — **different printings**. The band cannot separate them
#     because every Alcremie printing costs EUR 1-7.
#
# So: expensive cards self-protect (price separates printings), cheap cards do
# not. The residual harm is a user watching one printing being alerted about
# another at a similar price — annoying, bounded, and nothing like the €1.20
# novel that started this.
#
# The real fix is eBay's structured catalogue (EPID) instead of free-text
# search — string matching cannot reliably identify a printing. Do NOT try to
# close this with more keyword rules; that path was measured and it trades all
# of the yield for none of the precision.
# ─────────────────────────────────────────────────────────────────────────────


async def _get_reference_price(conn, item_ref: str) -> float | None:
    """Median known price for an item, from the bulk price feeds.

    TCG categories have excellent PRICE coverage (that is why they are in
    SKIP_CATEGORIES) — scryfall/tcgcsv/cardmarket rows. That coverage is
    exactly what makes the price band usable here: we always know roughly what
    the card is worth before we go looking for offers.

    Returns None when we have no reference, and the caller then writes NOTHING.
    Failing closed is deliberate: an unpriceable item is one we cannot
    sanity-check, and a wrong buyable row is worse than a missing one.
    """
    return await conn.fetchval(
        """
        SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY price_eur)
        FROM public.market_hits
        WHERE item_ref = $1
          AND price_eur IS NOT NULL
          AND price_eur > 0
          AND is_listing IS NOT TRUE
        """,
        item_ref,
    )


def _collector_number(item_key: str) -> str | None:
    """Extract the printing's collector number from a catalog item_key.

    Keys look like `5dn-120-eon-hub` (set-number-name) or
    `tdc-332-talisman-of-impulse`. The middle numeric segment is the collector
    number, and it is the only cheap handle we have on WHICH PRINTING an item
    is. Returns None for keys with no numeric segment (e.g. the
    `tcgplayer:95863:1st_edition` style), where no number check is possible.
    """
    if not item_key:
        return None
    for part in item_key.split("-")[1:]:
        if part.isdigit():
            return part.lstrip("0") or "0"
    return None


def _printing_matches(listing_title: str, collector_no: str | None) -> bool:
    """Reject a listing that names a DIFFERENT printing's collector number.

    Measured 2026-08-06: `mtg:tdc-332-talisman-of-impulse` (Tarkir Dragonstorm
    #332) collected 14 buyable rows, most of them other printings — Mirrodin
    254, Bloomburrow 0287, Modern Horizons 3 0311, Doctor Who 0251. Every one
    passes the title gate and the price band, because it IS the same card name
    and every printing costs EUR 0.86-1.72. Price cannot separate printings
    that cost the same.

    The rule is asymmetric on purpose:
      * listing quotes numbers, none of which is ours -> REJECT (it is
        provably a different printing)
      * listing quotes no number at all               -> ACCEPT (we cannot
        disprove it, and the correct-set listings often omit the number, e.g.
        "NM Talisman of Impulse, MTG, Tarkir Dragonstorm")

    Precision over recall, because this feeds a PAID alert: a wrong Target Hit
    costs the user's daily quota and their trust, a missing one costs nothing.
    """
    if not collector_no:
        return True
    nums = {n.lstrip("0") or "0" for n in re.findall(r"\d+", listing_title or "")}
    if not nums:
        return True
    return collector_no in nums


def _is_plausible_tcg_listing(listing_title: str, card_title: str, category: str) -> bool:
    """Reject listings that are not plausibly the card we searched for.

    Two conditions, both required:

    1. **A category marker.** The listing title must contain one of the
       category's `accept` tokens. This is what kills "Midnight Bayou -
       Hardcover By Roberts": a genuine MTG listing essentially always says
       "MTG" or "Magic the Gathering" somewhere, because that is how sellers
       make themselves findable.
    2. **The card name.** Every alphanumeric token of the card title (length
       >= 3) must appear in the listing title. Short tokens are skipped so
       "Sol Ring" is not rejected by a missing "of"/"the".

    Deliberately conservative: a false NEGATIVE costs one missed listing, a
    false POSITIVE fires a wrong Target Hit at a user. Those are not
    symmetrical.
    """
    if not listing_title or not card_title:
        return False
    lt = listing_title.lower()

    rules = _TCG_QUERY_RULES.get(category)
    if rules and not any(tok in lt for tok in rules["accept"]):
        return False

    # Accessories, proxies and altered art all legitimately carry the card's
    # name and the category marker. They are not the card.
    if any(tok in lt for tok in _TCG_REJECT_TOKENS):
        return False

    tokens = [t for t in re.split(r"[^a-z0-9]+", card_title.lower()) if len(t) >= 3]
    if not tokens:
        # Nothing substantial to match on (e.g. a numeric-only title) — the
        # category marker alone is not enough to claim identity.
        return False
    return all(t in lt for t in tokens)

_shutdown = False
_shutdown_event = asyncio.Event()
_started_at = time.time()


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Received signal %d, shutting down", signum)
    _shutdown = True
    _shutdown_event.set()


async def _get_stale_items(conn, batch_size: int):
    """Get catalog items due for a scrape attempt.

    Two-pass policy, both of which hit the same partial index
    `idx_category_items_scrape_attempt` on `last_scrape_attempt_at NULLS FIRST
    WHERE title IS NOT NULL`:

      1. **Bootstrap**: `WHERE last_scrape_attempt_at IS NULL LIMIT N` — uses
         the NULL-leading partial index; degenerates to a covered range scan.
      2. **Round-robin**: once all items have been touched once, fall back to
         `ORDER BY last_scrape_attempt_at ASC LIMIT N` (again index-aided).

    History of this query:
      * v1 LEFT-JOINed a `MAX(seen_at) GROUP BY item_ref` aggregate over the
        full 200k `market_hits` rows every cycle — timed out on the pooler's
        30s cap.
      * v2 dropped the aggregate but kept `WHERE category <> ALL(skip)` +
        `ORDER BY last_scrape_attempt_at`. Planner chose a Parallel Seq Scan
        (11s / 40 rows) because the `<>ALL` filter matches ~75% of rows — the
        partial index became unattractive relative to a full scan.
      * v3 (this): splits into two index-friendly queries and filters
        SKIP_CATEGORIES in Python after the fetch. Over-fetches 4× the batch
        size to cover the skip-ratio without a second round-trip.
    """
    # Filter skip categories IN SQL (not Python) because the NULL-attempted
    # pool is ~136k rows dominated by TCG categories (mtg/pokemon/yugioh/etc)
    # that are in SKIP_CATEGORIES. A Python-side filter threw away all rows
    # every cycle (2026-04-19: 6h of 0-hit cycles because the first 160 rows
    # were all yugioh). Postgres scans the partial index until it finds
    # batch_size matching rows — typically still fast.
    skip_list = sorted(SKIP_CATEGORIES)

    # Pass 0: boost — dedicate BOOST_SHARE of the batch to BOOST_CATEGORIES.
    # Round-robin per category via ROW_NUMBER() PARTITION BY so all 8 cats
    # share the boost slots fairly. Plain `ORDER BY last_scrape_attempt_at
    # ASC NULLS FIRST LIMIT N` packs NULL rows together with no tiebreaker,
    # so heap order picks one cat over the rest — on 2026-05-10 taylor_swift
    # took 286/1060 attempts/24h while action_figures/blind_box/ghibli/pens/
    # keycaps/pop_fandom (0 NULLs left) got 0 attempts for 8-14 days.
    # Same bug we hit in catalog_crawler 2026-04-25 (lorcana drought).
    #
    # Tiebreaker uses random() — with batch_size=20 and 8 BOOST cats the
    # quota is 5, so ORDER BY rn, category alphabetical would always pick
    # the first 5 (action_figures..pens) and never the last 3 (pop_fandom,
    # taylor_swift, whiskey). random() rotates the 5-of-8 selection across
    # cycles; over a day all 8 get roughly equal exposure.
    boost_quota = max(1, int(batch_size * BOOST_SHARE))
    boost_list = sorted(BOOST_CATEGORIES)
    boost = await conn.fetch(
        """
        SELECT id, item_key, title, category
        FROM (
            SELECT id, item_key, title, category,
                   ROW_NUMBER() OVER (
                       PARTITION BY category
                       ORDER BY last_scrape_attempt_at ASC NULLS FIRST
                   ) AS rn
            FROM public.category_items
            WHERE title IS NOT NULL
              AND category = ANY($2::text[])
        ) ranked
        ORDER BY rn, random()
        LIMIT $1
        """,
        boost_quota,
        boost_list,
    )
    out = list(boost)
    remaining = batch_size - len(out)
    if remaining <= 0:
        return out

    # Pass 1: items never attempted — uses idx_category_items_scrape_attempt_null
    bootstrap = await conn.fetch(
        """
        SELECT id, item_key, title, category
        FROM public.category_items
        WHERE title IS NOT NULL
          AND last_scrape_attempt_at IS NULL
          AND category <> ALL($2::text[])
        LIMIT $1
        """,
        remaining,
        skip_list,
    )
    out.extend(bootstrap)
    if len(out) >= batch_size:
        return out

    # Pass 2: fall back to the oldest-attempted when bootstrap is drained
    remaining = batch_size - len(out)
    pass2 = await conn.fetch(
        """
        SELECT id, item_key, title, category
        FROM public.category_items
        WHERE title IS NOT NULL
          AND last_scrape_attempt_at IS NOT NULL
          AND category <> ALL($2::text[])
        ORDER BY last_scrape_attempt_at ASC
        LIMIT $1
        """,
        remaining,
        skip_list,
    )
    return out + list(pass2)


async def _mark_attempted(conn, item_ids: list) -> None:
    """Bump last_scrape_attempt_at for every item we tried this cycle.

    Called regardless of whether the attempt produced hits — the whole
    point is that niche items don't lock the queue after a zero-hit run.
    category_items.id is uuid; asyncpg handles the coercion from the
    Python-side values returned by fetch() automatically.
    """
    if not item_ids:
        return
    await conn.execute(
        "UPDATE public.category_items "
        "SET last_scrape_attempt_at = NOW() "
        "WHERE id = ANY($1::uuid[])",
        item_ids,
    )


async def _get_tcg_listing_items(conn, batch_size: int) -> list:
    """Pick TCG items that need *buyable listing* coverage.

    SKIP_CATEGORIES keeps mtg/pokemon/yugioh out of the sold-comps passes, and
    that is correct — tcgcsv/scryfall/cardmarket already give those categories
    excellent PRICE coverage (pokemon 311%, mtg 728% as of 2026-04-18).

    But coverage was counted in price rows, and Target Hit needs *offers*.
    Measured 2026-08-06 over 7 days: mtg 276,125 hits / **0 buyable**, pokemon
    193,472 / **0**, yugioh 139,820 / **0** — while every eBay-fed category runs
    85-100% buyable. eBay is not category-gated (`"ebay": None` in
    ADAPTER_CATEGORY_ROUTING); it simply is never asked about these categories.

    So this pass exists to ask. It is deliberately small and separate from the
    sold-comps batch: the point is a trickle of buyable rows for the biggest
    audiences, not to re-open the queue-starvation problem SKIP_CATEGORIES was
    written to fix (80k+ TCG items would swamp the 48 thin categories).

    Watched items first — a target price is the strongest demand signal there
    is, and those are the rows that can actually produce a Target Hit today.

    The category list is SKIP_CATEGORIES itself, deliberately: this pass exists
    to give buyable coverage to exactly the categories the main scrape skips.
    Keeping one source of truth means a category can never fall between the two
    — which is precisely what happened to lorcana/digimon/one_piece_tcg (see
    the SKIP_CATEGORIES comment). It also means this pass only ever runs against
    categories with live bulk price feeds, which is what makes
    `_get_reference_price` able to answer.
    """
    if batch_size <= 0:
        return []
    tcg = sorted(SKIP_CATEGORIES)

    # Pass A: catalog items someone is watching with a target price.
    # watchlist_items.item_id holds a BARE canonical key; category_items.item_key
    # is the same vocabulary (see learning_canonical_key_vs_item_ref_namespace).
    demand = await conn.fetch(
        """
        SELECT ci.id, ci.item_key, ci.title, ci.category, TRUE AS is_watched
        FROM public.category_items ci
        JOIN public.watchlist_items w
          ON w.item_id = ci.item_key
         AND w.category = ci.category
        WHERE ci.title IS NOT NULL
          AND ci.category = ANY($2::text[])
          AND w.target_price IS NOT NULL
          AND w.target_price > 0
        ORDER BY ci.last_scrape_attempt_at ASC NULLS FIRST
        LIMIT $1
        """,
        batch_size,
        tcg,
    )
    out = list(demand)
    if len(out) >= batch_size:
        return out

    # Pass B: round-robin the TCG catalog so all six categories get coverage
    # rather than the alphabetically-first one monopolising the quota.
    remaining = batch_size - len(out)
    seen = {r["id"] for r in out}
    fill = await conn.fetch(
        """
        SELECT id, item_key, title, category, FALSE AS is_watched FROM (
            SELECT id, item_key, title, category,
                   ROW_NUMBER() OVER (
                       PARTITION BY category
                       ORDER BY last_scrape_attempt_at ASC NULLS FIRST
                   ) AS rn
            FROM public.category_items
            WHERE title IS NOT NULL
              AND category = ANY($2::text[])
        ) t
        ORDER BY rn, category
        LIMIT $1
        """,
        remaining + len(seen),
        tcg,
    )
    for r in fill:
        if r["id"] not in seen:
            out.append(r)
            if len(out) >= batch_size:
                break
    return out


async def _get_thin_category_items(conn, batch_size: int) -> list:
    """Catalog items from the most data-starved categories.

    Ordered by how little the category has, then by least-recently attempted,
    so the scarcest categories get the paid credits first and no single item
    monopolises them.
    """
    if batch_size <= 0:
        return []
    eligible = sorted(_thin_eligible_categories())
    if not eligible:
        return []
    return await conn.fetch(
        """
        WITH density AS (
            SELECT c.category, count(mh.*) AS hits
            FROM unnest($2::text[]) AS c(category)
            LEFT JOIN public.market_hits mh
                   ON mh.category = c.category
                  AND mh.seen_at > now() - interval '30 days'
            GROUP BY c.category
            -- STRUCTURAL exclusion of well-covered categories, not merely
            -- sorting them last. mtg/pokemon/yugioh pass the non-eBay-site
            -- eligibility test (tcgplayer/scryfall/cardmarket) but hold
            -- 331k/229k/167k hits per 30 days — paying to scrape them buys the
            -- least of anywhere in the catalog. Threshold matches the existing
            -- BOOST_CATEGORIES definition of "thin".
            HAVING count(mh.*) < $3
        )
        SELECT ci.id, ci.item_key, ci.title, ci.category
        FROM public.category_items ci
        JOIN density d ON d.category = ci.category
        WHERE ci.title IS NOT NULL
          AND length(ci.title) >= 3
        ORDER BY d.hits ASC, ci.last_scrape_attempt_at ASC NULLS FIRST
        LIMIT $1
        """,
        batch_size,
        eligible,
        THIN_CATEGORY_MAX_HITS,
    )


def _is_plausible_generic_listing(listing_title: str, item_title: str) -> bool:
    """Title gate for NON-TCG categories.

    The TCG gate cannot be reused: it demands a category marker ("MTG",
    "Pokemon") that only trading cards carry, and it leans on a price band that
    thin categories cannot supply — they have no reference price, which is
    precisely why they are thin.

    So this is weaker by necessity: every substantial token of the item title
    must appear in the listing title, and the not-a-product tokens are still
    rejected. Accepting that trade knowingly — a thin category has no watchlist
    targets either, so a wrong row here cannot mis-fire a Target Hit the way the
    Bayou false positives would have.
    """
    if not listing_title or not item_title:
        return False
    lt = listing_title.lower()
    if any(tok in lt for tok in _TCG_REJECT_TOKENS):
        return False
    tokens = [t for t in re.split(r"[^a-z0-9]+", item_title.lower()) if len(t) >= 3]
    if not tokens:
        return False
    # Require most tokens rather than all — non-TCG titles are wordier and
    # sellers abbreviate ("Squishmallow 16in Cam the Cat" vs "Cam the Cat").
    present = sum(1 for t in tokens if t in lt)
    return present >= max(1, int(len(tokens) * 0.7))


async def _scrape_thin_firecrawl(conn, agent, item_key: str, title: str, category: str):
    """PAID Firecrawl scrape for a starved category.

    Deliberately passes **no region**: get_firecrawl_sites() narrows most
    categories to ebay.de, which the free eBay adapter already covers, so
    paying for it buys nothing. With region=None the caller falls back to the
    global CATEGORY_SITE_TARGETS, which is where the genuinely distinct sites
    live (mycomicshop.com, comicbookrealm.com, buyee.jp, booth.pm,
    squishmallowsquad.com). Those are the pages we cannot reach for free.
    """
    try:
        result = await agent.aggregate_search(
            query=title,
            category=category,
            limit=20,
            include_sold=False,
            region=None,
            only_adapters={"firecrawl"},
            ignore_region_policy=True,
        )
        hits = getattr(result, "hits", []) or []
        if not hits:
            logger.info("  [thin-fc] %s/%s: 0 hits", category, item_key[:28])
            return 0

        kept = []
        for h in hits:
            d = h.hit if hasattr(h, "hit") else h
            if not _is_plausible_generic_listing(str(d.get("title") or ""), title):
                continue
            try:
                p = float(d.get("price_eur") or d.get("price") or 0)
            except (TypeError, ValueError):
                continue
            # No reference price exists for these categories, so only sanity
            # bounds are possible. 100k catches the parse errors that have hit
            # this table before (a EUR 20M row, 2026-04-20).
            if 0 < p < 100_000:
                kept.append(h)

        if not kept:
            logger.info(
                "  [thin-fc] %s/%s: %d hits, all rejected",
                category, item_key[:28], len(hits),
            )
            return 0

        result.hits = kept
        inserted = await agent.persist_comps_to_db(
            result, normalized_key=f"{category}:{item_key}", category=category
        )
        logger.info(
            "  [thin-fc] %s/%s: %d hits, %d kept, %d persisted",
            category, item_key[:28], len(hits), len(kept), inserted,
        )
        return inserted
    except Exception as e:
        logger.warning("  [thin-fc] %s/%s: error %s", category, item_key[:28], e)
        return 0


async def _scrape_cardmarket(conn, agent, item_key: str, title: str, category: str):
    """PAID Cardmarket leg for a watched TCG item, via Firecrawl.

    Why Cardmarket and why paid: it is where European TCG singles are actually
    bought, Crawl4AI cannot reach it (Cloudflare JS challenge, observed
    2026-08-06), and eBay's TCG results skew US and cannot pin a printing.
    Firecrawl gets through — verified the same day against the Fifth Dawn
    "Eon Hub" page — at 1 credit per page.

    Reuses the exact same three defences as the eBay leg (_scrape_listings):
    a qualified query, `_is_plausible_tcg_listing`, and the price band. A paid
    source is not a more trustworthy source — the Bayou false positives would
    have been just as wrong coming from Cardmarket.
    """
    rules = _TCG_QUERY_RULES.get(category)
    query = f"{title} {rules['qualifier'] if rules else ''}".strip()

    item_ref = f"{category}:{item_key}"
    ref = await _get_reference_price(conn, item_ref)
    if not ref or ref <= 0:
        return 0
    lo, hi = float(ref) * _TCG_PRICE_FLOOR_RATIO, float(ref) * _TCG_PRICE_CEIL_RATIO

    try:
        result = await agent.aggregate_search(
            query=query,
            category=category,
            limit=20,
            include_sold=False,
            region="europe",          # Cardmarket is the EU site list
            only_adapters={"firecrawl"},
            # _ADAPTER_POLICY has firecrawl:False in every region to stop it
            # firing on every marketplace ingest. That blanket rule stays; this
            # one path opts out because Crawl4AI cannot reach Cardmarket
            # (Cloudflare) and this call is budgeted + watched-items-only.
            ignore_region_policy=True,
        )
        hits = getattr(result, "hits", []) or []
        if not hits:
            logger.info("  [tcg-cardmarket] %s: 0 hits (1 credit)", item_key[:36])
            return 0

        kept = []
        for h in hits:
            d = h.hit if hasattr(h, "hit") else h
            if not _is_plausible_tcg_listing(str(d.get("title") or ""), title, category):
                continue
            try:
                p = float(d.get("price_eur") or d.get("price") or 0)
            except (TypeError, ValueError):
                continue
            if lo <= p <= hi:
                kept.append(h)

        if not kept:
            logger.info(
                "  [tcg-cardmarket] %s: %d hits, all rejected (band EUR %.2f-%.2f)",
                item_key[:36], len(hits), lo, hi,
            )
            return 0

        result.hits = kept
        inserted = await agent.persist_comps_to_db(
            result, normalized_key=item_ref, category=category
        )
        logger.info(
            "  [tcg-cardmarket] %s: %d hits, %d kept, %d persisted",
            item_key[:36], len(hits), len(kept), inserted,
        )
        return inserted
    except Exception as e:
        logger.warning("  [tcg-cardmarket] %s: error %s", item_key[:36], e)
        return 0


async def _scrape_listings(conn, agent, item_key: str, title: str, category: str):
    """eBay-only *search* for one item, persisted as buyable market_hits.

    Two deliberate differences from _scrape_item below:

    1. `aggregate_search`, not `find_sold_comps`. The sold path contributes
       nothing from eBay — `EbayCaller.sold_comps` needs the Marketplace
       Insights API we do not have. Search mode returns active listings, and
       `persist_comps_to_db` sets `is_listing = (ended_at IS NULL)`, so those
       rows land buyable, which is exactly what the snipe query requires.
       Verified live against prod 2026-08-06: 'Temple of the False God'/mtg →
       10 eBay hits, 'Alcremie'/pokemon → 10 eBay hits.

    2. `only_adapters={"ebay"}`. A full fan-out on a TCG query re-queries the
       price feeds these categories already have, and Cardmarket answers our
       scrape with a Cloudflare challenge. One adapter, one call per item.
    """
    rules = _TCG_QUERY_RULES.get(category)
    qualifier = rules["qualifier"] if rules else ""
    query = f"{title} {qualifier}".strip()

    # Third defence, and the one that actually works — see the
    # _TCG_PRICE_FLOOR_RATIO comment. No reference price => write nothing.
    item_ref = f"{category}:{item_key}"
    ref = await _get_reference_price(conn, item_ref)
    if not ref or ref <= 0:
        logger.info("  [tcg-listings] %s: no reference price, skipping", item_key[:40])
        return 0
    lo = float(ref) * _TCG_PRICE_FLOOR_RATIO
    hi = float(ref) * _TCG_PRICE_CEIL_RATIO

    try:
        result = await agent.aggregate_search(
            query=query,
            category=category,
            limit=20,
            include_sold=False,
            only_adapters={"ebay"},
        )
        hits = getattr(result, "hits", []) or []
        if not hits:
            return 0

        # Second defence: drop anything that does not look like this card.
        # The qualified query alone is NOT enough — eBay still returns loose
        # matches, and one bad row here fires a wrong Target Hit at a real
        # user (see the _TCG_QUERY_RULES comment for what that looked like).
        kept = []
        for h in hits:
            d = h.hit if hasattr(h, "hit") else h
            lt = str(d.get("title") or "")
            if not _is_plausible_tcg_listing(lt, title, category):
                continue
            if not _printing_matches(lt, _collector_number(item_key)):
                continue
            try:
                p = float(d.get("price_eur") or d.get("price") or 0)
            except (TypeError, ValueError):
                continue
            if p <= 0 or p < lo or p > hi:
                continue
            kept.append(h)

        rejected = len(hits) - len(kept)
        if not kept:
            logger.info(
                "  [tcg-listings] %s: %d hits, ALL rejected as false positives",
                item_key[:40], len(hits),
            )
            return 0

        result.hits = kept
        normalized_key = f"{category}:{item_key}"
        inserted = await agent.persist_comps_to_db(
            result, normalized_key=normalized_key, category=category
        )
        logger.info(
            "  [tcg-listings] %s: %d hits, %d rejected (band EUR %.2f-%.2f), %d persisted",
            item_key[:40], len(hits), rejected, lo, hi, inserted,
        )
        return inserted
    except Exception as e:
        logger.warning("  [tcg-listings] %s: error %s", item_key[:40], e)
        return 0


async def _scrape_item(agent, item_key: str, title: str, category: str):
    """Search for a single item using free adapters only, then persist hits."""
    try:
        result = await agent.find_sold_comps(
            query=title,
            category=category,
            limit=20,
            exclude_adapters=PAID_ADAPTERS,
        )
        hits = getattr(result, "hits", []) or []
        if not hits:
            return 0
        normalized_key = f"{category}:{item_key}"
        inserted = await agent.persist_comps_to_db(result, normalized_key=normalized_key, category=category)
        logger.info("  %s: %d hits, %d persisted", item_key[:40], len(hits), inserted)
        return inserted
    except Exception as e:
        logger.warning("  %s: error %s", item_key[:40], e)
        return 0


async def run_once():
    """Execute a single scrape batch."""
    # Prefer direct DSN — _get_stale_items boost+bootstrap passes scan
    # category_items (140k rows) and were hitting the pooler 30s cap
    # consecutively after the BOOST_CATEGORIES change (10+ errors
    # 2026-04-25 05:25 → 06:50 UTC). Direct DSN removes the cap.
    dsn = os.getenv("DB_DSN_DIRECT") or os.getenv("DB_DSN")
    if not dsn:
        logger.error("DB_DSN not set")
        return 0

    # Auto-shutdown check
    if MAX_DAYS > 0:
        elapsed_days = (time.time() - _started_at) / 86400
        if elapsed_days >= MAX_DAYS:
            logger.info(
                "Auto-shutdown: %d days elapsed (limit=%d). Stopping marketplace scraper.",
                int(elapsed_days), MAX_DAYS,
            )
            global _shutdown
            _shutdown = True
            _shutdown_event.set()
            record_run("marketplace_scrape_worker", "ok")
            return 0

    # Tagged via application_name for the ExecStop cancel hook.
    conn = await asyncpg.connect(
        dsn,
        server_settings={"application_name": "collectai-bake-marketplace_scrape_worker"},
    )
    try:
        items = await _get_stale_items(conn, BATCH_SIZE)
        if not items:
            logger.info("No stale items to scrape")
            record_run("marketplace_scrape_worker", "ok")
            return 0

        logger.info("Scraping %d stale items", len(items))

        # Lazy import to avoid circular deps at module level
        from app.agents.marketplace_agent import MarketplaceAgent
        agent = MarketplaceAgent()

        # Paid adapters are excluded per-call via exclude_adapters (see
        # _scrape_item). This used to be
        #     setattr(agent, f"_{name}_caller", None)  guarded by hasattr
        # which NEVER fired — the attribute is `_firecrawl`, not
        # `_firecrawl_caller`, so hasattr returned False and the loop silently
        # did nothing. It looked like a killswitch and was a no-op for months.
        # Invisible while FIRECRAWL_ENABLED=false; the moment that was flipped
        # (2026-08-06) this worker began spending paid Firecrawl credits on
        # every batch — ~2,880 calls/day against a 1,000/month allocation.
        # Nulling the attribute could never have worked either: the task loop
        # reads `inst.configured` and would raise AttributeError on None.

        total_hits = 0
        zero_hit_items = 0
        attempted_ids: list[int] = []
        for row in items:
            if _shutdown:
                break
            hits = await _scrape_item(
                agent,
                row["item_key"],
                row["title"],
                row["category"],
            )
            total_hits += hits
            if hits == 0:
                zero_hit_items += 1
            attempted_ids.append(row["id"])
            # Small delay to avoid hammering adapters
            await asyncio.sleep(2)

        # ── TCG listings pass ────────────────────────────────────────────
        # Separate budget, separate selector, eBay only. Runs AFTER the main
        # batch so a failure here can never cost the sold-comps work that
        # already succeeded — the whole pass is wrapped, and its items are
        # marked attempted regardless so a permanently-zero-hit item cannot
        # monopolise the quota next cycle.
        tcg_hits = 0
        tcg_items: list = []
        if TCG_LISTINGS_BATCH > 0 and not _shutdown:
            try:
                tcg_items = await _get_tcg_listing_items(conn, TCG_LISTINGS_BATCH)
                fc_budget = FIRECRAWL_TCG_PER_CYCLE
                for row in tcg_items:
                    if _shutdown:
                        break
                    tcg_hits += await _scrape_listings(
                        conn,
                        agent,
                        row["item_key"],
                        row["title"],
                        row["category"],
                    )
                    attempted_ids.append(row["id"])
                    await asyncio.sleep(2)

                    # PAID leg — watched items only, and only while the
                    # per-cycle credit budget lasts. Free eBay runs for every
                    # item above; Cardmarket costs a credit, so it is reserved
                    # for rows that can actually convert to a Target Hit.
                    if row["is_watched"] and fc_budget > 0:
                        tcg_hits += await _scrape_cardmarket(
                            conn,
                            agent,
                            row["item_key"],
                            row["title"],
                            row["category"],
                        )
                        fc_budget -= 1
                        await asyncio.sleep(2)
            except Exception as tcg_exc:
                logger.warning("[tcg-listings] pass failed: %s", tcg_exc, exc_info=True)

        # ── Thin-category Firecrawl pass (PAID) ──────────────────────────
        # Separate budget again. mtg/pokemon/yugioh are excluded by
        # construction: _thin_eligible_categories() only yields categories with
        # a non-eBay site target, and the selector orders by scarcity, so the
        # credits land on the starved end of the catalog.
        thin_hits = 0
        thin_items: list = []
        if FIRECRAWL_THIN_PER_CYCLE > 0 and not _shutdown:
            try:
                spent_today = await _firecrawl_items_today(conn)
                allowance = max(0, FIRECRAWL_THIN_PER_DAY - spent_today)
                if allowance == 0:
                    logger.info(
                        "[thin-fc] daily cap reached (%d/%d items) — skipping",
                        spent_today, FIRECRAWL_THIN_PER_DAY,
                    )
                thin_items = await _get_thin_category_items(
                    conn, min(FIRECRAWL_THIN_PER_CYCLE, allowance)
                )
                for row in thin_items:
                    if _shutdown:
                        break
                    thin_hits += await _scrape_thin_firecrawl(
                        conn, agent, row["item_key"], row["title"], row["category"],
                    )
                    attempted_ids.append(row["id"])
                    await asyncio.sleep(2)
            except Exception as thin_exc:
                logger.warning("[thin-fc] pass failed: %s", thin_exc, exc_info=True)

        try:
            await agent.close()
        except Exception:
            pass

        # Bump last_scrape_attempt_at for every item we tried this cycle
        # — even the ones that produced 0 hits. Keeps niche items from
        # re-winning the selector next cycle.
        try:
            await _mark_attempted(conn, attempted_ids)
        except Exception as e:
            logger.warning("Failed to mark items attempted: %s", e)

        # WARN + report worker error when the whole batch produced nothing.
        # Pre-2026-04-27 this logged a warning but reported `ok`, leaving the
        # silent_writer probe (6h staleness threshold) as the only signal.
        # Today's persist_comps TimeoutError outage silently produced
        # `Persisted 0/N` for hours before the table-staleness probe caught
        # it. Recording `error` here lets the orchestrator's
        # consecutive-error Telegram alert fire after 3 unproductive batches
        # (~45 min at 15-min intervals) instead of waiting 6h for table
        # staleness. False positives possible if the picked items genuinely
        # have no marketplace coverage — but 3 in a row from random items
        # is an extremely strong signal of upstream failure.
        if total_hits == 0 and len(items) > 0:
            logger.warning(
                "Batch unproductive: 0 hits from %d items — check adapter circuit state",
                len(items),
            )
            record_run("marketplace_scrape_worker", "error")
        else:
            # tcg_hits is reported but deliberately NOT folded into the
            # unproductive-batch check above: that check is the early-warning
            # signal for a broad adapter outage, and a 3-item eBay-only pass is
            # too small a sample to move it without adding false positives.
            logger.info(
                "Batch complete: %d items, %d total hits, %d items with 0 hits "
                "| tcg-listings: %d items, %d hits | thin-fc: %d items, %d hits",
                len(items), total_hits, zero_hit_items,
                len(tcg_items), tcg_hits, len(thin_items), thin_hits,
            )
            record_run("marketplace_scrape_worker", "ok")
        return total_hits

    finally:
        await conn.close()


async def scheduler_loop():
    """Run scrape batches in a loop."""
    logger.info(
        "Marketplace scrape scheduler started (interval=%ds, batch=%d, max_days=%d)",
        INTERVAL, BATCH_SIZE, MAX_DAYS,
    )

    while not _shutdown:
        try:
            await run_once()
        except Exception as e:
            log_dead_letter("marketplace_scrape_scheduler", {}, e)
            logger.exception("Scrape batch failed: %r", e)
            record_run("marketplace_scrape_worker", "error")

        if _shutdown:
            break

        try:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=INTERVAL)
            break
        except asyncio.TimeoutError:
            pass

    logger.info("Marketplace scrape scheduler stopped")


def main():
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if not os.getenv("DB_DSN"):
        logger.error("DB_DSN not set — cannot start")
        sys.exit(1)

    asyncio.run(scheduler_loop())


if __name__ == "__main__":
    main()
