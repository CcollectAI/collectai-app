"""
Simple in-memory circuit breaker for external API calls.

Usage:
    from workers.circuit_breaker import CircuitBreaker

    ebay_cb = CircuitBreaker("ebay", max_failures=5, cooldown_seconds=60)

    async def call_ebay(query):
        ebay_cb.check()  # raises CircuitOpenError if tripped
        try:
            result = await _do_ebay_call(query)
            ebay_cb.record_success()
            return result
        except Exception as exc:
            ebay_cb.record_failure()
            raise
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from threading import Lock

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open and calls should not be attempted."""

    def __init__(self, name: str, retry_after: float):
        self.name = name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit '{name}' is OPEN — retry after {retry_after:.0f}s"
        )


class CircuitBreaker:
    """Thread-safe circuit breaker with three states.

    CLOSED  → normal operation; failures increment counter
    OPEN    → all calls rejected; transitions to HALF_OPEN after cooldown
    HALF_OPEN → allows one probe call; success → CLOSED, failure → OPEN

    Lock choice: ``threading.Lock`` vs ``asyncio.Lock``
    ---------------------------------------------------
    This class uses ``threading.Lock`` intentionally, even though it is used
    from async code.  The critical sections inside each ``with self._lock``
    block are **sub-microsecond CPU-bound attribute reads/writes** that never
    ``await``.  Because no suspension points exist inside the lock,
    ``asyncio.Lock`` would add unnecessary coroutine overhead without any
    benefit.  ``threading.Lock`` is the correct primitive here: it is
    re-entrant-safe under the GIL, protects compound check-and-update
    operations (e.g. ``check()`` reading state then mutating
    ``_half_open_calls``), and works correctly if the breaker is ever shared
    across threads (e.g. in a threaded test runner or a mixed sync/async
    context).
    """

    def __init__(
        self,
        name: str,
        max_failures: int = 5,
        cooldown_seconds: float = 60.0,
        half_open_max: int = 1,
    ):
        self.name = name
        self.max_failures = max_failures
        self.cooldown_seconds = cooldown_seconds
        self.half_open_max = half_open_max

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
        self._last_failure_time: float = 0.0
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._effective_state()

    def _effective_state(self) -> CircuitState:
        """Compute effective state (may transition OPEN → HALF_OPEN on cooldown expiry)."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.cooldown_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                logger.info("Circuit '%s' transitioned OPEN → HALF_OPEN", self.name)
        return self._state

    def check(self) -> None:
        """Call before making an external request. Raises CircuitOpenError if open."""
        with self._lock:
            state = self._effective_state()
            if state == CircuitState.OPEN:
                retry_after = self.cooldown_seconds - (
                    time.monotonic() - self._last_failure_time
                )
                raise CircuitOpenError(self.name, max(retry_after, 0))
            if state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max:
                    raise CircuitOpenError(self.name, self.cooldown_seconds)
                self._half_open_calls += 1

    def record_success(self) -> None:
        """Call after a successful external request."""
        with self._lock:
            if self._state in (CircuitState.HALF_OPEN, CircuitState.CLOSED):
                if self._state == CircuitState.HALF_OPEN:
                    logger.info("Circuit '%s' recovered → CLOSED", self.name)
                self._state = CircuitState.CLOSED
                self._failure_count = 0

    def record_failure(self) -> None:
        """Call after a failed external request."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit '%s' probe failed → OPEN (cooldown %.0fs)",
                    self.name,
                    self.cooldown_seconds,
                )
            elif self._failure_count >= self.max_failures:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit '%s' tripped after %d failures → OPEN (cooldown %.0fs)",
                    self.name,
                    self._failure_count,
                    self.cooldown_seconds,
                )

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._half_open_calls = 0
            logger.info("Circuit '%s' manually reset → CLOSED", self.name)

    def status(self) -> dict:
        """Return current status for monitoring/ops endpoints."""
        with self._lock:
            return {
                "name": self.name,
                "state": self._effective_state().value,
                "failure_count": self._failure_count,
                "max_failures": self.max_failures,
                "cooldown_seconds": self.cooldown_seconds,
            }


# ---------------------------------------------------------------------------
# Pre-configured instances for external services
# ---------------------------------------------------------------------------

ebay_circuit = CircuitBreaker("ebay", max_failures=5, cooldown_seconds=60)
tcgplayer_circuit = CircuitBreaker("tcgplayer", max_failures=5, cooldown_seconds=60)
openai_circuit = CircuitBreaker("openai", max_failures=3, cooldown_seconds=120)
cardmarket_circuit = CircuitBreaker("cardmarket", max_failures=5, cooldown_seconds=60)
discogs_circuit = CircuitBreaker("discogs", max_failures=5, cooldown_seconds=60)
pricecharting_circuit = CircuitBreaker("pricecharting", max_failures=5, cooldown_seconds=60)
stockx_circuit = CircuitBreaker("stockx", max_failures=5, cooldown_seconds=60)
bricklink_circuit = CircuitBreaker("bricklink", max_failures=5, cooldown_seconds=60)
firecrawl_circuit = CircuitBreaker("firecrawl", max_failures=5, cooldown_seconds=120)
crawl4ai_circuit = CircuitBreaker("crawl4ai", max_failures=5, cooldown_seconds=120)
mercari_us_circuit = CircuitBreaker("mercari_us", max_failures=5, cooldown_seconds=60)
whatnot_circuit = CircuitBreaker("whatnot", max_failures=5, cooldown_seconds=60)
vinted_circuit = CircuitBreaker("vinted", max_failures=5, cooldown_seconds=60)
mavin_circuit = CircuitBreaker("mavin", max_failures=5, cooldown_seconds=60)
catawiki_circuit = CircuitBreaker("catawiki", max_failures=5, cooldown_seconds=60)
whisky_auctioneer_circuit = CircuitBreaker("whisky_auctioneer", max_failures=5, cooldown_seconds=60)
mandarake_circuit = CircuitBreaker("mandarake", max_failures=5, cooldown_seconds=60)
bezel_circuit = CircuitBreaker("bezel", max_failures=5, cooldown_seconds=60)
chrono24_circuit = CircuitBreaker("chrono24", max_failures=5, cooldown_seconds=60)
keh_circuit = CircuitBreaker("keh", max_failures=5, cooldown_seconds=60)
mpb_circuit = CircuitBreaker("mpb", max_failures=5, cooldown_seconds=60)
drop_circuit = CircuitBreaker("drop", max_failures=5, cooldown_seconds=60)
gouletpens_circuit = CircuitBreaker("gouletpens", max_failures=5, cooldown_seconds=60)
brickeconomy_circuit = CircuitBreaker("brickeconomy", max_failures=5, cooldown_seconds=60)
popmart_circuit = CircuitBreaker("popmart", max_failures=5, cooldown_seconds=60)
booth_circuit = CircuitBreaker("booth", max_failures=5, cooldown_seconds=60)
scalemates_circuit = CircuitBreaker("scalemates", max_failures=5, cooldown_seconds=60)
ktown4u_circuit = CircuitBreaker("ktown4u", max_failures=5, cooldown_seconds=60)
comicbookrealm_circuit = CircuitBreaker("comicbookrealm", max_failures=5, cooldown_seconds=60)
masterofmalt_circuit = CircuitBreaker("masterofmalt", max_failures=5, cooldown_seconds=60)
yahoo_auctions_circuit = CircuitBreaker("yahoo_auctions", max_failures=5, cooldown_seconds=60)


def all_circuit_status() -> list[dict]:
    """Return status of all circuit breakers for ops monitoring."""
    return [
        cb.status()
        for cb in (
            ebay_circuit, tcgplayer_circuit, openai_circuit,
            cardmarket_circuit, discogs_circuit, pricecharting_circuit,
            stockx_circuit, bricklink_circuit, firecrawl_circuit,
            crawl4ai_circuit, mercari_us_circuit, whatnot_circuit,
            vinted_circuit, mavin_circuit, catawiki_circuit,
            whisky_auctioneer_circuit, mandarake_circuit,
            bezel_circuit, chrono24_circuit,
            keh_circuit, mpb_circuit,
            drop_circuit, gouletpens_circuit, brickeconomy_circuit,
            popmart_circuit, booth_circuit, scalemates_circuit,
            ktown4u_circuit, comicbookrealm_circuit, masterofmalt_circuit,
            yahoo_auctions_circuit,
        )
    ]
