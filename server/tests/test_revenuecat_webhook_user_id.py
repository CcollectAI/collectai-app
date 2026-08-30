"""RevenueCat webhook: app_user_id -> subscriptions.user_id (uuid).

Live failure, 2026-08-30. Once the webhook's Events filter was corrected,
RevenueCat began delivering and every POST returned **500**:

    revenuecat: ledger insert failed for 38A420F6-CF4B-4706-BFC7-89C5D7F53E00
    POST /billing/revenuecat-webhook  status 500

The handler binds `user_id` to `$3::uuid`, and RevenueCat's TEST events carry a
non-UUID `app_user_id`. Proven against prod:

    select 'test_app_user_id'::uuid;
    ERROR: invalid input syntax for type uuid: "test_app_user_id"

`subscription_events.app_user_id` is a TEXT column that exists precisely to
hold whatever RevenueCat sent, so a non-UUID belongs there with `user_id` NULL
— the same shape the handler already applies to `$RCAnonymousID`.

Why it matters beyond test events: the handler returns 500 so RevenueCat
retries, and a webhook that 500s persistently gets throttled or disabled. A
real customer's id IS a uuid (AuthProvider calls Purchases.logIn with the
Supabase uid), so this would have sat as a silent trap that only bit on test
traffic — until any non-uuid id appeared.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.routes.billing_router import _rc_identified_user_id


def test_a_real_supabase_uuid_is_kept():
    uid = "4a1d7970-69a6-4575-aff3-8e1c52ae420a"
    assert _rc_identified_user_id(uid) == uid


def test_revenuecats_test_event_id_is_dropped_not_cast():
    """The exact value that produced the 500."""
    assert _rc_identified_user_id("test_app_user_id") is None


def test_anonymous_ids_are_dropped():
    assert _rc_identified_user_id("$RCAnonymousID:abc123") is None


def test_missing_id_is_dropped():
    assert _rc_identified_user_id(None) is None
    assert _rc_identified_user_id("") is None


def test_uppercase_uuid_is_accepted():
    """RevenueCat echoes ids verbatim; Postgres accepts either case."""
    uid = "4A1D7970-69A6-4575-AFF3-8E1C52AE420A"
    assert _rc_identified_user_id(uid) == uid


@pytest.mark.parametrize("bad", [
    "not-a-uuid",
    "4a1d7970-69a6-4575-aff3",              # truncated
    "4a1d7970x69a6x4575xaff3x8e1c52ae420a", # wrong separators
    "12345",
])
def test_anything_postgres_would_reject_is_dropped(bad):
    """Whatever ::uuid would refuse must never reach the bind."""
    assert _rc_identified_user_id(bad) is None


# ---------------------------------------------------------------------------
# A valid UUID is not necessarily a REAL user
# ---------------------------------------------------------------------------
#
# Second live failure, 2026-08-30, after the uuid guard above shipped:
#
#   ForeignKeyViolationError: violates foreign key constraint
#   "subscription_events_user_id_fkey"
#   DETAIL: Key (user_id)=(2b7db244-13cb-478d-b612-ddf4acb60841)
#           is not present in table "users".
#
# RevenueCat's test events invent a random UUID. It passes the format check and
# then fails the FK. Both subscription_events.user_id and subscriptions.user_id
# reference auth.users(id) — and the events FK is ON DELETE SET NULL, so NULL
# is explicitly the intended state for a user we cannot resolve.
#
# Format-valid is not existence-valid.

import pytest

from app.routes.billing_router import _rc_resolve_user_id


class _FakePool:
    """Stands in for the asyncpg pool. Records what it was asked."""

    def __init__(self, known: set[str]):
        self.known = known
        self.queries: list[tuple] = []

    async def fetchval(self, sql: str, *args):
        self.queries.append((sql, args))
        return 1 if args and str(args[0]) in self.known else None


@pytest.mark.asyncio
async def test_a_known_user_is_kept():
    uid = "4a1d7970-69a6-4575-aff3-8e1c52ae420a"
    pool = _FakePool({uid})
    assert await _rc_resolve_user_id(uid, pool) == uid


@pytest.mark.asyncio
async def test_a_valid_uuid_that_is_not_a_user_becomes_None():
    """The exact 2026-08-30 failure: RevenueCat's invented test UUID."""
    pool = _FakePool(set())
    assert await _rc_resolve_user_id("2b7db244-13cb-478d-b612-ddf4acb60841", pool) is None


@pytest.mark.asyncio
async def test_a_non_uuid_never_reaches_the_database():
    """Do not spend a round trip on something ::uuid would reject anyway."""
    pool = _FakePool(set())
    assert await _rc_resolve_user_id("test_app_user_id", pool) is None
    assert pool.queries == [], "must short-circuit before querying"


@pytest.mark.asyncio
async def test_no_pool_degrades_to_unidentified_rather_than_raising():
    """Without a DB we cannot prove the user exists, so we must not claim it."""
    assert await _rc_resolve_user_id("4a1d7970-69a6-4575-aff3-8e1c52ae420a", None) is None
