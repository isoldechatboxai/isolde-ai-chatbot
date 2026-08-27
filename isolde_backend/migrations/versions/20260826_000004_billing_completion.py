"""Complete billing provider state and credit ledger.

Revision ID: 20260826_000004
Revises: 20260826_000003
"""
from alembic import op
import sqlalchemy as sa

revision = "20260826_000004"
down_revision = "20260826_000003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("billing_subscriptions") as batch:
        batch.add_column(sa.Column("provider_subscription_id", sa.String(length=255), nullable=True))
        batch.create_unique_constraint("uq_billing_subscription_provider_id", ["provider_subscription_id"])
    with op.batch_alter_table("billing_invoices") as batch:
        batch.add_column(sa.Column("provider_payment_id", sa.String(length=255), nullable=True))
    op.create_table(
        "billing_credit_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("credits_delta", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("provider_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_billing_credit_ledger_user_id", "billing_credit_ledger", ["user_id"])
    op.create_index("ix_billing_credit_ledger_idempotency_key", "billing_credit_ledger", ["idempotency_key"], unique=True)


def downgrade():
    op.drop_index("ix_billing_credit_ledger_idempotency_key", table_name="billing_credit_ledger")
    op.drop_index("ix_billing_credit_ledger_user_id", table_name="billing_credit_ledger")
    op.drop_table("billing_credit_ledger")
    with op.batch_alter_table("billing_invoices") as batch:
        batch.drop_column("provider_payment_id")
    with op.batch_alter_table("billing_subscriptions") as batch:
        batch.drop_constraint("uq_billing_subscription_provider_id", type_="unique")
        batch.drop_column("provider_subscription_id")
