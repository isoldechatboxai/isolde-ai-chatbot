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
    inspector = sa.inspect(op.get_bind())
    if "billing_payment_events" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("billing_payment_events")}
        required = {"id", "provider", "event_id", "event_type", "processed_at"}
        if not required <= columns:
            raise RuntimeError("Existing billing_payment_events schema is incompatible with this migration.")
        return
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
