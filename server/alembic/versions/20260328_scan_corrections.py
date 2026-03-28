"""Add scan_corrections table for QuickScan feedback loop.

Revision ID: 20260328_scan_corrections
"""
from alembic import op
import sqlalchemy as sa

revision = "20260328_scan_corrections"
down_revision = None  # Will be auto-set by Alembic
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "scan_corrections",
        sa.Column("id", sa.dialects.postgresql.UUID, server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", sa.dialects.postgresql.UUID, nullable=False),
        sa.Column("scan_session_id", sa.Text, nullable=False),
        sa.Column("corrected_name", sa.Text, nullable=True),
        sa.Column("corrected_category", sa.Text, nullable=True),
        sa.Column("corrected_condition", sa.Text, nullable=True),
        sa.Column("user_weight", sa.Float, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "scan_session_id", name="uq_scan_corrections_user_session"),
    )
    op.create_index("idx_scan_corrections_session", "scan_corrections", ["scan_session_id"])
    op.create_index("idx_scan_corrections_category", "scan_corrections", ["corrected_category"])

def downgrade():
    op.drop_table("scan_corrections")
