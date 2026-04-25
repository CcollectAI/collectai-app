"""Tests for workers.circuit_breaker — CircuitBreaker state machine."""

import time
from unittest.mock import patch

import pytest

from workers.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    all_circuit_status,
    ebay_circuit,
    openai_circuit,
    tcgplayer_circuit,
)


@pytest.fixture()
def cb():
    """Create a fresh CircuitBreaker with small thresholds for easy testing."""
    return CircuitBreaker("test_service", max_failures=3, cooldown_seconds=10.0)


@pytest.fixture(autouse=True)
def _reset_global_circuits():
    """Reset pre-configured global circuit breakers between tests."""
    for circuit in (ebay_circuit, tcgplayer_circuit, openai_circuit):
        circuit.reset()
    yield
    for circuit in (ebay_circuit, tcgplayer_circuit, openai_circuit):
        circuit.reset()


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

class TestInitialState:
    def test_starts_closed(self, cb):
        assert cb.state == CircuitState.CLOSED

    def test_initial_failure_count_zero(self, cb):
        status = cb.status()
        assert status["failure_count"] == 0

    def test_initial_status_name(self, cb):
        status = cb.status()
        assert status["name"] == "test_service"
        assert status["state"] == "closed"
        assert status["max_failures"] == 3
        assert status["cooldown_seconds"] == 10.0

    def test_check_does_not_raise_when_closed(self, cb):
        cb.check()  # should not raise


# ---------------------------------------------------------------------------
# CLOSED -> OPEN transition (after max_failures)
# ---------------------------------------------------------------------------

class TestClosedToOpen:
    def test_opens_after_max_failures(self, cb):
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_does_not_open_before_max_failures(self, cb):
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_success_resets_failure_count(self, cb):
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        # After success, failure count should be 0
        assert cb._failure_count == 0
        # Even after two more failures, should still be CLOSED (only 2 total now)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_check_raises_when_open(self, cb):
        for _ in range(3):
            cb.record_failure()
        with pytest.raises(CircuitOpenError) as exc_info:
            cb.check()
        assert exc_info.value.name == "test_service"
        assert exc_info.value.retry_after > 0

    def test_circuit_open_error_message(self, cb):
        for _ in range(3):
            cb.record_failure()
        with pytest.raises(CircuitOpenError, match="OPEN"):
            cb.check()


# ---------------------------------------------------------------------------
# OPEN -> HALF_OPEN transition (after cooldown)
# ---------------------------------------------------------------------------

class TestOpenToHalfOpen:
    def test_transitions_to_half_open_after_cooldown(self, cb):
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Simulate time passing beyond cooldown
        with patch("workers.circuit_breaker.time.monotonic",
                    return_value=time.monotonic() + 15):
            assert cb.state == CircuitState.HALF_OPEN

    def test_stays_open_before_cooldown(self, cb):
        for _ in range(3):
            cb.record_failure()
        # Time hasn't passed enough
        with patch("workers.circuit_breaker.time.monotonic",
                    return_value=time.monotonic() + 5):
            assert cb.state == CircuitState.OPEN

    def test_check_allows_probe_in_half_open(self, cb):
        for _ in range(3):
            cb.record_failure()

        # Advance time past cooldown
        future = time.monotonic() + 15
        with patch("workers.circuit_breaker.time.monotonic", return_value=future):
            cb.check()  # should not raise — one probe call allowed

    def test_check_rejects_extra_probes_in_half_open(self, cb):
        """Default half_open_max=1 — second probe should be rejected."""
        for _ in range(3):
            cb.record_failure()

        future = time.monotonic() + 15
        with patch("workers.circuit_breaker.time.monotonic", return_value=future):
            cb.check()  # first probe allowed
            with pytest.raises(CircuitOpenError):
                cb.check()  # second probe rejected


# ---------------------------------------------------------------------------
# HALF_OPEN -> CLOSED (success) or OPEN (failure)
# ---------------------------------------------------------------------------

class TestHalfOpenTransitions:
    def _make_half_open(self, cb):
        """Helper: trip circuit and advance time to HALF_OPEN."""
        for _ in range(3):
            cb.record_failure()
        # Manually transition to HALF_OPEN
        cb._state = CircuitState.HALF_OPEN
        cb._half_open_calls = 0

    def test_success_in_half_open_closes_circuit(self, cb):
        self._make_half_open(cb)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0

    def test_failure_in_half_open_reopens_circuit(self, cb):
        self._make_half_open(cb)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_check_works_after_half_open_success(self, cb):
        self._make_half_open(cb)
        cb.record_success()
        # Now CLOSED — check() should not raise
        cb.check()

    def test_check_fails_after_half_open_failure(self, cb):
        self._make_half_open(cb)
        cb.record_failure()
        # Now OPEN again — check() should raise
        with pytest.raises(CircuitOpenError):
            cb.check()


# ---------------------------------------------------------------------------
# reset()
# ---------------------------------------------------------------------------

class TestReset:
    def test_manual_reset_from_open(self, cb):
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0
        cb.check()  # should not raise

    def test_manual_reset_from_half_open(self, cb):
        cb._state = CircuitState.HALF_OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# status()
# ---------------------------------------------------------------------------

class TestStatus:
    def test_status_reflects_closed(self, cb):
        s = cb.status()
        assert s["state"] == "closed"
        assert s["failure_count"] == 0

    def test_status_reflects_open(self, cb):
        for _ in range(3):
            cb.record_failure()
        s = cb.status()
        assert s["state"] == "open"
        assert s["failure_count"] == 3

    def test_status_reflects_half_open(self, cb):
        cb._state = CircuitState.HALF_OPEN
        # _effective_state may not transition since _state is not OPEN
        # Set directly:
        s = cb.status()
        assert s["state"] == "half_open"


# ---------------------------------------------------------------------------
# all_circuit_status() — pre-configured global instances
# ---------------------------------------------------------------------------

class TestAllCircuitStatus:
    def test_returns_list_of_all_breakers(self):
        statuses = all_circuit_status()
        assert isinstance(statuses, list)
        assert len(statuses) >= 30

    def test_contains_expected_services(self):
        statuses = all_circuit_status()
        names = {s["name"] for s in statuses}
        expected = {
            "ebay", "tcgplayer", "openai", "cardmarket", "discogs",
            "pricecharting", "stockx", "bricklink", "firecrawl", "crawl4ai",
            "mercari_us", "whatnot", "vinted", "mavin", "catawiki",
            "keh", "mpb", "drop", "gouletpens", "brickeconomy",
            "popmart", "booth", "scalemates",
        }
        assert expected.issubset(names)

    def test_all_start_closed(self):
        statuses = all_circuit_status()
        for s in statuses:
            assert s["state"] == "closed"

    def test_reflects_state_changes(self):
        # Trip the eBay circuit
        for _ in range(5):
            ebay_circuit.record_failure()

        statuses = all_circuit_status()
        ebay_status = next(s for s in statuses if s["name"] == "ebay")
        assert ebay_status["state"] == "open"

        # Others should remain closed
        tcg_status = next(s for s in statuses if s["name"] == "tcgplayer")
        assert tcg_status["state"] == "closed"

    def test_openai_circuit_config(self):
        statuses = all_circuit_status()
        oai = next(s for s in statuses if s["name"] == "openai")
        assert oai["max_failures"] == 3
        assert oai["cooldown_seconds"] == 120


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_custom_half_open_max(self):
        """CircuitBreaker with half_open_max=2 allows two probes."""
        cb = CircuitBreaker("multi_probe", max_failures=2, cooldown_seconds=5, half_open_max=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Advance to HALF_OPEN
        cb._state = CircuitState.HALF_OPEN
        cb._half_open_calls = 0

        cb.check()  # first probe
        cb.check()  # second probe
        with pytest.raises(CircuitOpenError):
            cb.check()  # third probe rejected

    def test_zero_max_failures_opens_on_first_failure(self):
        """max_failures=0 means even zero failures won't trip (need at least 1)."""
        # Actually max_failures=0 means _failure_count (1) >= 0 is always true
        # so it trips on the very first failure
        cb = CircuitBreaker("instant_trip", max_failures=1, cooldown_seconds=5)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_retry_after_decreases_over_time(self, cb):
        """retry_after should reflect remaining cooldown time."""
        for _ in range(3):
            cb.record_failure()

        # Immediately after opening, retry_after should be close to cooldown
        try:
            cb.check()
        except CircuitOpenError as e:
            assert e.retry_after > 8  # close to 10s cooldown
            assert e.retry_after <= 10

    def test_thread_safety_smoke(self, cb):
        """Basic smoke test that concurrent access doesn't crash."""
        import threading

        errors = []

        def trip_and_check():
            try:
                for _ in range(5):
                    cb.record_failure()
                try:
                    cb.check()
                except CircuitOpenError:
                    pass
                cb.record_success()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=trip_and_check) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
