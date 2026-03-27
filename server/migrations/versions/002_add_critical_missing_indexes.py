"""Add critical missing indexes for notifications, marketplace, and worker queries.

Revision ID: 002_critical_indexes
Revises: 001_perf_indexes
Create Date: 2026-03-27
"""
from __future__ import annotations

from alembic import op

revision: str = "002_critical_indexes"
down_revision: str | None = "001_perf_indexes"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Portfolio items: speeds up category filtering and user item listing
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_portfolio_items_user_category "
        "ON portfolio_items(user_id, category, updated_at DESC)"
    )
    # Price predictions: speeds up recent prediction lookups by item
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_price_preds_nk_recent "
        "ON price_predictions(nk, created_at DESC)"
    )
    # User push tokens: speeds up push notification targeting (partial index)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_push_tokens_user_active "
        "ON user_push_tokens(user_id) WHERE active = true"
    )
    # Notification history: speeds up type-filtered notification queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_notification_history_user_type "
        "ON notification_history(user_id, type, created_at DESC)"
    )
    # Events: speeds up event listing by date
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_date_user "
        "ON events(start_date, user_id)"
    )
    # Marketplace listings: speeds up user listing dashboard
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_marketplace_listings_user_status "
        "ON marketplace_listings(user_id, status, updated_at DESC)"
    )
    # Market hits: speeds up valuation worker batch queries (partial index)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_market_hits_processed "
        "ON market_hits(processed) WHERE processed = false"
    )
    # Watchlist: speeds up monitor worker batch queries (partial index)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_watchlist_user_next_check "
        "ON watchlist(user_id, next_check_at) WHERE active = true"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_portfolio_items_user_category")
    op.execute("DROP INDEX IF EXISTS idx_price_preds_nk_recent")
    op.execute("DROP INDEX IF EXISTS idx_user_push_tokens_user_active")
    op.execute("DROP INDEX IF EXISTS idx_notification_history_user_type")
    op.execute("DROP INDEX IF EXISTS idx_events_date_user")
    op.execute("DROP INDEX IF EXISTS idx_marketplace_listings_user_status")
    op.execute("DROP INDEX IF EXISTS idx_market_hits_processed")
    op.execute("DROP INDEX IF EXISTS idx_watchlist_user_next_check")
