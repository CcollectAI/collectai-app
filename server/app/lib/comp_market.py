"""Which MARKET a valuation's comps came from.

Mirror of `src/lib/compProvenance.ts` on the frontend. Two copies of one map is
`learning_duplicated_value_chain_drifts_silently`, so `PROVIDER_MARKET` below is
pinned against the TS file by
`server/tests/test_comp_market.py::test_matches_the_frontend_map` — an edit to
either side that is not made to both fails the build.

WHY THIS EXISTS (2026-08-31)
--------------------------------------------------------------------------
docs/COLLECTOR_DEMAND.md §3: European and US markets price the same card ~31%
apart, before any methodology difference. We blend them -- TCGplayer is 28.6% of
the corpus and Cardmarket + Scryfall's `eur` fields are ~70% -- convert
everything to EUR at ingest, and the currency column then reads 'EUR' for all of
it, so the market of origin is ERASED at the point of storage. `provider` is the
only surviving signal.

The item card can already say "TCGplayer, Cardmarket · US + EU markets". The
portfolio total says nothing, so a US member's collection value is an
unlabelled, EU-weighted number.

Each mapping was verified in the IMPORTER, not assumed from the brand:
  scryfall  -> EU  import_mtg.py reads `eur`/`eur_foil`, which Scryfall sources
                   from Cardmarket. EU, despite Scryfall being a US site.
  lorcast   -> EU  import_lorcana.py reads `price_eur`/`price_eur_foil`.
  tcgplayer -> US  import_pokemon.py does `to_eur(market_price, "USD")`.
  pricecharting -> US  the adapter sets currency 'USD'.
A provider absent from the map makes NO claim -- eBay depends on the marketplace
id per query, and guessing would be the overclaim this module exists to prevent.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

PROVIDER_MARKET: Dict[str, str] = {
    "scryfall": "EU",
    "cardmarket": "EU",
    "lorcast": "EU",
    "tcgplayer": "US",
    "pricecharting": "US",
}


def market_of_sources(sources: Optional[Iterable[Any]]) -> Optional[str]:
    """'EU' | 'US' | 'mixed' | None for a prediction's evidence sources.

    None when nothing is mappable. Absence of a claim, never a default: a
    portfolio labelled 'EU market' because we could not tell would be worse than
    one labelled nothing.
    """
    if not sources:
        return None
    seen = set()
    for s in sources:
        if not isinstance(s, dict):
            continue
        m = PROVIDER_MARKET.get((s.get("source") or "").strip())
        if m:
            seen.add(m)
    if not seen:
        return None
    return "mixed" if len(seen) > 1 else next(iter(seen))


def market_of_evidence(evidence_summary: Any) -> Optional[str]:
    """As above, straight off a `price_predictions.evidence_summary` jsonb."""
    if not isinstance(evidence_summary, dict):
        return None
    return market_of_sources(evidence_summary.get("sources"))


def split_by_market(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate item values by the market their comps came from.

    Mirrors `splitPortfolioByValueSource` in src/lib/portfolioAnalytics.ts and
    keeps its rule: **include and mark, never hide**. An item whose market
    cannot be determined lands in `unknown_total` rather than being dropped --
    a member whose portfolio silently shrank would be told a smaller lie than
    one whose portfolio is honestly labelled "we cannot say for these".
    """
    out = {
        "us_total": 0.0, "eu_total": 0.0, "mixed_total": 0.0, "unknown_total": 0.0,
        "us_count": 0, "eu_count": 0, "mixed_count": 0, "unknown_count": 0,
    }
    for r in rows:
        value = float(r.get("value") or 0)
        market = r.get("market")
        key = {"US": "us", "EU": "eu", "mixed": "mixed"}.get(market or "", "unknown")
        out[f"{key}_total"] += value
        out[f"{key}_count"] += 1
    for k in ("us_total", "eu_total", "mixed_total", "unknown_total"):
        out[k] = round(out[k], 2)
    return out
