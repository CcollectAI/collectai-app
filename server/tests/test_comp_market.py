"""Market of origin — and the parity that stops two copies of one map drifting.

docs/COLLECTOR_DEMAND.md §3: EU and US price the same card ~31% apart. We blend
them and convert everything to EUR at ingest, so `market_hits.currency` reads
'EUR' for all of it and the market of origin is ERASED at storage. `provider` is
the only surviving signal, which is why both the FE and the server key on it --
and why the two maps must be pinned to each other.
"""
import pathlib
import re

import pytest

from app.lib.comp_market import (
    PROVIDER_MARKET, market_of_sources, market_of_evidence, split_by_market,
)

FE_MAP = (pathlib.Path(__file__).resolve().parents[2]
          / "src" / "lib" / "compProvenance.ts")


class TestParityWithTheFrontend:
    def test_matches_the_frontend_map(self):
        """Two copies of one fact is learning_duplicated_value_chain_drifts_silently.

        Parsed rather than duplicated here: writing the expected pairs into this
        test would make it a THIRD copy, and a third copy drifts too.
        """
        src = FE_MAP.read_text()
        block = re.search(r"const PROVIDER_MARKET[^=]*=\s*\{(.*?)\};", src, re.S)
        assert block, "could not find PROVIDER_MARKET in compProvenance.ts"
        fe = dict(re.findall(r"(\w+):\s*'(EU|US)'", block.group(1)))
        assert fe == PROVIDER_MARKET, (
            f"server and frontend market maps disagree.\n"
            f"  server: {PROVIDER_MARKET}\n  frontend: {fe}\n"
            f"A card would then be labelled US on the item screen and EU in the "
            f"portfolio total, or the other way round."
        )

    def test_the_parse_is_not_vacuous(self):
        # An empty parse would make any two maps "agree" -- the failure this
        # gate exists to catch.
        assert len(PROVIDER_MARKET) >= 5


class TestMarketOfSources:
    @pytest.mark.parametrize("provider,expected", [
        ("scryfall", "EU"),      # import_mtg reads eur/eur_foil (Cardmarket-sourced)
        ("cardmarket", "EU"),
        ("lorcast", "EU"),       # import_lorcana reads price_eur
        ("tcgplayer", "US"),     # import_pokemon does to_eur(..., 'USD')
        ("pricecharting", "US"),
    ])
    def test_each_mapping(self, provider, expected):
        assert market_of_sources([{"source": provider}]) == expected

    def test_two_markets_is_mixed(self):
        assert market_of_sources([{"source": "tcgplayer"}, {"source": "cardmarket"}]) == "mixed"

    def test_an_UNMAPPED_provider_makes_no_claim(self):
        # eBay depends on the marketplace id per query. Guessing would be the
        # overclaim the module exists to prevent.
        assert market_of_sources([{"source": "ebay"}]) is None

    def test_the_historic_unknown_provider_makes_no_claim(self):
        # 84% of stored predictions predate the 2026-08-27 provider fix and say
        # 'unknown'. They must not be silently filed as either market.
        assert market_of_sources([{"source": "unknown"}]) is None

    @pytest.mark.parametrize("bad", [None, [], [{}], ["not a dict"], [{"source": ""}]])
    def test_junk_in_none_out(self, bad):
        assert market_of_sources(bad) is None

    def test_reads_a_whole_evidence_summary(self):
        assert market_of_evidence({"sources": [{"source": "tcgplayer", "count": 4}]}) == "US"

    @pytest.mark.parametrize("bad", [None, "a string", 42, {}, {"sources": None}])
    def test_a_malformed_summary_is_None_not_a_crash(self, bad):
        assert market_of_evidence(bad) is None


class TestSplitByMarket:
    def test_totals_and_counts_per_market(self):
        out = split_by_market([
            {"value": 10.0, "market": "US"}, {"value": 5.5, "market": "US"},
            {"value": 20.0, "market": "EU"}, {"value": 1.0, "market": "mixed"},
        ])
        assert out["us_total"] == 15.5 and out["us_count"] == 2
        assert out["eu_total"] == 20.0 and out["eu_count"] == 1
        assert out["mixed_total"] == 1.0

    def test_an_UNKNOWN_market_is_included_and_marked_never_dropped(self):
        """`splitPortfolioByValueSource`'s rule: include and mark, never hide.

        Dropping them would show a member a portfolio worth less than they know
        it is -- a bigger lie than an honest "we cannot say for these".
        """
        out = split_by_market([{"value": 30.0, "market": None}])
        assert out["unknown_total"] == 30.0 and out["unknown_count"] == 1

    def test_the_totals_add_up_to_the_whole_collection(self):
        rows = [{"value": 10, "market": "US"}, {"value": 20, "market": "EU"},
                {"value": 5, "market": None}, {"value": 1, "market": "mixed"}]
        out = split_by_market(rows)
        assert (out["us_total"] + out["eu_total"] + out["mixed_total"]
                + out["unknown_total"]) == 36.0

    def test_empty_in_zeroes_out(self):
        out = split_by_market([])
        assert all(out[k] == 0 for k in out)
