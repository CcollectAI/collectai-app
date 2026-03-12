"""Tests for backend hardening (B1/B2/B4).

B1: Rate limit 429 on quickscan-advanced
B2: Circuit breaker skip for reprompt validation
B4: Batch dedup in price_monitor
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


# ── B1: quickscan-advanced now requires auth ────────────────────────────────


def test_quickscan_advanced_has_auth_dependency():
    """quickscan_advanced endpoints should depend on get_current_user_id."""
    from app.features.quickscan_advanced_router import quickscan_single, quickscan_batch
    import inspect

    single_sig = inspect.signature(quickscan_single)
    batch_sig = inspect.signature(quickscan_batch)

    # Both should have _user parameter (auth dependency)
    assert "_user" in single_sig.parameters, "quickscan_single missing _user auth dep"
    assert "_user" in batch_sig.parameters, "quickscan_batch missing _user auth dep"

    # Both should have _rl parameter (rate limit dependency)
    assert "_rl" in single_sig.parameters, "quickscan_single missing _rl rate limit dep"
    assert "_rl" in batch_sig.parameters, "quickscan_batch missing _rl rate limit dep"


# ── B2: reprompt validation with circuit breaker ─────────────────────────────


@pytest.mark.asyncio
async def test_reprompt_skips_when_circuit_open():
    """Reprompt validation should return None when OpenAI circuit is OPEN."""
    from workers.circuit_breaker import CircuitOpenError

    with patch("app.config.OPENAI_API_KEY", "sk-test"), \
         patch("app.agents.intake_agent.OPENAI_API_KEY", "sk-test"), \
         patch("workers.circuit_breaker.openai_circuit") as mock_circuit:
        mock_circuit.check.side_effect = CircuitOpenError("openai", 60)

        from app.agents.intake_agent import _validate_with_reprompt

        result = await _validate_with_reprompt(
            image_bytes=b"\x89PNG\r\n\x1a\nfake",
            initial_name="Test Item",
            initial_category="pokemon",
            catalog_candidates=[
                {"title": "Charizard", "item_key": "charizard-base"},
            ],
        )

        assert result is None
        mock_circuit.check.assert_called_once()


@pytest.mark.asyncio
async def test_reprompt_records_failure_on_error():
    """Reprompt validation should record_failure on the circuit breaker on errors."""
    with patch("app.config.OPENAI_API_KEY", "sk-test"), \
         patch("app.agents.intake_agent.OPENAI_API_KEY", "sk-test"), \
         patch("workers.circuit_breaker.openai_circuit") as mock_circuit:
        mock_circuit.check.return_value = None

        # Patch httpx to raise
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("connection timeout")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            from app.agents.intake_agent import _validate_with_reprompt

            result = await _validate_with_reprompt(
                image_bytes=b"\x89PNG\r\n\x1a\nfake",
                initial_name="Test Item",
                initial_category="pokemon",
                catalog_candidates=[
                    {"title": "Pikachu", "item_key": "pikachu-base"},
                ],
            )

            assert result is None
            mock_circuit.record_failure.assert_called_once()


# ── B4: price_monitor batch dedup ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_price_monitor_batch_alert_dedup():
    """check_threshold_alerts should batch-fetch fired alerts instead of N+1."""
    conn = AsyncMock()

    # Two active alerts
    conn.fetch.side_effect = [
        # First call: active alerts query
        [
            {"alert_id": "a1", "user_id": "u1", "item_id": "i1", "category": "funko", "threshold_value": 50.0},
            {"alert_id": "a2", "user_id": "u2", "item_id": "i2", "category": "pokemon", "threshold_value": 30.0},
        ],
        # Second call: batch dedup query — a1 already fired
        [
            {"alert_id": "a1"},
        ],
    ]

    # Price predictions for item i2 (a1 is deduped)
    conn.fetchrow.return_value = {
        "q50": 25.0,  # Below threshold of 30
        "q10": 20.0,
        "q90": 35.0,
    }

    conn.execute.return_value = None

    from workers.price_monitor_worker import check_threshold_alerts

    fired = await check_threshold_alerts(conn)

    # Only a2 should fire (a1 deduped)
    assert fired == 1

    # Verify the batch dedup query was used (second fetch call)
    dedup_call = conn.fetch.call_args_list[1]
    assert "alert_id = ANY($1)" in dedup_call[0][0]

    # Verify the alert was inserted
    insert_calls = [
        c for c in conn.execute.call_args_list
        if "alert_trigger_history" in str(c)
    ]
    assert len(insert_calls) == 1
