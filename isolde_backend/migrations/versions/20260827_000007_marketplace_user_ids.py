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
    inspector = sa.inspect(op.get_bind())
    developer_column = next(column for column in inspector.get_columns("developers") if column["name"] == "user_id")
    developer_indexes = {index["name"] for index in inspector.get_indexes("developers")}
    if not isinstance(developer_column["type"], sa.String):
        with op.batch_alter_table("developers") as batch:
            batch.alter_column("user_id", existing_type=developer_column["type"], type_=sa.String(length=36), existing_nullable=False, postgresql_using="user_id::text")
    if "ix_developers_user_id" not in developer_indexes:
        op.create_index("ix_developers_user_id", "developers", ["user_id"], unique=False)
    plugin_column = next(column for column in inspector.get_columns("plugin_installations") if column["name"] == "user_id")
    plugin_indexes = {index["name"] for index in inspector.get_indexes("plugin_installations")}
    if not isinstance(plugin_column["type"], sa.String):
        with op.batch_alter_table("plugin_installations") as batch:
            batch.alter_column("user_id", existing_type=plugin_column["type"], type_=sa.String(length=36), existing_nullable=True, nullable=True, postgresql_using="user_id::text")
    if "ix_plugin_installations_user_id" not in plugin_indexes:
        op.create_index("ix_plugin_installations_user_id", "plugin_installations", ["user_id"], unique=False)


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
