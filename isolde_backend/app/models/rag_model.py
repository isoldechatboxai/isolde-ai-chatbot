import uuid
from datetime import datetime, timezone

from app.extensions import db
from pgvector.sqlalchemy import Vector
from sqlalchemy.types import TypeDecorator


def _uuid():
    return str(uuid.uuid4())


class EmbeddingVector(TypeDecorator):
    """pgvector comparator on PostgreSQL, JSON storage in SQLite tests."""

    impl = Vector
    cache_ok = True
    comparator_factory = Vector.comparator_factory

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector())
        return dialect.type_descriptor(db.JSON())


class RAGDocument(db.Model):
    __tablename__ = "rag_documents"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    chunk_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class RAGChunk(db.Model):
    __tablename__ = "rag_chunks"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    document_id = db.Column(db.String(36), db.ForeignKey("rag_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    embedding = db.Column(db.JSON, nullable=False)
    # ``Vector()`` deliberately has no fixed dimension: supported embedding
    # providers/models can have different dimensions. Queries always constrain
    # embedding_dimension before calculating pgvector distance, so dimensions
    # are never mixed.
    embedding_vector = db.Column(EmbeddingVector(), nullable=True)
    embedding_provider = db.Column(db.String(32), nullable=True)
    embedding_model = db.Column(db.String(128), nullable=True)
    embedding_dimension = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("document_id", "position", name="uq_rag_chunk_document_position"),
        db.CheckConstraint("embedding_dimension > 0", name="ck_rag_chunk_embedding_dimension"),
        db.Index("ix_rag_chunks_user_dimension", "user_id", "embedding_dimension"),
    )
