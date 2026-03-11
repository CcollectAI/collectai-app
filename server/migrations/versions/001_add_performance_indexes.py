"""Add performance indexes for common query patterns.

Revision ID: 001_perf_indexes
Revises: None
Create Date: 2026-03-10
"""
from __future__ import annotations

from alembic import op

revision: str = "001_perf_indexes"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Items: user lookup + category filtering (portfolio, trends, items list)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_user_category "
        "ON items (user_id, category)"
    )
    # Price predictions: item lookup + time-series ordering
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_price_predictions_item_asof "
        "ON price_predictions (item_id, asof DESC)"
    )
    # Notifications: user inbox + unread filtering (partial index)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_notifications_user_unread "
        "ON notifications (user_id, created_at DESC) WHERE read_at IS NULL"
    )
    # Webhook idempotency: event dedup lookup
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_processed_webhook_events_event_id "
        "ON processed_webhook_events (event_id)"
    )
    # Watchlist: user lookup
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_watchlist_items_user "
        "ON watchlist_items (user_id)"
    )
    # Price history: item + date range queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_price_history_item_date "
        "ON price_history (item_id, recorded_at DESC)"
    )
    # Market hits: category + recency (model retrain worker)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_market_hits_category_date "
        "ON market_hits (category, fetched_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_items_user_category")
    op.execute("DROP INDEX IF EXISTS idx_price_predictions_item_asof")
    op.execute("DROP INDEX IF EXISTS idx_notifications_user_unread")
    op.execute("DROP INDEX IF EXISTS idx_processed_webhook_events_event_id")
    op.execute("DROP INDEX IF EXISTS idx_watchlist_items_user")
    op.execute("DROP INDEX IF EXISTS idx_price_history_item_date")
    op.execute("DROP INDEX IF EXISTS idx_market_hits_category_date")
