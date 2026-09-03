"""Add pgvector storage for RAG chunk embeddings.

Revision ID: 20260903_000009
Revises: 20260827_000008

The JSON embedding column is retained as a non-destructive compatibility
record. Valid numeric legacy arrays are copied into pgvector. Rows that do
not meet that strict shape remain preserved but require re-embedding before
they participate in PostgreSQL retrieval.
"""
from alembic import op
import sqlalchemy as sa


revision = "20260903_000009"
down_revision = "20260827_000008"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("rag_chunks")}

    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        if "embedding_vector" not in columns:
            op.execute("ALTER TABLE rag_chunks ADD COLUMN embedding_vector vector")
        # Conversion is intentionally strict. Invalid or historically malformed
        # JSON is retained in ``embedding`` and must be safely re-embedded,
        # rather than making migration success depend on invented vectors.
        op.execute("""
            UPDATE rag_chunks
               SET embedding_vector = embedding::text::vector
             WHERE embedding_vector IS NULL
               AND jsonb_typeof(embedding::jsonb) = 'array'
               AND jsonb_array_length(embedding::jsonb) > 0
               AND NOT EXISTS (
                   SELECT 1
                     FROM jsonb_array_elements(embedding::jsonb) AS value
                    WHERE jsonb_typeof(value) <> 'number'
               )
        """)
    elif "embedding_vector" not in columns:
        # SQLite is used only by the isolated test suite. Keeping a JSON
        # representation lets the ORM model load while production uses vector.
        op.add_column("rag_chunks", sa.Column("embedding_vector", sa.JSON(), nullable=True))

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("rag_chunks")}
    if "ix_rag_chunks_user_dimension" not in indexes:
        op.create_index("ix_rag_chunks_user_dimension", "rag_chunks", ["user_id", "embedding_dimension"])


def downgrade():
    bind = op.get_bind()
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("rag_chunks")}
    if "ix_rag_chunks_user_dimension" in indexes:
        op.drop_index("ix_rag_chunks_user_dimension", table_name="rag_chunks")
    columns = {column["name"] for column in sa.inspect(bind).get_columns("rag_chunks")}
    if "embedding_vector" in columns:
        op.drop_column("rag_chunks", "embedding_vector")
    # Do not drop the shared PostgreSQL extension: other schemas may use it.
