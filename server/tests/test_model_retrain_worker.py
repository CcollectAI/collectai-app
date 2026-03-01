"""
Tests for workers/model_retrain_worker.py — Model Retrain Worker.

Covers:
  - _price_to_features() heuristic scoring
  - _export_market_hits_to_jsonl() with mocked DB
  - _retrain_category() with insufficient samples
  - run_once() end-to-end with mocked DB
  - No DSN error handling
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DB_DSN", "mock://localhost")


class TestPriceToFeatures:
    """Tests for _price_to_features()."""

    def test_mint_condition(self):
        from workers.model_retrain_worker import _price_to_features

        features = _price_to_features(100.0, "Mint", True)
        assert features["condition_score"] == 0.95

    def test_near_mint_condition(self):
        from workers.model_retrain_worker import _price_to_features

        features = _price_to_features(50.0, "Near Mint", False)
        assert features["condition_score"] == 0.85

    def test_good_condition(self):
        from workers.model_retrain_worker import _price_to_features

        features = _price_to_features(30.0, "Good", True)
        assert features["condition_score"] == 0.70

    def test_poor_condition(self):
        from workers.model_retrain_worker import _price_to_features

        features = _price_to_features(10.0, "Poor", False)
        assert features["condition_score"] == 0.20

    def test_unknown_condition_defaults_good(self):
        from workers.model_retrain_worker import _price_to_features

        features = _price_to_features(50.0, None, True)
        assert features["condition_score"] == 0.70

    def test_empty_string_condition(self):
        from workers.model_retrain_worker import _price_to_features

        features = _price_to_features(50.0, "", False)
        assert features["condition_score"] == 0.70

    def test_all_features_present(self):
        from workers.model_retrain_worker import _price_to_features

        features = _price_to_features(100.0, "Sealed", True)
        assert "condition_score" in features
        assert "rarity_score" in features
        assert "edition_score" in features
        assert features["rarity_score"] == 0.50
        assert features["edition_score"] == 0.50


class TestRetrainCategory:
    """Tests for _retrain_category() with file-based logic."""

    def test_insufficient_samples_skips(self):
        from workers.model_retrain_worker import _retrain_category

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("workers.model_retrain_worker.DATA_DIR", Path(tmpdir)):
                with patch("workers.model_retrain_worker.MIN_SAMPLES", 20):
                    # No data files exist → 0 samples
                    result = _retrain_category("pokemon")

        assert result["status"] == "skipped"
        assert result["samples"] == 0

    def test_enough_samples_attempts_train(self):
        from workers.model_retrain_worker import _retrain_category

        with tempfile.TemporaryDirectory() as tmpdir:
            cat_dir = Path(tmpdir) / "pokemon"
            cat_dir.mkdir()

            # Write 25 training records
            with open(cat_dir / "train.jsonl", "w") as f:
                for i in range(25):
                    record = {"features": {"condition_score": 0.8, "rarity_score": 0.5, "edition_score": 0.5}, "price": 50.0 + i}
                    f.write(json.dumps(record) + "\n")

            with patch("workers.model_retrain_worker.DATA_DIR", Path(tmpdir)):
                with patch("workers.model_retrain_worker.MIN_SAMPLES", 20):
                    # train_category won't exist, will use CLI fallback which also fails
                    # but we can patch it
                    with patch("pipelines.train_price.train_category", return_value={"cv_mae": 5.0, "version": "v3"}, create=True):
                        result = _retrain_category("pokemon")

        assert result["status"] == "ok"
        assert result["samples"] == 25

    def test_merges_multiple_jsonl_files(self):
        from workers.model_retrain_worker import _retrain_category

        with tempfile.TemporaryDirectory() as tmpdir:
            cat_dir = Path(tmpdir) / "lego"
            cat_dir.mkdir()

            # Static seed data
            with open(cat_dir / "train.jsonl", "w") as f:
                for i in range(10):
                    f.write(json.dumps({"features": {"condition_score": 0.8, "rarity_score": 0.5, "edition_score": 0.5}, "price": 100.0}) + "\n")

            # Live market data
            with open(cat_dir / "train_live.jsonl", "w") as f:
                for i in range(10):
                    f.write(json.dumps({"features": {"condition_score": 0.7, "rarity_score": 0.5, "edition_score": 0.5}, "price": 90.0}) + "\n")

            # Ground truth
            with open(cat_dir / "train_ground_truth.jsonl", "w") as f:
                for i in range(5):
                    f.write(json.dumps({"features": {"condition_score": 0.9, "rarity_score": 0.5, "edition_score": 0.5}, "price": 110.0}) + "\n")

            with patch("workers.model_retrain_worker.DATA_DIR", Path(tmpdir)):
                with patch("workers.model_retrain_worker.MIN_SAMPLES", 20):
                    with patch("pipelines.train_price.train_category", return_value={"cv_mae": 3.0, "version": "v3"}, create=True):
                        result = _retrain_category("lego")

        assert result["status"] == "ok"
        assert result["samples"] == 25  # 10 + 10 + 5


class TestRunOnce:
    """Tests for model_retrain_worker.run_once()."""

    @pytest.fixture
    def _mock_dsn(self):
        with patch("workers.model_retrain_worker.DSN", "mock://localhost"):
            yield

    @pytest.fixture
    def _mock_record_run(self):
        with patch("workers.model_retrain_worker.record_run") as mock_rr:
            yield mock_rr

    @pytest.fixture
    def _mock_connect(self):
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        conn.close = AsyncMock()
        with patch("workers.model_retrain_worker.asyncpg.connect", return_value=conn):
            yield conn

    @pytest.mark.asyncio
    async def test_no_dsn_records_error(self, _mock_record_run):
        """Worker records error if DB_DSN is not set."""
        with patch("workers.model_retrain_worker.DSN", None):
            from workers.model_retrain_worker import run_once
            await run_once()

        _mock_record_run.assert_called_with("model_retrain_worker", "error")

    @pytest.mark.asyncio
    async def test_run_once_completes(self, _mock_dsn, _mock_connect, _mock_record_run):
        """Full run_once with empty DB completes with ok status."""
        _mock_connect.fetch.return_value = []

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("workers.model_retrain_worker.DATA_DIR", Path(tmpdir)):
                from workers.model_retrain_worker import run_once
                await run_once()

        # All categories skipped (no data), but no errors → ok
        _mock_record_run.assert_called_with("model_retrain_worker", "ok")
