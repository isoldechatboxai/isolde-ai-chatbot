"""
Extracts plain text from uploaded documents so it can be chunked
and indexed by rag_service. Add OCR (e.g. pytesseract) for scanned
PDFs/images if needed later.
"""
import os
import csv
import zipfile
import pypdf
import docx
import pandas as pd


def validate_document_container(filepath, file_type):
    """Reject Office archives whose expanded data can exhaust a worker."""
    if file_type not in {"docx", "xlsx"}:
        return
    with zipfile.ZipFile(filepath) as archive:
        entries = archive.infolist()
        if len(entries) > 2000 or sum(item.file_size for item in entries) > 50 * 1024 * 1024:
            raise ValueError("Document archive exceeds extraction limits.")
        if any(item.file_size > 10 * 1024 * 1024 and item.file_size > max(item.compress_size, 1) * 200
               for item in entries):
            raise ValueError("Document archive exceeds compression limits.")


def extract_text(filepath: str, file_type: str) -> str:
    file_type = file_type.lower()
    validate_document_container(filepath, file_type)

    if file_type == "pdf":
        return _extract_pdf(filepath)
    if file_type == "docx":
        return _extract_docx(filepath)
    if file_type == "txt":
        return _extract_txt(filepath)
    if file_type == "csv":
        return _extract_csv(filepath)
    if file_type == "xlsx":
        return _extract_xlsx(filepath)

    # images: no text extraction here — route to Gemini Vision instead
    return ""


def _extract_pdf(filepath: str) -> str:
    text = []
    with open(filepath, "rb") as f:
        reader = pypdf.PdfReader(f)
        for page in reader.pages:
            content = page.extract_text() or ""
            text.append(content)
    return "\n".join(text)


def _extract_docx(filepath: str) -> str:
    document = docx.Document(filepath)
    return "\n".join(p.text for p in document.paragraphs)


def _extract_txt(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _extract_csv(filepath: str) -> str:
    rows = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(", ".join(row))
    return "\n".join(rows)


def _extract_xlsx(filepath: str) -> str:
    dfs = pd.read_excel(filepath, sheet_name=None)
    parts = []
    for sheet_name, df in dfs.items():
        parts.append(f"Sheet: {sheet_name}")
        parts.append(df.to_string(index=False))
    return "\n".join(parts)
