"""
Minimal Retrieval-Augmented-Generation store.

This uses a JSON file on disk + numpy cosine similarity so the project
runs with zero extra infrastructure. For production scale, swap this
module's storage/search internals for ChromaDB, FAISS, or Pinecone —
the function signatures below (index_document / search) are the
integration points the rest of the app calls.
"""
import json
import os
import uuid
import numpy as np
from flask import current_app

from app.services.gemini_service import embed_text

INDEX_FILENAME = "index.json"


def _index_path():
    store_dir = current_app.config["VECTOR_STORE_DIR"]
    os.makedirs(store_dir, exist_ok=True)
    return os.path.join(store_dir, INDEX_FILENAME)


def _load_index():
    path = _index_path()
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_index(records):
    with open(_index_path(), "w", encoding="utf-8") as f:
        json.dump(records, f)


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return [c.strip() for c in chunks if c.strip()]


def index_document(file_id: str, filename: str, text: str, user_id: str | None = None):
    """Chunk, embed, and store a document's text for later semantic search."""
    records = _load_index()
    chunks = _chunk_text(text)

    for chunk in chunks:
        try:
            vector = embed_text(chunk)
        except Exception as e:
            current_app.logger.error(f"Embedding failed for {filename}: {e}")
            continue
        records.append({
            "id": str(uuid.uuid4()),
            "file_id": file_id,
            "filename": filename,
            "user_id": user_id,
            "text": chunk,
            "vector": vector,
        })

    _save_index(records)
    return len(chunks)


def search(query: str, top_k: int = 4, user_id: str | None = None) -> list[dict]:
    """Return the top_k most relevant chunks for a query."""
    records = _load_index()
    if not records:
        return []

    try:
        query_vec = np.array(embed_text(query))
    except Exception as e:
        current_app.logger.error(f"Query embedding failed: {e}")
        return []

    scored = []
    for r in records:
        if user_id and r.get("user_id") and r["user_id"] != user_id:
            continue  # keep per-user documents private
        vec = np.array(r["vector"])
        denom = (np.linalg.norm(query_vec) * np.linalg.norm(vec)) or 1e-9
        similarity = float(np.dot(query_vec, vec) / denom)
        scored.append((similarity, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"text": r["text"], "filename": r["filename"], "score": round(s, 3)}
        for s, r in scored[:top_k]
        if s > 0.55  # relevance threshold; tune as needed
    ]


def build_context_block(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    lines = ["Relevant knowledge base excerpts:"]
    for c in chunks:
        lines.append(f"- (from {c['filename']}, relevance {c['score']}): {c['text']}")
    return "\n".join(lines)
