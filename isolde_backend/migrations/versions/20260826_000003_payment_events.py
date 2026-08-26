"""Add idempotent payment event persistence.

Revision ID: 20260826_000003
Revises: 20260826_000002
"""
from alembic import op
import sqlalchemy as sa

revision = "20260826_000003"
down_revision = "20260826_000002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "billing_payment_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_billing_payment_events_event_id", "billing_payment_events", ["event_id"], unique=True)


def downgrade():
    op.drop_index("ix_billing_payment_events_event_id", table_name="billing_payment_events")
    op.drop_table("billing_payment_events")
