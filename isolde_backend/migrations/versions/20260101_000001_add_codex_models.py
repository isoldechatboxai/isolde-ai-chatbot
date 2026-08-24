"""Add Codex Project Engineering models

Revision ID: 20260101_000001
Revises: 
Create Date: 2026-01-01 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260101_000001'
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade():
    # CodexProject
    op.create_table(
        'codex_projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='Active'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_codex_projects_user_id'), 'codex_projects', ['user_id'], unique=False)
    op.create_index(op.f('ix_codex_projects_workspace_id'), 'codex_projects', ['workspace_id'], unique=False)

    # CodexProjectFile
    op.create_table(
        'codex_project_files',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_content', sa.Text(), nullable=False),
        sa.Column('file_type', sa.String(length=50), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('last_modified_by', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['codex_projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'file_path', name='uq_project_file_path')
    )
    op.create_index(op.f('ix_codex_project_files_project_id'), 'codex_project_files', ['project_id'], unique=False)

    # CodexTask
    op.create_table(
        'codex_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('instruction', sa.Text(), nullable=False),
        sa.Column('ai_plan', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('validation_output', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['codex_projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_codex_tasks_project_id'), 'codex_tasks', ['project_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_codex_tasks_project_id'), table_name='codex_tasks')
    op.drop_table('codex_tasks')
    op.drop_index(op.f('ix_codex_project_files_project_id'), table_name='codex_project_files')
    op.drop_table('codex_project_files')
    op.drop_index(op.f('ix_codex_projects_workspace_id'), table_name='codex_projects')
    op.drop_index(op.f('ix_codex_projects_user_id'), table_name='codex_projects')
    op.drop_table('codex_projects')
