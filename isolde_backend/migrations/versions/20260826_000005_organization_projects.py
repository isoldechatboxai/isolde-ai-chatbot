"""Add tenant-scoped project sharing.

Revision ID: 20260826_000005
Revises: 20260826_000004
"""
from alembic import op
import sqlalchemy as sa

revision = "20260826_000005"
down_revision = "20260826_000004"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "organization_projects" in inspector.get_table_names():
        required = {"id", "org_id", "project_id", "shared_by", "access_level", "created_at"}
        if not required <= {column["name"] for column in inspector.get_columns("organization_projects")}:
            raise RuntimeError("Existing organization_projects schema is incompatible with this migration.")
        return
    op.create_table(
        "organization_projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shared_by", sa.String(length=36), nullable=False),
        sa.Column("access_level", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("project_id"),
    )
    op.create_index("ix_organization_projects_org_id", "organization_projects", ["org_id"])
    op.create_index("ix_organization_projects_project_id", "organization_projects", ["project_id"], unique=True)


def downgrade():
    op.drop_index("ix_organization_projects_project_id", table_name="organization_projects")
    op.drop_index("ix_organization_projects_org_id", table_name="organization_projects")
    op.drop_table("organization_projects")
