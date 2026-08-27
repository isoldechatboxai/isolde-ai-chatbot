"""Align marketplace ownership columns with string user identities.

Revision ID: 20260827_000007
Revises: 20260827_000006
"""
from alembic import op
import sqlalchemy as sa

revision = "20260827_000007"
down_revision = "20260827_000006"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("developers") as batch:
        batch.alter_column(
            "user_id", existing_type=sa.Integer(), type_=sa.String(length=36),
            existing_nullable=False, postgresql_using="user_id::text",
        )
        batch.create_index("ix_developers_user_id", ["user_id"], unique=False)
    with op.batch_alter_table("plugin_installations") as batch:
        batch.alter_column(
            "user_id", existing_type=sa.Integer(), type_=sa.String(length=36),
            existing_nullable=True, nullable=True, postgresql_using="user_id::text",
        )
        batch.create_index("ix_plugin_installations_user_id", ["user_id"], unique=False)


def downgrade():
    with op.batch_alter_table("plugin_installations") as batch:
        batch.drop_index("ix_plugin_installations_user_id")
        batch.alter_column(
            "user_id", existing_type=sa.String(length=36), type_=sa.Integer(),
            existing_nullable=True, nullable=True, postgresql_using="user_id::integer",
        )
    with op.batch_alter_table("developers") as batch:
        batch.drop_index("ix_developers_user_id")
        batch.alter_column(
            "user_id", existing_type=sa.String(length=36), type_=sa.Integer(),
            existing_nullable=False, postgresql_using="user_id::integer",
        )
