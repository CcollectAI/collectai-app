"""User blocking — one implementation, used by every surface a blocked user
could otherwise still reach.

Why this module exists
----------------------
`user_blocks` was enforced in exactly ONE place (`chat_router._check_not_blocked`)
while the P2P marketplace shipped with no block logic at all. The result: you
could block someone and still see their listings, and they could still send you
offers. "Block" meant "block in chat", which is not what the word promises and
not what Apple App Review Guideline 1.2 asks for ("the ability to block abusive
users **from the service**").

The fix is a chokepoint rather than N call sites — the same reasoning as
`_OFFER_COLUMNS` in p2p_offers_router.py. A second private copy of this query is
how one surface gets the fix and another silently does not
(learning_duplicate_impl_silently_drops_the_fix).

Blocking is ALWAYS symmetric here. If either party blocked the other, they do
not interact. A one-directional read would let the blocked party keep watching
the blocker's activity, which is the failure mode blocking exists to prevent.
"""
from __future__ import annotations

from typing import List, Optional

import asyncpg

from app.errors import error_response


async def is_blocked(conn: asyncpg.Connection, user_a: str, user_b: str) -> bool:
    """True if either user has blocked the other. Symmetric by design."""
    if not user_a or not user_b or user_a == user_b:
        return False
    return bool(
        await conn.fetchval(
            """
            SELECT 1 FROM user_blocks
            WHERE (blocker_id = $1::uuid AND blocked_id = $2::uuid)
               OR (blocker_id = $2::uuid AND blocked_id = $1::uuid)
            LIMIT 1
            """,
            user_a,
            user_b,
        )
    )


async def raise_if_blocked(
    conn: asyncpg.Connection,
    user_a: str,
    user_b: str,
    message: str = "You can't interact with this member",
) -> None:
    """403 if either party blocked the other."""
    if await is_blocked(conn, user_a, user_b):
        raise error_response(403, message, code="USER_BLOCKED")


async def blocked_user_ids(
    conn: asyncpg.Connection, user_id: Optional[str]
) -> List[str]:
    """Every user_id `user_id` cannot see, in BOTH directions.

    For filtering a list query. Returns [] for an anonymous caller — an
    anonymous browser has no blocks, and passing NULL into the SQL below would
    silently match nothing rather than everything.
    """
    if not user_id:
        return []
    rows = await conn.fetch(
        """
        SELECT blocked_id AS other FROM user_blocks WHERE blocker_id = $1::uuid
        UNION
        SELECT blocker_id AS other FROM user_blocks WHERE blocked_id = $1::uuid
        """,
        user_id,
    )
    return [str(r["other"]) for r in rows]
