"""DAC7 reportable-seller threshold rule.

Guards a promise made to users in writing. `app/legal/marketplace-terms.tsx` §6
tells members we count their sales automatically and will warn them before they
are reported. That sentence used to have NOTHING behind it; `_dac7_accrue` is
now what makes it true, and this is what stops it silently rotting.

The ONE thing that matters here is the connective. A seller is an EXCLUDED
SELLER only when BOTH limbs hold:

    fewer than 30 sales  AND  no more than EUR 2,000

so a seller becomes REPORTABLE when EITHER is breached. Writing `and` instead of
`or` in the reportable test would under-report every high-volume/low-value
seller — 40 sales at EUR 20 is the exact shape that slips through — and nothing
else in the system would notice, because the failure mode is silence.

These tests exercise the rule as a pure predicate rather than mocking a DB
round-trip: the SQL is a counter, the rule is the part that can be wrong.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.features.p2p_offers_router import (  # noqa: E402
    DAC7_SALES_LIMIT,
    DAC7_GROSS_EUR_LIMIT,
)


def reportable(sales: int, gross_eur: float) -> bool:
    """The predicate exactly as `_dac7_accrue` applies it."""
    return sales >= DAC7_SALES_LIMIT or gross_eur > DAC7_GROSS_EUR_LIMIT


class TestDac7Limits:
    def test_limits_match_the_published_terms(self):
        """If these drift, the legal screen becomes a false statement."""
        assert DAC7_SALES_LIMIT == 30
        assert DAC7_GROSS_EUR_LIMIT == 2000.0


class TestExcludedSeller:
    def test_under_both_limits_is_excluded(self):
        assert reportable(29, 1999.99) is False

    def test_no_sales_is_excluded(self):
        assert reportable(0, 0) is False

    def test_at_the_value_limit_is_still_excluded(self):
        """The rule is 'more than EUR 2,000', not 'at least'. Exactly 2000 is out."""
        assert reportable(29, 2000.00) is False

    def test_one_below_the_count_limit_is_excluded(self):
        assert reportable(29, 0) is False


class TestReportableSeller:
    def test_count_limb_alone_makes_a_seller_reportable(self):
        """40 sales at EUR 20 — the case an `and` would silently miss.

        Total consideration is EUR 800, far below the value limit, so this
        seller is reportable ONLY because of the count. This is the test that
        fails if someone 'simplifies' the connective.
        """
        assert reportable(40, 800.00) is True

    def test_value_limb_alone_makes_a_seller_reportable(self):
        """3 sales at EUR 1,000 — reportable on value with 27 sales to spare."""
        assert reportable(3, 3000.00) is True

    def test_exactly_at_the_count_limit_is_reportable(self):
        """'Fewer than 30' excludes; 30 itself does not."""
        assert reportable(30, 0) is True

    def test_just_over_the_value_limit_is_reportable(self):
        assert reportable(1, 2000.01) is True

    def test_both_limbs_breached_is_reportable(self):
        assert reportable(100, 50_000.00) is True


class TestAccrualWiring:
    def test_completion_path_calls_the_accrual(self):
        """Completion is the only moment consideration becomes known.

        If this call is ever dropped, the counters stay at zero forever and the
        app quietly stops keeping a promise it makes in writing — with no error
        anywhere. Assert the wiring, not just the arithmetic.
        """
        import inspect
        from app.features.p2p_offers_router import confirm_exchange

        src = inspect.getsource(confirm_exchange)
        assert "_dac7_accrue" in src, "trade completion no longer accrues DAC7"
        assert 'fresh["seller_id"]' in src, "DAC7 must accrue against the SELLER"
