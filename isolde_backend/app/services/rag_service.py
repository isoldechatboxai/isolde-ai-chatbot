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
from typing import Optional, List, Dict
from flask import current_app

from app.services.gemini_service import embed_text

INDEX_FILENAME = "index.json"


def _index_path():
    # ஃபால்பேக் (Fallback) ஃபோல்டர் நேம் சேர்க்கப்பட்டுள்ளது
    store_dir = current_app.config.get("VECTOR_STORE_DIR", "vector_store")
    os.makedirs(store_dir, exist_ok=True)
    return os.path.join(store_dir, INDEX_FILENAME)


def _load_index():
    path = _index_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


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


# 🌟 NEW: PDF மற்றும் TXT ஃபைல்களைப் படிக்க உதவும் பிரத்தியேக பங்கஷன்
def extract_text_from_file(file_path: str, filename: str) -> str:
    """Helper to extract text from files (TXT, PDF, etc.)"""
    ext = filename.lower().split('.')[-1]
    text = ""
    try:
        if ext == 'pdf':
            try:
                import PyPDF2
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        extracted = page.extract_text()
                        if extracted:
                            text += extracted + "\n"
            except ImportError:
                current_app.logger.error("PyPDF2 is not installed. Run: pip install PyPDF2")
                text = f"[PDF extraction failed. PyPDF2 not installed. File: {filename}]"
        else:
            # Default to reading as plain text for TXT, CSV, etc.
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
    except Exception as e:
        current_app.logger.error(f"Failed to read file {filename}: {e}")
        
    return text


# 🌟 NEW: Route-ல் இருந்து நேரடியாக கால் செய்ய உதவும் Wrapper
def process_and_index_file(file_path: str, filename: str, user_id: Optional[str] = None):
    """Extracts text from a file and indexes it."""
    text = extract_text_from_file(file_path, filename)
    file_id = str(uuid.uuid4())
    return index_document(file_id, filename, text, user_id)


def index_document(file_id: str, filename: str, text: str, user_id: Optional[str] = None):
    """Chunk, embed, and store a document's text for later semantic search."""
    if not text.strip():
        return 0
        
    records = _load_index()
    chunks = _chunk_text(text)
    success_count = 0

    for chunk in chunks:
        try:
            vector = embed_text(chunk)
            records.append({
                "id": str(uuid.uuid4()),
                "file_id": file_id,
                "filename": filename,
                "user_id": user_id,
                "text": chunk,
                "vector": vector,
            })
            success_count += 1
        except Exception as e:
            current_app.logger.error(f"Embedding failed for {filename}: {e}")
            continue

    if success_count > 0:
        _save_index(records)
        
    return success_count


def search(query: str, top_k: int = 4, user_id: Optional[str] = None) -> List[Dict]:
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
        # Check matching user_id to ensure private data stays private
        if user_id and r.get("user_id") and str(r["user_id"]) != str(user_id):
            continue 
            
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


def build_context_block(chunks: List[Dict]) -> str:
    if not chunks:
        return ""
    lines = ["Relevant knowledge base excerpts:"]
    for c in chunks:
        lines.append(f"- (from {c['filename']}, relevance {c['score']}): {c['text']}")
    return "\n".join(lines)