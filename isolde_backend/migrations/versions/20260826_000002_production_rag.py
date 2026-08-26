"""Add transactional RAG document and embedding storage.

Revision ID: 20260826_000002
Revises: 20260826_000001
"""
from alembic import op
import sqlalchemy as sa

revision = "20260826_000002"
down_revision = "20260826_000001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rag_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_rag_documents_user_id", "rag_documents", ["user_id"])
    op.create_table(
        "rag_chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("rag_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("embedding_provider", sa.String(length=32), nullable=True),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("document_id", "position", name="uq_rag_chunk_document_position"),
        sa.CheckConstraint("embedding_dimension > 0", name="ck_rag_chunk_embedding_dimension"),
    )
    op.create_index("ix_rag_chunks_document_id", "rag_chunks", ["document_id"])
    op.create_index("ix_rag_chunks_user_id", "rag_chunks", ["user_id"])


def downgrade():
    op.drop_index("ix_rag_chunks_user_id", table_name="rag_chunks")
    op.drop_index("ix_rag_chunks_document_id", table_name="rag_chunks")
    op.drop_table("rag_chunks")
    op.drop_index("ix_rag_documents_user_id", table_name="rag_documents")
    op.drop_table("rag_documents")
