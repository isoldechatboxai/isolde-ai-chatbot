"""
Extracts plain text from uploaded documents so it can be chunked
and indexed by rag_service. Add OCR (e.g. pytesseract) for scanned
PDFs/images if needed later.
"""
import os
import csv
import PyPDF2
import docx
import pandas as pd


def extract_text(filepath: str, file_type: str) -> str:
    file_type = file_type.lower()

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
        reader = PyPDF2.PdfReader(f)
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
