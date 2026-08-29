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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    def table_has_rows(name):
        return bind.execute(sa.text(f'SELECT 1 FROM "{name}" LIMIT 1')).first() is not None

    def ensure_columns(name, expected):
        columns = {column["name"]: column for column in inspector.get_columns(name)}
        missing = [column for column in expected if column.name not in columns]
        if missing and table_has_rows(name):
            raise RuntimeError(
                f"Cannot safely reconcile populated {name}: missing required columns "
                + ", ".join(column.name for column in missing)
            )
        for column in missing:
            op.add_column(name, column)
        columns = {column["name"]: column for column in sa.inspect(bind).get_columns(name)}
        for expected_column in expected:
            actual = columns[expected_column.name]
            if actual["nullable"] != expected_column.nullable:
                raise RuntimeError(
                    f"Incompatible {name}.{expected_column.name} nullability; "
                    "manual data-preserving reconciliation is required."
                )

    document_columns = (
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    chunk_columns = (
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("embedding_provider", sa.String(length=32), nullable=True),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    if "rag_documents" not in existing_tables:
        op.create_table(
        "rag_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    else:
        ensure_columns("rag_documents", document_columns)

    inspector = sa.inspect(bind)
    document_indexes = {index["name"] for index in inspector.get_indexes("rag_documents")}
    if "ix_rag_documents_user_id" not in document_indexes:
        op.create_index("ix_rag_documents_user_id", "rag_documents", ["user_id"])

    if "rag_chunks" not in existing_tables:
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
    else:
        ensure_columns("rag_chunks", chunk_columns)

    inspector = sa.inspect(bind)
    chunk_indexes = {index["name"] for index in inspector.get_indexes("rag_chunks")}
    if "ix_rag_chunks_document_id" not in chunk_indexes:
        op.create_index("ix_rag_chunks_document_id", "rag_chunks", ["document_id"])
    if "ix_rag_chunks_user_id" not in chunk_indexes:
        op.create_index("ix_rag_chunks_user_id", "rag_chunks", ["user_id"])


def downgrade():
    op.drop_index("ix_rag_chunks_user_id", table_name="rag_chunks")
    op.drop_index("ix_rag_chunks_document_id", table_name="rag_chunks")
    op.drop_table("rag_chunks")
    op.drop_index("ix_rag_documents_user_id", table_name="rag_documents")
    op.drop_table("rag_documents")
