"""A guessed shipping cost never decides a deal; checks are structured.

2026-09-24: a €12.27 card was rejected against a €30 limit because the agent
ADDED an estimated €22.50 shipping (a regional midpoint) — 6 of 39 rejections on
one test mandate — and the deal screen showed engine strings verbatim.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.policy_engine import evaluate  # noqa: E402

M = {"max_price": 30, "min_trust_score": 0.6, "allowed_sources": ["ebay"]}


def _hit(**kw):
    h = {"title": "Charizard ex", "price": 12.27, "source": "ebay", "provenance_score": 0.7}
    h.update(kw)
    return h


def test_estimated_shipping_does_not_fail_the_limit():
    v = evaluate(M, _hit(shipping_cost=22.5, shipping_estimated=True, shipping_min=5, shipping_max=40))
    assert v.passed
    price = next(c for c in v.checks if c["code"] == "price")
    assert price["ok"] and price["shipping"] is None and price["shipping_estimated"]
    assert (price["shipping_min"], price["shipping_max"]) == (5, 40)


def test_stated_shipping_still_counts():
    v = evaluate(M, _hit(shipping_cost=22.5))
    assert not v.passed
    price = next(c for c in v.checks if c["code"] == "price")
    assert not price["ok"] and price["shipping"] == 22.5


def test_every_check_is_a_code_not_a_sentence():
    v = evaluate(M, _hit(shipping_cost=1.0))
    codes = {c["code"] for c in v.checks}
    assert {"price", "trust", "source"} <= codes
    assert all(isinstance(c["ok"], bool) for c in v.checks)
