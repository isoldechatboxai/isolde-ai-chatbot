# app/services/rag_service.py
"""
Minimal Retrieval-Augmented-Generation store.

This uses a JSON file on disk plus numpy cosine similarity so the project
runs with zero extra infrastructure.

For production scale, swap this module's storage/search internals for
ChromaDB, FAISS, or Pinecone. The function signatures below
(index_document / search) are the integration points used by the app.
"""

import json
import os
import uuid

import numpy as np

from typing import Optional, List, Dict

from flask import current_app

from app.services.provider_router import embed_text

INDEX_FILENAME = "index.json"
DEFAULT_RELEVANCE_THRESHOLD = 0.55


def _index_path():
    store_dir = current_app.config.get("VECTOR_STORE_DIR", "vector_store")
    os.makedirs(store_dir, exist_ok=True)

    return os.path.join(store_dir, INDEX_FILENAME)


def _load_index():
    try:
        path = _index_path()
    except Exception as e:
        current_app.logger.error(f"Failed to resolve RAG index path: {e}")
        return []

    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)

        if not isinstance(records, list):
            current_app.logger.error("RAG index file is corrupted. Expected a JSON list.")
            return []

        return records
    except Exception as e:
        current_app.logger.error(f"Failed to load RAG index: {e}")
        return []


def _save_index(records):
    if not isinstance(records, list):
        records = []

    path = _index_path()
    tmp_path = f"{path}.tmp"

    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False)

        os.replace(tmp_path, path)
    except Exception as e:
        current_app.logger.error(f"Failed to save RAG index: {e}")

        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

        raise


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100):
    chunks = []

    if not text:
        return chunks

    if chunk_size <= 0:
        chunk_size = 800

    if overlap < 0:
        overlap = 0

    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 10)

    start = 0

    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap

    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _extract_pdf_text(file_path: str, filename: str) -> str:
    try:
        import PyPDF2
    except ImportError:
        current_app.logger.error("PyPDF2 is not installed. Run: pip install PyPDF2")
        return ""

    try:
        text_parts = []

        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)

            for page in reader.pages:
                try:
                    extracted = page.extract_text()
                except Exception as page_error:
                    current_app.logger.error(
                        f"Failed to extract a page from {filename}: {page_error}"
                    )
                    continue

                if extracted:
                    text_parts.append(extracted)

        return "\n".join(text_parts)
    except Exception as e:
        current_app.logger.error(f"Failed to extract PDF {filename}: {e}")
        return ""


def _extract_docx_text(file_path: str, filename: str) -> str:
    try:
        import docx
    except ImportError:
        current_app.logger.error(
            "python-docx is not installed. Run: pip install python-docx"
        )
        return ""

    try:
        document = docx.Document(file_path)
        text_parts = []

        for paragraph in document.paragraphs:
            if paragraph.text:
                text_parts.append(paragraph.text)

        for table in document.tables:
            for row in table.rows:
                row_text_parts = []

                for cell in row.cells:
                    if cell.text:
                        row_text_parts.append(cell.text)

                row_text = " | ".join(row_text_parts).strip()

                if row_text:
                    text_parts.append(row_text)

        return "\n".join(text_parts)
    except Exception as e:
        current_app.logger.error(f"Failed to extract DOCX {filename}: {e}")
        return ""


def extract_text_from_file(file_path: str, filename: str) -> str:
    """
    Extract text from supported files.

    Supported:
    - PDF
    - DOCX
    - XLSX
    - TXT
    - CSV
    - Other plain-text files
    """
    if not file_path or not os.path.exists(file_path):
        current_app.logger.error(f"File not found for extraction: {file_path}")
        return ""

    ext = filename.lower().rsplit(".", 1)[-1].strip() if "." in filename else ""

    try:
        if ext == "pdf":
            return _extract_pdf_text(file_path, filename)

        if ext == "docx":
            return _extract_docx_text(file_path, filename)

        if ext == "xlsx":
            try:
                import openpyxl
                wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
                rows_text = []
                for sheet in wb.sheetnames:
                    ws = wb[sheet]
                    rows_text.append(f"[Sheet: {sheet}]")
                    for row in ws.iter_rows(values_only=True):
                        row_values = [str(cell) if cell is not None else "" for cell in row]
                        if any(v.strip() for v in row_values):
                            rows_text.append(" | ".join(row_values))
                wb.close()
                return "\n".join(rows_text)
            except ImportError:
                current_app.logger.error("openpyxl is not installed. Run: pip install openpyxl")
                return f"[XLSX extraction failed. openpyxl not installed. File: {filename}]"
            except Exception as e:
                current_app.logger.error(f"Failed to extract XLSX {filename}: {e}")
                return ""

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        current_app.logger.error(f"Failed to read file {filename}: {e}")
        return ""


def process_and_index_file(file_path: str, filename: str, user_id: Optional[str] = None):
    """
    Extract text from a file and index it.

    Returns the number of successfully indexed chunks.
    """
    text = extract_text_from_file(file_path, filename)

    if not text or not text.strip():
        return 0

    file_id = str(uuid.uuid4())

    return index_document(file_id, filename, text, user_id)


def index_document(file_id: str, filename: str, text: str, user_id: Optional[str] = None):
    """
    Chunk, embed, and store a document's text for later semantic search.
    """
    if not text or not text.strip():
        return 0

    if user_id is not None:
        user_id = str(user_id).strip() or None

    records = _load_index()
    chunks = _chunk_text(text)

    if not chunks:
        return 0

    success_count = 0

    for chunk in chunks:
        try:
            vector = embed_text(chunk)

            if not vector:
                continue

            vector = [float(value) for value in vector]

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
    """
    Return the top_k most relevant chunks for a query, deduplicated.
    """
    if not query or not query.strip():
        return []

    if top_k <= 0:
        return []

    if user_id is not None:
        user_id = str(user_id).strip() or None

    records = _load_index()

    if not records:
        return []

    try:
        query_vector_raw = embed_text(query)
        query_vec = np.array(query_vector_raw, dtype=float).flatten()
    except Exception as e:
        current_app.logger.error(f"Query embedding failed: {e}")
        return []

    if query_vec.size == 0:
        return []

    scored = []
    seen_texts = set()

    for record in records:
        record_user_id = record.get("user_id")

        if record_user_id is not None:
            record_user_id = str(record_user_id).strip() or None

        # Records are private to their exact owner. Legacy records without an
        # owner are intentionally visible only to anonymous legacy flows and
        # must never enter an authenticated tenant's context.
        if record_user_id != user_id:
            continue

        chunk_key = record.get("text", "")[:200]
        if chunk_key in seen_texts:
            continue

        try:
            vec = np.array(record.get("vector"), dtype=float).flatten()
        except Exception:
            continue

        if vec.size == 0:
            continue

        if vec.shape != query_vec.shape:
            continue

        denominator = (np.linalg.norm(query_vec) * np.linalg.norm(vec)) or 1e-9
        similarity = float(np.dot(query_vec, vec) / denominator)

        if similarity > DEFAULT_RELEVANCE_THRESHOLD:
            scored.append((similarity, record))
            seen_texts.add(chunk_key)

    scored.sort(key=lambda item: item[0], reverse=True)

    return [
        {
            "text": record["text"],
            "filename": record["filename"],
            "score": round(score, 3),
        }
        for score, record in scored[:top_k]
    ]


def build_context_block(chunks: List[Dict], max_chars: int = 4000) -> str:
    """Build context block with a hard character limit to respect token budgets."""
    if not chunks:
        return ""

    lines = ["Relevant knowledge base excerpts:"]
    total_length = len(lines[0])

    for chunk in chunks:
        entry = f"- (from {chunk['filename']}, relevance {chunk['score']}): {chunk['text']}"
        if total_length + len(entry) > max_chars:
            break
        lines.append(entry)
        total_length += len(entry)

    return "\n".join(lines) if len(lines) > 1 else ""
