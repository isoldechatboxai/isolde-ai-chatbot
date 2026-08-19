"""baseline current schema

Revision ID: 2442f1de8168
Revises:
Create Date: 2026-08-18 00:00:00.000000

This is a NO-OP baseline migration.

The existing database already contains the current schema.
This migration establishes the Alembic baseline without modifying,
dropping, creating, or altering any database table.
"""

# Revision identifiers, used by Alembic.
revision = "2442f1de8168"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """
    Establish the baseline without changing the existing database schema.
    """
    pass


def downgrade():
    """
    No schema changes are associated with this baseline revision.
    """
    pass