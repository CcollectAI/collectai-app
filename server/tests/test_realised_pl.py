"""Realised P/L — the arithmetic docs/COLLECTOR_DEMAND.md §5 says nobody does.

Calls the REAL `summarise_realised_sales`, never a copy of it: the observed_at
tests on 2026-08-30 reimplemented the writer loop inside the test file and
stayed green while the fix was reverted (learning_tests_that_pin_a_stub).
"""
import pytest

from app.routes.portfolio_router import summarise_realised_sales


def sale(**kw):
    row = {
        "id": "s1", "sold_at": None, "sale_price": 1000.0, "currency": "EUR",
        "net_proceeds": 852.20, "platform_fee": 132.80,
        "payment_processing_fee": 0.30, "shipping_cost_actual": 15.0,
        "item_id": "i1", "item_name": "Card", "category": "pokemon",
        "purchase_price_eur": 900.0, "acquisition_fees_eur": 56.25,
        "cost_basis": 956.25,
    }
    row.update(kw)
    return row


class TestTheResearchCase:
    def test_a_1000_sale_on_a_956_basis_is_a_LOSS(self):
        """The worked example, end to end.

        EUR 900 card + EUR 56.25 tax = EUR 956.25 basis. Sells for EUR 1000 --
        which looks like +44 -- and after 13.25%+0.30 and 15 shipping nets
        852.20, a 104.05 LOSS. Every collection app shows the +44.
        """
        out = summarise_realised_sales([sale()])
        assert out["sales"][0]["profit"] == -104.05
        assert out["total_profit"] == -104.05

    def test_profit_is_rounded_for_display(self):
        # -104.04999999999995 reaches the client and renders that way.
        p = summarise_realised_sales([sale()])["sales"][0]["profit"]
        assert p == round(p, 2)

    def test_ignoring_acquisition_fees_would_flip_the_sign(self):
        # Proves the fee half is load-bearing rather than cosmetic: without it
        # the SAME sale reports a profit.
        out = summarise_realised_sales([sale(cost_basis=900.0)])
        assert out["sales"][0]["profit"] == -47.8
        assert out["sales"][0]["profit"] > -104.05


class TestUnknownBasisIsNotZero:
    def test_a_sale_with_no_purchase_price_reports_profit_NULL(self):
        """`None`, never 0.

        Subtracting a missing basis from net proceeds renders the entire
        proceeds as pure profit -- the `None or 0` failure that turns UNKNOWN
        into a confident number
        (learning_a_blind_source_deletes_the_finding_not_just_the_number).
        """
        out = summarise_realised_sales([sale(cost_basis=None, purchase_price_eur=None)])
        assert out["sales"][0]["profit"] is None
        assert out["sales"][0]["cost_basis_known"] is False

    def test_unknown_basis_is_EXCLUDED_from_the_total_and_COUNTED(self):
        out = summarise_realised_sales([sale(), sale(id="s2", cost_basis=None)])
        assert out["total_profit"] == -104.05      # only the known one
        assert out["sales_without_cost_basis"] == 1
        assert out["count"] == 2

    def test_net_proceeds_still_totals_across_unknown_basis_rows(self):
        # Proceeds are known even when the basis is not; hiding them would
        # under-report money that actually arrived.
        out = summarise_realised_sales([sale(), sale(id="s2", cost_basis=None)])
        assert out["total_net_proceeds"] == round(852.20 * 2, 2)

    def test_a_missing_net_proceeds_is_also_None_not_zero(self):
        out = summarise_realised_sales([sale(net_proceeds=None)])
        assert out["sales"][0]["profit"] is None
        assert out["total_net_proceeds"] == 0.0


class TestShape:
    def test_empty_in_empty_out_with_zero_totals(self):
        out = summarise_realised_sales([])
        assert out == {"sales": [], "count": 0, "total_profit": 0.0,
                       "total_net_proceeds": 0.0, "sales_without_cost_basis": 0}

    def test_fees_are_broken_out_so_the_client_can_SHOW_the_deduction(self):
        f = summarise_realised_sales([sale()])["sales"][0]["fees"]
        assert f == {"platform": 132.80, "payment_processing": 0.30, "shipping": 15.0}

    def test_null_fees_render_as_zero_not_crash(self):
        f = summarise_realised_sales([sale(platform_fee=None, shipping_cost_actual=None)])[
            "sales"][0]["fees"]
        assert f["platform"] == 0 and f["shipping"] == 0

    def test_an_item_deleted_after_sale_still_reports_the_sale(self):
        # LEFT JOIN: the sale is real even if the item row is gone.
        out = summarise_realised_sales([sale(item_id=None, item_name=None, cost_basis=None)])
        assert out["count"] == 1
        assert out["sales"][0]["item_id"] is None
        assert out["sales"][0]["profit"] is None


class TestTheSQLItself:
    """The arithmetic tests above pass `cost_basis` in pre-computed, so the SQL
    that PRODUCES it is invisible to them. Proven by mutation on 2026-08-31:
    deleting `+ COALESCE(i.acquisition_fees_eur, 0)` from the query left all 11
    green. That is learning_sql_in_a_python_string_is_invisible_to_js_checkers,
    and the cost basis now lives in THREE places that must agree:

      * portfolio_router  /portfolio/items      -- the CASE
      * portfolio_router  /portfolio/realised-pl -- the same CASE
      * value_summary_router                     -- projection AND filter

    Three copies of one fact is learning_duplicated_value_chain_drifts_silently;
    these assertions are what stops the next edit landing on only one of them.
    """

    import pathlib
    ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"

    def _src(self, rel):
        return (self.ROOT / rel).read_text()

    def test_both_portfolio_queries_add_the_fee_half(self):
        src = self._src("routes/portfolio_router.py")
        occurrences = src.count("i.purchase_price_eur + COALESCE(i.acquisition_fees_eur, 0)")
        assert occurrences == 2, (
            f"expected the fee-aware basis in BOTH /portfolio/items and "
            f"/portfolio/realised-pl, found {occurrences}. A basis that differs "
            f"between the projection and the realised view is two answers to "
            f"'what did you pay'."
        )

    def test_fees_are_NOT_added_to_the_model_estimate_fallback(self):
        # Attaching real tax to a model guess would dress drift up as evidence.
        src = self._src("routes/portfolio_router.py")
        assert "ELSE COALESCE(e.first_q50, 0)" in src
        assert "e.first_q50, 0) + COALESCE(i.acquisition_fees_eur" not in src

    def test_value_summary_moves_its_FILTER_with_its_PROJECTION(self):
        # Filtering on the sticker price while displaying a fee-aware saving
        # lists items whose saving is negative --
        # learning_queue_filter_disagrees_with_its_own_projection.
        src = self._src("features/value_summary_router.py")
        assert "pp.q50 > (i.purchase_price_eur + COALESCE(i.acquisition_fees_eur, 0))" in src
        assert "(pp.q50 - i.purchase_price_eur - COALESCE(i.acquisition_fees_eur, 0)) AS saved" in src

    def test_the_purchase_route_writes_BOTH_halves_of_the_fee_pair(self):
        # Writing one half of a paired column never throws; the reader defaults
        # and the feature renders empty (docs/ARCHITECTURE.md).
        # Both halves move together, and BOTH are gated by the same $9 flag.
        # A pair where only one half is conditional is the paired-column bug
        # wearing a different hat: one edit and the two columns disagree.
        src = self._src("routes/items_router.py")
        assert "acquisition_fees     = CASE WHEN $9 THEN $7 ELSE acquisition_fees     END" in src
        assert "acquisition_fees_eur = CASE WHEN $9 THEN $8 ELSE acquisition_fees_eur END" in src

    def test_clearing_the_price_clears_the_fees(self):
        src = self._src("routes/items_router.py")
        assert "if price is None:" in src and "fees, fees_eur = None, None" in src


class TestOmittedIsNotNull:
    """A caller that does not mention fees must not erase them.

    Found by auditing my own new code on 2026-08-31, BEFORE release.
    `acquisition_fees` defaults to None, and the first version of the route
    wrote it unconditionally -- so the shipped app, which predates the field and
    sends only `purchase_price`, would have wiped a member's fees on every
    price edit. Verified against the real database in a rolled-back transaction
    as well as here.
    """

    def _payload(self, **kw):
        from app.routes.items_router import UpdateItemPurchaseRequest
        return UpdateItemPurchaseRequest(**kw)

    def test_pydantic_cannot_distinguish_omitted_from_null_by_VALUE(self):
        # Both are None; only model_fields_set separates them. This is the
        # whole reason the route cannot just check `if fees is None`.
        omitted = self._payload(purchase_price=900.0, purchase_currency="EUR")
        explicit = self._payload(purchase_price=900.0, purchase_currency="EUR",
                                 acquisition_fees=None)
        assert omitted.acquisition_fees is explicit.acquisition_fees is None
        assert "acquisition_fees" not in omitted.model_fields_set
        assert "acquisition_fees" in explicit.model_fields_set

    def test_the_route_gates_the_write_on_model_fields_set(self):
        import pathlib
        src = (pathlib.Path(__file__).resolve().parents[1]
               / "app" / "routes" / "items_router.py").read_text()
        assert 'fees_provided = ("acquisition_fees" in payload.model_fields_set) or price is None' in src
        # The CASE is what makes the flag do anything.
        assert "acquisition_fees     = CASE WHEN $9 THEN $7 ELSE acquisition_fees     END" in src
        assert "acquisition_fees_eur = CASE WHEN $9 THEN $8 ELSE acquisition_fees_eur END" in src

    def test_clearing_the_price_still_clears_fees_even_if_unmentioned(self):
        # Coherence of the ROW beats what the caller typed: fees on a purchase
        # with no price would be added to a model estimate by portfolio_router.
        p = self._payload(purchase_price=None, purchase_currency="EUR")
        fees_provided = ("acquisition_fees" in p.model_fields_set) or p.purchase_price is None
        assert fees_provided is True
