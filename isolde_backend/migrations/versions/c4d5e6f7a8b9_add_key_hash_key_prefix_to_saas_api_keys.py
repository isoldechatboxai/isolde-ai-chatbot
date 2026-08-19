"""Add key_hash and key_prefix to saas_api_keys — Phase 2

Revision ID: c4d5e6f7a8b9
Revises: 2442f1de8168
Create Date: 2026-08-19

PHASE 2 — API-KEY HASH + PREFIX HARDENING (SAAS SYSTEM)

This migration is strictly NON-DESTRUCTIVE:
  * Adds key_hash and key_prefix columns to saas_api_keys.
  * Makes key_secret nullable to allow new secure keys to omit plaintext storage.
  * Does NOT drop any column or table.
  * Does NOT modify existing rows.
"""
from alembic import op
import sqlalchemy as sa

revision = 'c4d5e6f7a8b9'
down_revision = '2442f1de8168'
branch_labels = None
depends_on = None

def upgrade():
    # SQLite requires batch_alter_table for most ALTER COLUMN operations
    with op.batch_alter_table('saas_api_keys', schema=None) as batch_op:
        batch_op.add_column(sa.Column('key_hash', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('key_prefix', sa.String(length=20), nullable=True))
        batch_op.alter_column('key_secret',
                              existing_type=sa.String(length=255),
                              nullable=True)

def downgrade():
    # Note: If new keys were created with key_secret=None, downgrading to
    # nullable=False will fail. This is standard Alembic behavior for
    # schema tightening when data violates the new constraint.
    with op.batch_alter_table('saas_api_keys', schema=None) as batch_op:
        batch_op.alter_column('key_secret',
                              existing_type=sa.String(length=255),
                              nullable=False)
        batch_op.drop_column('key_prefix')
        batch_op.drop_column('key_hash')