"""Add tenant-wide provider and billing policies.

Revision ID: 20260827_000006
Revises: 20260826_000005
"""
from alembic import op
import sqlalchemy as sa

revision = "20260827_000006"
down_revision = "20260826_000005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organization_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("allowed_providers", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("billing_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_organization_policies_org_id", "organization_policies", ["org_id"], unique=True)


def downgrade():
    op.drop_index("ix_organization_policies_org_id", table_name="organization_policies")
    op.drop_table("organization_policies")
