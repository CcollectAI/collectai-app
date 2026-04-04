"""
Monthly spend tracker with budget circuit breaker.

Tracks API call costs per provider and blocks calls when the monthly
budget is exceeded.  All state is in-memory (resets on restart) with
optional DB persistence for historical reporting.

Usage:
    from app.lib.spend_tracker import spend_tracker, BudgetExceededError

    # Before making an API call:
    spend_tracker.check("openai")  # raises BudgetExceededError if over budget

    # After a successful call:
    spend_tracker.record("openai", cost_eur=0.002)

    # Check current state:
    summary = spend_tracker.summary()
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    """Raised when monthly spend budget has been reached."""

    def __init__(self, provider: str, spent: float, budget: float):
        self.provider = provider
        self.spent = spent
        self.budget = budget
        super().__init__(
            f"Monthly budget exceeded: {spent:.2f}/{budget:.2f} EUR "
            f"(blocked call to '{provider}')"
        )


# ---------------------------------------------------------------------------
# Cost-per-call estimates (EUR) — conservative upper bounds
# ---------------------------------------------------------------------------
# These are defaults; actual cost is passed by the caller when known.

DEFAULT_COSTS: dict[str, float] = {
    "openai": 0.003,       # gpt-4o-mini vision: ~500 input + 200 output tokens
    "firecrawl": 0.006,    # Growth plan: ~€19/3000 credits
    "scrapedo": 0.001,     # ~€1/1000 requests
    "serpapi": 0.005,      # ~€50/10K searches
    "fal_clip": 0.002,     # FAL.ai CLIP embedding
    "posthog": 0.0,        # Free tier (1M events/mo)
    "sentry": 0.0,         # Free tier or flat monthly
}


class SpendTracker:
    """Thread-safe monthly spend tracker with budget enforcement."""

    def __init__(self, monthly_budget_eur: float = 150.0):
        self._budget = monthly_budget_eur
        self._lock = Lock()
        self._current_month: str = self._month_key()
        self._provider_spend: dict[str, float] = {}
        self._provider_calls: dict[str, int] = {}
        self._call_log: list[dict[str, Any]] = []  # last 100 calls for dashboard
        self._paused_providers: set[str] = set()  # manually paused
        self._budget_breached = False
        self._alerted_75 = False
        self._alerted_90 = False
        self._alerted_100 = False

    @staticmethod
    def _month_key() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def _maybe_reset_month(self) -> None:
        """Reset counters if we've rolled into a new month."""
        key = self._month_key()
        if key != self._current_month:
            logger.info(
                "Spend tracker month rollover %s -> %s (was %.2f EUR)",
                self._current_month, key, self.total_spent,
            )
            self._current_month = key
            self._provider_spend.clear()
            self._provider_calls.clear()
            self._call_log.clear()
            self._budget_breached = False
            self._alerted_75 = False
            self._alerted_90 = False
            self._alerted_100 = False

    @property
    def total_spent(self) -> float:
        return sum(self._provider_spend.values())

    @property
    def budget(self) -> float:
        return self._budget

    @property
    def remaining(self) -> float:
        return max(0.0, self._budget - self.total_spent)

    @property
    def pct_used(self) -> float:
        if self._budget <= 0:
            return 100.0
        return min(100.0, (self.total_spent / self._budget) * 100)

    def set_budget(self, eur: float) -> None:
        """Update the monthly budget cap."""
        with self._lock:
            self._budget = max(0.0, eur)
            self._budget_breached = self.total_spent >= self._budget
            logger.info("Spend budget updated to %.2f EUR", self._budget)

    def pause_provider(self, provider: str) -> None:
        """Manually pause a provider (blocks all calls)."""
        with self._lock:
            self._paused_providers.add(provider)
            logger.info("Provider '%s' manually paused", provider)

    def resume_provider(self, provider: str) -> None:
        """Resume a manually paused provider."""
        with self._lock:
            self._paused_providers.discard(provider)
            logger.info("Provider '%s' resumed", provider)

    def check(self, provider: str) -> None:
        """Check if a call to this provider is allowed. Raises BudgetExceededError."""
        with self._lock:
            self._maybe_reset_month()

            if provider in self._paused_providers:
                raise BudgetExceededError(
                    provider, self.total_spent, self._budget
                )

            if self.total_spent >= self._budget:
                if not self._budget_breached:
                    self._budget_breached = True
                    logger.warning(
                        "BUDGET BREACHED: %.2f/%.2f EUR — blocking paid API calls",
                        self.total_spent, self._budget,
                    )
                raise BudgetExceededError(
                    provider, self.total_spent, self._budget
                )

    def record(self, provider: str, cost_eur: float | None = None) -> None:
        """Record a completed API call and its cost."""
        actual_cost = cost_eur if cost_eur is not None else DEFAULT_COSTS.get(provider, 0.0)

        with self._lock:
            self._maybe_reset_month()
            self._provider_spend[provider] = (
                self._provider_spend.get(provider, 0.0) + actual_cost
            )
            self._provider_calls[provider] = (
                self._provider_calls.get(provider, 0) + 1
            )

            # Keep rolling log (last 100 entries)
            entry = {
                "provider": provider,
                "cost_eur": actual_cost,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "running_total": self.total_spent,
            }
            self._call_log.append(entry)
            if len(self._call_log) > 100:
                self._call_log.pop(0)

            # Warn at thresholds and fire Telegram alerts
            pct = self.pct_used
            spent = self.total_spent
            budget = self._budget

            if pct >= 100 and not self._alerted_100:
                self._alerted_100 = True
                self._budget_breached = True
                logger.warning("BUDGET EXCEEDED: %.2f/%.2f EUR", spent, budget)
                self._fire_telegram_alert(pct, spent, budget)
            elif pct >= 90 and not self._alerted_90:
                self._alerted_90 = True
                logger.warning("Spend at 90%%: %.2f/%.2f EUR", spent, budget)
                self._fire_telegram_alert(pct, spent, budget)
            elif pct >= 75 and not self._alerted_75:
                self._alerted_75 = True
                logger.warning("Spend at 75%%: %.2f/%.2f EUR", spent, budget)
                self._fire_telegram_alert(pct, spent, budget)

    @staticmethod
    def _fire_telegram_alert(pct: float, spent: float, budget: float) -> None:
        """Fire-and-forget Telegram alert (runs in background)."""
        import asyncio
        try:
            from app.lib.telegram_ops import send_budget_warning, configured
            if not configured():
                return
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(send_budget_warning(pct, spent, budget))
            else:
                asyncio.run(send_budget_warning(pct, spent, budget))
        except Exception:
            logger.debug("Telegram alert skipped (not in async context)")

    def summary(self) -> dict[str, Any]:
        """Return current spend summary for the admin dashboard."""
        with self._lock:
            self._maybe_reset_month()

            providers = []
            for name in sorted(
                set(list(self._provider_spend.keys()) + list(DEFAULT_COSTS.keys()))
            ):
                providers.append({
                    "provider": name,
                    "spent_eur": round(self._provider_spend.get(name, 0.0), 4),
                    "calls": self._provider_calls.get(name, 0),
                    "cost_per_call": DEFAULT_COSTS.get(name, 0.0),
                    "paused": name in self._paused_providers,
                })

            return {
                "month": self._current_month,
                "budget_eur": self._budget,
                "total_spent_eur": round(self.total_spent, 4),
                "remaining_eur": round(self.remaining, 4),
                "pct_used": round(self.pct_used, 1),
                "budget_breached": self._budget_breached,
                "providers": providers,
                "recent_calls": self._call_log[-20:],
            }

    def reset(self) -> None:
        """Manual reset (for testing or new month)."""
        with self._lock:
            self._current_month = self._month_key()
            self._provider_spend.clear()
            self._provider_calls.clear()
            self._call_log.clear()
            self._budget_breached = False
            self._paused_providers.clear()
            self._alerted_75 = False
            self._alerted_90 = False
            self._alerted_100 = False
            logger.info("Spend tracker manually reset")


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

spend_tracker = SpendTracker(monthly_budget_eur=150.0)
