from app.models.rag_model import RAGChunk
from app.services import rag_service
from sqlalchemy.dialects import postgresql


def test_rag_model_has_pgvector_compatibility_column():
    assert "embedding_vector" in RAGChunk.__table__.c
    assert "ix_rag_chunks_user_dimension" in {index.name for index in RAGChunk.__table__.indexes}


def test_pgvector_cosine_distance_compiles_for_postgresql():
    expression = RAGChunk.embedding_vector.cosine_distance([0.1, 0.2])
    compiled = str(expression.compile(dialect=postgresql.dialect()))
    assert "<=>" in compiled


def test_postgres_search_branch_is_bounded_and_does_not_load_json_index(app, monkeypatch):
    monkeypatch.setattr(rag_service, "embed_text", lambda _query: [0.1, 0.2, 0.3])
    monkeypatch.setattr(rag_service, "_uses_postgres", lambda: True)
    monkeypatch.setattr(rag_service, "_load_index", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("JSON path used")))
    captured = {}

    def postgres_search(vector, top_k, user_id):
        captured.update(vector=vector, top_k=top_k, user_id=user_id)
        return [{"text": "owned", "filename": "owned.txt", "score": 0.9}]

    monkeypatch.setattr(rag_service, "_search_postgres", postgres_search)
    with app.app_context():
        result = rag_service.search("question", top_k=2, user_id="user-a")
    assert result[0]["text"] == "owned"
    assert captured == {"vector": [0.1, 0.2, 0.3], "top_k": 2, "user_id": "user-a"}


def test_pgvector_migration_enables_extension_and_preserves_json_strategy():
    path = "migrations/versions/20260903_000009_pgvector_rag.py"
    source = open(path, encoding="utf-8").read()
    assert "CREATE EXTENSION IF NOT EXISTS vector" in source
    assert "embedding::text::vector" in source
    assert "embedding_vector vector" in source
