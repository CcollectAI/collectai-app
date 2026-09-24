"""Paid event features stay OFF until they can take money correctly.

Measured 2026-09-24: Stripe on prod is a test key, the sponsor price ids are
empty (one route used invented ones), and ticket checkout pays the organiser
nothing. config.PAID_EVENTS_ENABLED gates every door to it on the SERVER, so an
older app build cannot open one either. Also pins the event time parser: the
form's own placeholder "19:30 CET" made create_event answer 500.
"""
import os
import sys
from datetime import time as dt_time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_ENABLED", "false")

from fastapi import HTTPException  # noqa: E402

from app.features import sponsor_company_router, sponsor_router  # noqa: E402
from app.features.events import events_core  # noqa: E402
from app.features.events.events_helpers import CreateEventRequest, parse_event_time  # noqa: E402

EVENT = "00000000-0000-0000-0000-0000000000e1"
USER = "00000000-0000-0000-0000-0000000000a1"


@pytest.mark.parametrize("raw,expected", [
    ("19:30", dt_time(19, 30)), ("19:30 CET", dt_time(19, 30)), ("19.30", dt_time(19, 30)),
    ("7pm", dt_time(19, 0)), ("7:30 pm", dt_time(19, 30)), ("12am", dt_time(0, 0)),
    ("19:30:00", dt_time(19, 30)), ("", None), (None, None),
])
def test_parse_event_time_accepts(raw, expected):
    assert parse_event_time(raw) == expected


@pytest.mark.parametrize("raw", ["25:00", "abc", "13pm", "2026"])
def test_parse_event_time_rejects(raw):
    with pytest.raises(ValueError):
        parse_event_time(raw)


def _status(exc_info):
    return exc_info.value.status_code


def _closed(exc_info):
    """503 alone is not proof — with no DB or Stripe in tests these routes 503
    anyway. The GATE's own code is."""
    d = exc_info.value.detail
    return exc_info.value.status_code == 503 and isinstance(d, dict) and d.get("code") == "PAID_FEATURE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_ticket_checkout_is_closed(monkeypatch):
    monkeypatch.setattr(events_core, "PAID_EVENTS_ENABLED", False)
    with pytest.raises(HTTPException) as e:
        await events_core.ticket_checkout(EVENT, user_id=USER)
    assert _closed(e)


@pytest.mark.asyncio
async def test_priced_event_is_refused(monkeypatch):
    monkeypatch.setattr(events_core, "PAID_EVENTS_ENABLED", False)
    req = CreateEventRequest(title="t", kind="meetup", date="2026-10-01", ticket_price_cents=500)
    with pytest.raises(HTTPException) as e:
        await events_core.create_event(req, user_id=USER)
    assert _status(e) == 400 and e.value.detail["code"] == "PAID_FEATURE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_bad_time_is_a_400_not_a_500(monkeypatch):
    req = CreateEventRequest(title="t", kind="meetup", date="2026-10-01", time="whenever")
    with pytest.raises(HTTPException) as e:
        await events_core.create_event(req, user_id=USER)
    assert _status(e) == 400


@pytest.mark.asyncio
async def test_sponsor_checkouts_are_closed(monkeypatch):
    monkeypatch.setattr(sponsor_company_router, "PAID_EVENTS_ENABLED", False)
    monkeypatch.setattr(sponsor_router, "PAID_EVENTS_ENABLED", False)
    company = "00000000-0000-0000-0000-0000000000c1"
    with pytest.raises(HTTPException) as e:
        await sponsor_company_router.create_event_checkout(
            company, sponsor_company_router.CreateSponsorEventCheckoutRequest(
                tier="featured", event_title="t", event_kind="meetup", event_date="2026-10-01"),
            user_id=USER)
    assert _closed(e)
    with pytest.raises(HTTPException) as e:
        await sponsor_company_router.create_subscription_checkout(
            company, sponsor_company_router.CreateSponsorSubscriptionRequest(tier="featured"),
            user_id=USER, _rl=None)
    assert _closed(e)
    with pytest.raises(HTTPException) as e:
        await sponsor_router.create_sponsor_checkout(
            sponsor_router.SponsorCheckoutRequest(event_id=EVENT, tier="featured", sponsor_name="x"),
            user_id=USER, _rl=None)
    assert _closed(e)
