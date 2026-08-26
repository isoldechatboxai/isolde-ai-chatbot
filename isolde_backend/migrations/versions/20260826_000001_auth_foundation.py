"""Add secure authentication sessions, tokens, and OAuth identities.

Revision ID: 20260826_000001
Revises: 20260101_000001
"""
from alembic import op
import sqlalchemy as sa

revision = "20260826_000001"
down_revision = "20260101_000001"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    def create_table_if_missing(name, *columns_and_constraints):
        if name in existing_tables:
            return False
        op.create_table(name, *columns_and_constraints)
        existing_tables.add(name)
        return True

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("password_hash", existing_type=sa.String(length=255), nullable=True)

    auth_sessions_created = create_table_if_missing(
        "auth_sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
    )
    if auth_sessions_created:
        op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])

    auth_tokens_created = create_table_if_missing(
        "auth_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )
    if auth_tokens_created:
        op.create_index("ix_auth_tokens_user_id", "auth_tokens", ["user_id"])
        op.create_index("ix_auth_tokens_purpose", "auth_tokens", ["purpose"])
        op.create_index("ix_auth_tokens_token_hash", "auth_tokens", ["token_hash"], unique=True)

    oauth_accounts_created = create_table_if_missing(
        "oauth_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("provider_email", sa.String(length=180), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_oauth_provider_subject"),
        sa.UniqueConstraint("user_id", "provider", name="uq_oauth_user_provider"),
    )
    if oauth_accounts_created:
        op.create_index("ix_oauth_accounts_user_id", "oauth_accounts", ["user_id"])

    revoked_tokens_created = create_table_if_missing(
        "revoked_tokens",
        sa.Column("jti", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    if revoked_tokens_created:
        op.create_index("ix_revoked_tokens_user_id", "revoked_tokens", ["user_id"])

    # Align legacy feature ownership columns with the UUID user primary key.
    for table_name, column_name in (
        ("saas_api_keys", "user_id"),
        ("ai_insights", "user_id"),
        ("ai_recommendations", "user_id"),
        ("learning_profiles", "user_id"),
        ("organizations", "owner_id"),
        ("organization_members", "user_id"),
        ("tasks", "user_id"),
    ):
        column = next(item for item in sa.inspect(op.get_bind()).get_columns(table_name) if item["name"] == column_name)
        if not isinstance(column["type"], sa.String):
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.alter_column(
                    column_name, existing_type=column["type"], type_=sa.String(length=36),
                    nullable=False,
                )

    for table_name in ("voice_profiles", "audio_settings", "voice_sessions"):
        column = next(item for item in sa.inspect(op.get_bind()).get_columns(table_name) if item["name"] == "user_id")
        if not isinstance(column["type"], sa.String):
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.alter_column(
                    "user_id", existing_type=column["type"], type_=sa.String(length=36), nullable=True,
                )

    with op.batch_alter_table("saas_api_keys") as batch_op:
        batch_op.alter_column("key_secret", existing_type=sa.String(length=255), nullable=True)

    for table_name in ("calendar_events", "notes", "bookmarks", "meetings"):
        columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table_name)}
        if "user_id" not in columns:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.add_column(sa.Column("user_id", sa.String(length=36), nullable=True))
                batch_op.create_index(f"ix_{table_name}_user_id", ["user_id"])


def downgrade():
    with op.batch_alter_table("meetings") as batch_op:
        batch_op.drop_index("ix_meetings_user_id")
        batch_op.drop_column("user_id")
    with op.batch_alter_table("bookmarks") as batch_op:
        batch_op.drop_index("ix_bookmarks_user_id")
        batch_op.drop_column("user_id")
    with op.batch_alter_table("notes") as batch_op:
        batch_op.drop_index("ix_notes_user_id")
        batch_op.drop_column("user_id")
    with op.batch_alter_table("calendar_events") as batch_op:
        batch_op.drop_index("ix_calendar_events_user_id")
        batch_op.drop_column("user_id")
    for table_name, column_name, nullable in (
        ("tasks", "user_id", True),
        ("organization_members", "user_id", False),
        ("organizations", "owner_id", False),
        ("learning_profiles", "user_id", False),
        ("ai_recommendations", "user_id", False),
        ("ai_insights", "user_id", False),
        ("saas_api_keys", "user_id", False),
        ("voice_sessions", "user_id", True),
        ("audio_settings", "user_id", True),
        ("voice_profiles", "user_id", True),
    ):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                column_name, existing_type=sa.String(length=36), type_=sa.Integer(), nullable=nullable,
            )
    op.drop_index("ix_revoked_tokens_user_id", table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
    op.drop_index("ix_oauth_accounts_user_id", table_name="oauth_accounts")
    op.drop_table("oauth_accounts")
    op.drop_index("ix_auth_tokens_token_hash", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_purpose", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_user_id", table_name="auth_tokens")
    op.drop_table("auth_tokens")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("password_hash", existing_type=sa.String(length=255), nullable=False)
