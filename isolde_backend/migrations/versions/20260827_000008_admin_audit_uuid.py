"""Add UUID actor identity to admin audit records.

Revision ID: 20260827_000008
Revises: 20260827_000007
"""
from alembic import op
import sqlalchemy as sa

revision = "20260827_000008"
down_revision = "20260827_000007"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("enterprise_audit_logs")}
    if "actor_user_id" in columns:
        return
    with op.batch_alter_table("enterprise_audit_logs") as batch:
        batch.add_column(sa.Column("actor_user_id", sa.String(length=36), nullable=True))
        batch.create_index("ix_enterprise_audit_logs_actor_user_id", ["actor_user_id"], unique=False)


def downgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("enterprise_audit_logs")}
    if "actor_user_id" not in columns:
        return
    with op.batch_alter_table("enterprise_audit_logs") as batch:
        batch.drop_index("ix_enterprise_audit_logs_actor_user_id")
        batch.drop_column("actor_user_id")
