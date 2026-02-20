"""Tests for new marketplace adapters: Cardmarket, Discogs, PriceCharting, StockX, BrickLink."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from collections import OrderedDict


# ---------------------------------------------------------------------------
# Cardmarket
# ---------------------------------------------------------------------------

class TestCardmarketCaller:
    """Tests for the Cardmarket API caller."""

    @pytest.fixture
    def caller(self):
        from app.agents.adapters.cardmarket_caller import CardmarketCaller
        return CardmarketCaller(app_token="test_token", app_secret="test_secret")

    @pytest.fixture
    def unconfigured_caller(self):
        from app.agents.adapters.cardmarket_caller import CardmarketCaller
        return CardmarketCaller(app_token="", app_secret="")

    def test_configured(self, caller):
        assert caller.configured is True

    def test_unconfigured(self, unconfigured_caller):
        assert unconfigured_caller.configured is False

    @pytest.mark.asyncio
    async def test_search_unconfigured_returns_empty(self, unconfigured_caller):
        result = await unconfigured_caller.search("charizard", "pokemon")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_unsupported_category_returns_empty(self, caller):
        result = await caller.search("charizard", "funko")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_success(self, caller):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "product": [
                {
                    "idProduct": 12345,
                    "enName": "Charizard ex",
                    "priceGuide": {"TREND": 42.50, "LOW": 35.00, "AVG": 40.00},
                    "countArticles": 150,
                    "rarity": "Ultra Rare",
                    "image": "cards/123.jpg",
                    "expansion": {"enName": "Obsidian Flames"},
                }
            ]
        }

        with patch.object(caller, "_client") as mock_client:
            client_mock = AsyncMock()
            client_mock.get = AsyncMock(return_value=mock_resp)
            mock_client.return_value = client_mock

            results = await caller.search("charizard", "pokemon", 10)

        assert len(results) == 1
        assert results[0]["source"] == "cardmarket"
        assert results[0]["title"] == "Charizard ex"
        assert results[0]["price"] == 42.50
        assert results[0]["currency"] == "EUR"
        assert results[0]["rarity"] == "Ultra Rare"

    @pytest.mark.asyncio
    async def test_health_check_unconfigured(self, unconfigured_caller):
        result = await unconfigured_caller.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_sold_comps_marks_as_sold(self, caller):
        with patch.object(caller, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [{"source": "cardmarket", "is_sold": False}]
            results = await caller.sold_comps("charizard", "pokemon")
            assert results[0]["is_sold"] is True


# ---------------------------------------------------------------------------
# Discogs
# ---------------------------------------------------------------------------

class TestDiscogsCaller:
    """Tests for the Discogs API caller."""

    @pytest.fixture
    def caller(self):
        from app.agents.adapters.discogs_caller import DiscogsCaller
        return DiscogsCaller(personal_token="test_token")

    @pytest.fixture
    def unconfigured(self):
        from app.agents.adapters.discogs_caller import DiscogsCaller
        return DiscogsCaller(personal_token="")

    def test_configured(self, caller):
        assert caller.configured is True

    def test_unconfigured(self, unconfigured):
        assert unconfigured.configured is False

    @pytest.mark.asyncio
    async def test_search_unconfigured_returns_empty(self, unconfigured):
        result = await unconfigured.search("akira ost")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_success(self, caller):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {
                    "id": 9876,
                    "title": "Geinoh Yamashirogumi - Akira OST",
                    "year": 2017,
                    "country": "JP",
                    "format": ["Vinyl", "LP"],
                    "thumb": "https://example.com/thumb.jpg",
                    "uri": "https://www.discogs.com/release/9876",
                    "lowest_price": 45.00,
                    "community": {"have": 500, "want": 1200},
                }
            ]
        }

        with patch.object(caller, "_client") as mock_client:
            client_mock = AsyncMock()
            client_mock.get = AsyncMock(return_value=mock_resp)
            mock_client.return_value = client_mock

            results = await caller.search("akira ost", "anime_ost_vinyl")

        assert len(results) == 1
        assert results[0]["source"] == "discogs"
        assert results[0]["price"] == 45.00
        assert results[0]["year"] == "2017"
        assert results[0]["want"] == 1200

    @pytest.mark.asyncio
    async def test_health_check_unconfigured(self, unconfigured):
        assert await unconfigured.health_check() is False


# ---------------------------------------------------------------------------
# PriceCharting
# ---------------------------------------------------------------------------

class TestPriceChartingCaller:
    """Tests for the PriceCharting API caller."""

    @pytest.fixture
    def caller(self):
        from app.agents.adapters.pricecharting_caller import PriceChartingCaller
        return PriceChartingCaller(api_key="test_key")

    @pytest.fixture
    def unconfigured(self):
        from app.agents.adapters.pricecharting_caller import PriceChartingCaller
        return PriceChartingCaller(api_key="")

    def test_configured(self, caller):
        assert caller.configured is True

    @pytest.mark.asyncio
    async def test_search_unconfigured_returns_empty(self, unconfigured):
        result = await unconfigured.search("super mario world")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_success(self, caller):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "products": [
                {
                    "id": "54321",
                    "product-name": "Super Mario World",
                    "console-name": "Super Nintendo",
                    "loose-price": 2500,   # $25.00
                    "cib-price": 7500,     # $75.00
                    "new-price": 35000,    # $350.00
                    "graded-price": 100000,
                }
            ]
        }

        with patch.object(caller, "_client") as mock_client:
            client_mock = AsyncMock()
            client_mock.get = AsyncMock(return_value=mock_resp)
            mock_client.return_value = client_mock

            results = await caller.search("super mario world", "retro_games")

        assert len(results) == 1
        assert results[0]["source"] == "pricecharting"
        assert results[0]["price"] == 75.00  # CIB price
        assert results[0]["price_loose"] == 25.00
        assert results[0]["price_new"] == 350.00
        assert "Super Nintendo" in results[0]["title"]

    @pytest.mark.asyncio
    async def test_lookup_unconfigured(self, unconfigured):
        result = await unconfigured.lookup("12345")
        assert result is None


# ---------------------------------------------------------------------------
# StockX
# ---------------------------------------------------------------------------

class TestStockXCaller:
    """Tests for the StockX API caller."""

    @pytest.fixture
    def caller(self):
        from app.agents.adapters.stockx_caller import StockXCaller
        return StockXCaller(api_key="test_key")

    @pytest.fixture
    def unconfigured(self):
        from app.agents.adapters.stockx_caller import StockXCaller
        return StockXCaller(api_key="")

    def test_configured(self, caller):
        assert caller.configured is True

    @pytest.mark.asyncio
    async def test_search_unconfigured_returns_empty(self, unconfigured):
        result = await unconfigured.search("kaws companion")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_success(self, caller):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "products": [
                {
                    "id": "abc123",
                    "title": "KAWS Companion (Black)",
                    "urlKey": "kaws-companion-black",
                    "media": {"thumbUrl": "https://example.com/thumb.jpg"},
                    "market": {
                        "lastSale": 450.00,
                        "lowestAsk": 500.00,
                        "highestBid": 400.00,
                    },
                    "attributes": {"retailPrice": 250, "brand": "KAWS"},
                }
            ]
        }

        with patch.object(caller, "_client") as mock_client:
            client_mock = AsyncMock()
            client_mock.get = AsyncMock(return_value=mock_resp)
            mock_client.return_value = client_mock

            results = await caller.search("kaws companion", "designer_toys")

        assert len(results) == 1
        assert results[0]["source"] == "stockx"
        assert results[0]["price"] == 450.00
        assert results[0]["last_sale"] == 450.00
        assert results[0]["lowest_ask"] == 500.00
        assert results[0]["brand"] == "KAWS"

    @pytest.mark.asyncio
    async def test_sold_comps_filters_to_sold(self, caller):
        with patch.object(caller, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [
                {"source": "stockx", "is_sold": False, "last_sale": 100, "price": 120, "source_price": 120},
                {"source": "stockx", "is_sold": False, "last_sale": None, "price": 0, "source_price": 0},
            ]
            results = await caller.sold_comps("kaws", "designer_toys")
            assert len(results) == 1
            assert results[0]["is_sold"] is True
            assert results[0]["price"] == 100


# ---------------------------------------------------------------------------
# BrickLink
# ---------------------------------------------------------------------------

class TestBrickLinkCaller:
    """Tests for the BrickLink API caller."""

    @pytest.fixture
    def caller(self):
        from app.agents.adapters.bricklink_caller import BrickLinkCaller
        return BrickLinkCaller(
            consumer_key="ck", consumer_secret="cs",
            token="tk", token_secret="ts",
        )

    @pytest.fixture
    def unconfigured(self):
        from app.agents.adapters.bricklink_caller import BrickLinkCaller
        return BrickLinkCaller(consumer_key="", consumer_secret="", token="", token_secret="")

    def test_configured(self, caller):
        assert caller.configured is True

    def test_unconfigured(self, unconfigured):
        assert unconfigured.configured is False

    @pytest.mark.asyncio
    async def test_search_unconfigured_returns_empty(self, unconfigured):
        result = await unconfigured.search("75192")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_set_number(self, caller):
        """Test that numeric query triggers direct set lookup."""
        item_data = {
            "no": "75192",
            "name": "Millennium Falcon",
            "type": "SET",
            "year_released": 2017,
        }
        price_data = {
            "avg_price": "399.99",
            "min_price": "350.00",
            "max_price": "450.00",
            "total_quantity": 42,
            "currency_code": "USD",
        }

        with patch.object(caller, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [item_data, price_data]
            results = await caller.search("75192", "lego")

        assert len(results) == 1
        assert results[0]["source"] == "bricklink"
        assert "75192" in results[0]["title"]
        assert "Millennium Falcon" in results[0]["title"]
        assert results[0]["price"] == 399.99

    @pytest.mark.asyncio
    async def test_search_text_returns_empty(self, caller):
        """BrickLink API doesn't support text search — should return empty."""
        results = await caller.search("millennium falcon", "lego")
        assert results == []

    @pytest.mark.asyncio
    async def test_health_check_unconfigured(self, unconfigured):
        assert await unconfigured.health_check() is False

    @pytest.mark.asyncio
    async def test_get_price_guide_unconfigured(self, unconfigured):
        result = await unconfigured.get_price_guide("75192")
        assert result is None


# ---------------------------------------------------------------------------
# Yahoo Auctions JP
# ---------------------------------------------------------------------------

class TestYahooAuctionsCaller:
    """Tests for the Yahoo Auctions JP caller."""

    @pytest.fixture
    def caller(self):
        from app.agents.adapters.yahoo_auctions_caller import YahooAuctionsCaller
        return YahooAuctionsCaller(enabled=True)

    @pytest.fixture
    def disabled(self):
        from app.agents.adapters.yahoo_auctions_caller import YahooAuctionsCaller
        return YahooAuctionsCaller(enabled=False)

    def test_configured(self, caller):
        assert caller.configured is True

    def test_disabled(self, disabled):
        assert disabled.configured is False

    @pytest.mark.asyncio
    async def test_search_disabled_returns_empty(self, disabled):
        result = await disabled.search("ガンダム")
        assert result == []

    @pytest.mark.asyncio
    async def test_health_check_disabled(self, disabled):
        assert await disabled.health_check() is False

    def test_extract_jpy_price(self):
        from app.agents.adapters.yahoo_auctions_caller import _extract_jpy_price
        assert _extract_jpy_price("¥12,500") == 12500.0
        assert _extract_jpy_price("3,200円") == 3200.0
        assert _extract_jpy_price("Price: 45000") == 45000.0
        assert _extract_jpy_price("no price") is None

    def test_normalize_listing(self):
        from app.agents.adapters.yahoo_auctions_caller import _normalize_listing
        item = {
            "id": "abc123",
            "title": "MG Wing Gundam Ver.Ka",
            "price": 5500,
            "image": "https://img.example.com/thumb.jpg",
        }
        result = _normalize_listing(item)
        assert result["source"] == "yahoo_auctions_jp"
        assert result["raw_id"] == "yahoo-jp-abc123"
        assert result["price_jpy"] == 5500.0
        assert result["source_currency"] == "JPY"
        assert result["price"] > 0  # Converted to EUR

    def test_supported_categories(self):
        from app.agents.adapters.yahoo_auctions_caller import SUPPORTED_CATEGORIES
        assert "bandai_premium" in SUPPORTED_CATEGORIES
        assert "jp_event" in SUPPORTED_CATEGORIES
        assert "ghibli" in SUPPORTED_CATEGORIES
        assert "anime_figures" in SUPPORTED_CATEGORIES
        assert "gunpla" in SUPPORTED_CATEGORIES
        assert "vtuber" in SUPPORTED_CATEGORIES

    @pytest.mark.asyncio
    async def test_sold_comps_disabled(self, disabled):
        result = await disabled.sold_comps("test")
        assert result == []


# ---------------------------------------------------------------------------
# Cross-adapter coverage
# ---------------------------------------------------------------------------

class TestAdapterCoverage:
    """Verify all new adapters cover the right categories."""

    def test_cardmarket_covers_tcgs(self):
        from app.agents.adapters.cardmarket_caller import SUPPORTED_CATEGORIES
        assert "pokemon" in SUPPORTED_CATEGORIES
        assert "mtg" in SUPPORTED_CATEGORIES
        assert "yugioh" in SUPPORTED_CATEGORIES
        assert "lorcana" in SUPPORTED_CATEGORIES

    def test_discogs_covers_music(self):
        from app.agents.adapters.discogs_caller import SUPPORTED_CATEGORIES
        assert "anime_ost_vinyl" in SUPPORTED_CATEGORIES
        assert "anime_soundtrack" in SUPPORTED_CATEGORIES
        assert "kpop_merch" in SUPPORTED_CATEGORIES

    def test_pricecharting_covers_retro(self):
        from app.agents.adapters.pricecharting_caller import SUPPORTED_CATEGORIES
        assert "retro_games" in SUPPORTED_CATEGORIES
        assert "retro_handhelds" in SUPPORTED_CATEGORIES

    def test_stockx_covers_design_toys(self):
        from app.agents.adapters.stockx_caller import SUPPORTED_CATEGORIES
        assert "designer_toys" in SUPPORTED_CATEGORIES
        assert "funko" in SUPPORTED_CATEGORIES

    def test_bricklink_covers_lego(self):
        from app.agents.adapters.bricklink_caller import SUPPORTED_CATEGORIES
        assert "lego" in SUPPORTED_CATEGORIES

    def test_yahoo_covers_jp_exclusives(self):
        from app.agents.adapters.yahoo_auctions_caller import SUPPORTED_CATEGORIES
        assert "bandai_premium" in SUPPORTED_CATEGORIES
        assert "jp_event" in SUPPORTED_CATEGORIES
        assert "jp_magazine" in SUPPORTED_CATEGORIES
        assert "ghibli" in SUPPORTED_CATEGORIES
