"""Every FK to auth.users that blocks a delete must be cleared first.

Ten tables reference `auth.users` with `NO ACTION` (measured on prod
2026-08-30), so a row in any of them makes `DELETE FROM auth.users` raise a
foreign-key violation. GoTrue surfaces that as a 500, which is how the e2e
sanity workflow had been failing.

Five were already cleared by the deletion path. Five were not:

    chat_rooms, chat_reports, task_queue, event_announcements, sponsor_companies

All five held 0 rows except task_queue (1, the e2e test user), so this was
LATENT, not live — no real member was blocked. It would have bitten the first
user to file a report or author an announcement.

⚠️ The trap this file exists to prevent: the deletion loop hardcodes
`WHERE user_id = $1` and, on UndefinedColumnError, logs and RE-RAISES rather
than skipping — deliberately, so a partial erasure can never report success.
So adding a table whose owner column is `created_by` would not merely fail to
delete it; it would ABORT every account deletion. The name and the column have
to be added together.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.routes.account_router import _ALLOWED_TABLES, _OWNER_COLUMN, _RETAINED_TABLES

# Measured on prod 2026-08-30:
#   select conrelid::regclass, conname, confdeltype from pg_constraint
#    where contype='f' and confrelid='auth.users'::regclass and confdeltype not in ('c','n');
_BLOCKING_FKS = {
    "portfolio_values": "user_id",
    "chat_rooms": "created_by",
    "chat_messages": "user_id",
    "chat_reports": "reporter",
    "task_queue": "created_by",
    "event_announcements": "author_user_id",
    "event_templates": "user_id",
    "sponsor_companies": "admin_user_id",
    "user_category_follows": "user_id",
    "event_announcement_reads": "user_id",
}

# Deliberately NOT cleared, with the reason. Both are unreachable today.
_KNOWN_UNCLEARED = {
    "chat_rooms": "orphan table — no writer anywhere in the repo (only "
                  "audit_rls_coverage.py names it), so no row can ever exist",
    "sponsor_companies": "future product, 0 rows; deleting a company because "
                         "its admin left is the wrong semantics — needs "
                         "reassignment, which is a product decision",
}


def test_every_blocking_fk_is_cleared_or_explicitly_excused():
    """The enumeration IS the gate. A new FK to auth.users with NO ACTION must
    either join the deletion path or be justified here — not discovered later
    by a member whose deletion 500s."""
    unhandled = [
        t for t in _BLOCKING_FKS
        if t not in _ALLOWED_TABLES and t not in _KNOWN_UNCLEARED
        and t not in _RETAINED_TABLES
    ]
    assert unhandled == [], f"blocking FKs neither cleared nor excused: {unhandled}"


def test_tables_whose_owner_column_is_not_user_id_declare_it():
    """The loop hardcodes WHERE user_id = $1 and RE-RAISES on a missing column,
    so a mismatch here aborts every account deletion rather than skipping one
    table."""
    for table, col in _BLOCKING_FKS.items():
        if table in _ALLOWED_TABLES and col != "user_id":
            assert _OWNER_COLUMN.get(table) == col, (
                f"{table} is cleared by column '{col}', not 'user_id', and must "
                f"declare that in _OWNER_COLUMN or it will abort deletion"
            )


def test_owner_columns_are_safe_identifiers():
    """They are interpolated into SQL."""
    for table, col in _OWNER_COLUMN.items():
        assert col.isidentifier(), f"{table}: {col!r} is not a bare identifier"
        assert table.isidentifier(), f"{table!r} is not a bare identifier"


def test_owner_column_entries_are_actually_in_the_delete_list():
    """A mapping for a table nobody deletes is dead config that reads as cover."""
    for table in _OWNER_COLUMN:
        assert table in _ALLOWED_TABLES, (
            f"{table} has an _OWNER_COLUMN entry but is not in _ALLOWED_TABLES"
        )


# ---------------------------------------------------------------------------
# The loop must USE the mapping, not merely have one
# ---------------------------------------------------------------------------
#
# Mutation-testing exposed a gap in the tests above: they inspect
# _ALLOWED_TABLES and _OWNER_COLUMN, so reverting the loop to a hardcoded
# `WHERE user_id = $1` left all of them green while task_queue silently stopped
# being cleared. Config tests are not behaviour tests.

import re

import pytest


def test_the_delete_loop_targets_the_mapped_column():
    """Read the SQL the loop actually builds, not the table it builds it from."""
    src = Path(__file__).resolve().parent.parent / "app" / "routes" / "account_router.py"
    body = src.read_text()
    stmt = re.search(r"DELETE FROM \"\{table\}\" WHERE ([^\n]*?)= \$1", body)
    assert stmt, "could not find the deletion statement"
    assert "owner_col" in stmt.group(1), (
        "the loop hardcodes its column instead of using _OWNER_COLUMN — "
        f"task_queue would stop being cleared. Found: {stmt.group(1)!r}"
    )


def test_task_queue_is_deleted_by_created_by_not_user_id():
    """End of the argument: run the real handler against the sibling test
    file's known-good pool mock and read the SQL it actually issued."""
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from tests.test_account_router import _mock_pool
    from main import app

    issued: list[str] = []

    async def _capture(sql, *a, **k):
        issued.append(sql)
        return None

    pool, conn = _mock_pool(execute_side_effect=_capture)

    with patch("app.routes.account_router.get_db_pool") as gp, \
         patch("app.routes.account_router._get_supabase_admin") as ga:
        gp.return_value = pool
        ga.return_value = None
        TestClient(app).delete("/account?confirm=DELETE_MY_ACCOUNT")

    tq = [x for x in issued if "task_queue" in x]
    assert tq, f"task_queue was never deleted; issued {len(issued)} statements"
    assert any('"created_by"' in x for x in tq), f"expected created_by, got: {tq}"
    assert not any("WHERE user_id" in x for x in tq), (
        "task_queue has no user_id column — this would abort the whole deletion"
    )
