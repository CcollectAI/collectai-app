"""The writer must carry the SOURCE'S price date, not just our fetch time.

`MarketHit.sold_at` existed from the start and `upsert_market_hits` never put
it in the row dict -- captured and dropped. import_pokemon (TCGplayer and
Cardmarket `updatedAt`) and import_lorcana all populate it, so every one of
those rows fell back to `seen_at`: when WE fetched, not when the price was
computed.

These tests pin BOTH halves, because either alone is passable by a wrong
implementation: the value must be written when present, AND the key must be
absent when there is no source date (writing None would clobber a good
observed_at under `resolution=merge-duplicates`).
"""
import pytest

from pipelines.import_common import MarketHit, parse_observed_at


class TestParseObservedAt:
    @pytest.mark.parametrize("raw", ["", "   ", None, "not a date", "2026-13-45", 12345])
    def test_unparseable_is_none_not_an_exception(self, raw):
        # None is load-bearing: the reader COALESCEs to seen_at, so an
        # unparseable date must degrade to today's behaviour, never crash a
        # 3M-row ingest.
        assert parse_observed_at(raw) is None

    def test_pokemontcg_slash_format(self):
        # pokemontcg.io returns "2026/08/29" -- not ISO, and the most common
        # single input this function will ever see.
        out = parse_observed_at("2026/08/29")
        assert out is not None and out.startswith("2026-08-29")

    def test_iso_with_z_suffix(self):
        out = parse_observed_at("2026-08-29T10:30:00Z")
        assert out is not None and "2026-08-29" in out

    def test_naive_timestamp_is_made_utc(self):
        # A bare date bound to a timestamptz column is the trap recorded in
        # learning_items_paired_columns_trigger.
        out = parse_observed_at("2026-08-29")
        assert out is not None and ("+00:00" in out or out.endswith("Z"))


class TestWriterCarriesIt:
    """Calls the REAL row builder. The first version of this class copied the
    loop into the test, so reverting the fix and writing None instead of
    omitting the key BOTH passed -- learning_tests_that_pin_a_stub, live."""

    def _builder(self):
        from pipelines.import_common import SupabaseIngest
        w = SupabaseIngest.__new__(SupabaseIngest)   # no network, no config
        w.enabled = True
        return w

    def test_source_date_is_written(self):
        hit = MarketHit(provider="tcgplayer", listing_id="x", title="t", price=1.0,
                        category="pokemon", normalized_key="k", sold_at="2026/08/29")
        rows, dropped = self._builder().build_market_hit_rows([hit])
        assert dropped == 0
        assert rows[0]["observed_at"].startswith("2026-08-29")

    def test_absent_date_OMITS_the_key_rather_than_writing_null(self):
        # `merge-duplicates` means a None here would erase an observed_at that
        # an earlier run wrote correctly.
        hit = MarketHit(provider="scryfall", listing_id="x", title="t", price=1.0,
                        category="mtg", normalized_key="k")
        rows, _ = self._builder().build_market_hit_rows([hit])
        assert "observed_at" not in rows[0]

    def test_the_other_columns_are_unchanged(self):
        hit = MarketHit(provider="cardmarket", listing_id="L1", title="T", price=2.5,
                        category="pokemon", normalized_key="nk", sold_at="2026-08-29")
        row = self._builder().build_market_hit_rows([hit])[0][0]
        assert row["item_ref"] == "pokemon:nk"
        assert row["price"] == 2.5 and row["price_eur"] == 2.5

    def test_the_real_importers_still_supply_a_date(self):
        # Guards the OTHER end: if an importer stops passing sold_at, this fix
        # silently reverts to seen_at with no error anywhere.
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[1] / "pipelines"
        for name in ("import_pokemon.py", "import_lorcana.py"):
            assert "sold_at=" in (root / name).read_text(), \
                f"{name} no longer passes sold_at -- observed_at silently falls back to seen_at"
