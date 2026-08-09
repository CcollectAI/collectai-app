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
    dac7_reportable as reportable,
)

# The REAL predicate, imported — not a local mirror of it.
#
# This file used to define its own `reportable()` copying the expression out of
# `_dac7_accrue`. Every test below passed against the copy, so the suite would
# have stayed green if the connective in the accrual had been changed to `and` —
# which is the single thing these tests exist to prevent
# (learning_tests_that_pin_a_stub). `dac7_reportable` is now module-level in the
# router and used by the accrual, `GET /p2p/dac7/me`, and here.


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


class TestDac7StatusEndpoint:
    """`GET /p2p/dac7/me` — the member-visible half of the §6 promise.

    Terms tell members we count their sales and warn them before reporting.
    The counter existed and the warning fired, but nothing could SHOW it, so
    there was no way to verify the promise was being kept.
    """

    def test_headroom_is_null_once_reportable(self):
        """"0 sales remaining" would read as "one more crosses it" when it has
        already been crossed."""
        from app.features.p2p_offers_router import _dac7_year_out

        row = {
            "year": 2026, "sales_count": 40, "gross_eur": 800.0,
            "reportable_at": None, "notified_at": None, "details_provided_at": None,
        }
        out = _dac7_year_out(row)
        assert out.reportable is True
        assert out.sales_remaining is None
        assert out.gross_eur_remaining is None

    def test_headroom_counts_down_while_excluded(self):
        from app.features.p2p_offers_router import _dac7_year_out

        out = _dac7_year_out({
            "year": 2026, "sales_count": 4, "gross_eur": 500.0,
            "reportable_at": None, "notified_at": None, "details_provided_at": None,
        })
        assert out.reportable is False
        assert out.sales_remaining == 26        # 30 - 4
        assert out.gross_eur_remaining == 1500.0

    def test_reportable_is_recomputed_not_read_off_the_stamp(self):
        """`reportable_at` records WHEN we noticed. Between the counter update
        and the notify stamp it is still NULL while the seller is already over,
        and reporting `false` there would tell them the opposite of the truth."""
        from app.features.p2p_offers_router import _dac7_year_out

        out = _dac7_year_out({
            "year": 2026, "sales_count": 31, "gross_eur": 10.0,
            "reportable_at": None,          # not stamped yet
            "notified_at": None, "details_provided_at": None,
        })
        assert out.reportable is True

    def test_zero_row_is_excluded_and_keeps_full_headroom(self):
        from app.features.p2p_offers_router import _dac7_year_out

        out = _dac7_year_out({
            "year": 2026, "sales_count": 0, "gross_eur": 0.0,
            "reportable_at": None, "notified_at": None, "details_provided_at": None,
        })
        assert out.reportable is False
        assert out.sales_remaining == 30
        assert out.gross_eur_remaining == 2000.0

    def test_endpoint_is_authed_and_self_only(self):
        """No user_id parameter anywhere: another member's tax exposure is not
        something an authenticated caller may ask this router for."""
        import inspect
        from app.features.p2p_offers_router import dac7_status

        sig = inspect.signature(dac7_status)
        assert list(sig.parameters) == ["user_id"], sig.parameters
        src = inspect.getsource(dac7_status)
        assert "WHERE user_id = $1::uuid" in src
        # The year must come from the DB, matching the accrual's
        # EXTRACT(YEAR FROM now()) — not from Python's clock.
        assert "EXTRACT(YEAR FROM now())" in src
