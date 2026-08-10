# app/routes/rag_routes.py
import os
import uuid

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from app.services.rag_service import (
    process_and_index_file,
    _load_index,
    _save_index
)

rag_bp = Blueprint("rag", __name__)

RAG_ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "csv", "xlsx"}


def _allowed_rag_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in RAG_ALLOWED_EXTENSIONS
    )


@rag_bp.route("/api/rag/upload", methods=["POST"], strict_slashes=False)
@jwt_required()
def upload_rag_file():
    user_id = get_jwt_identity()

    if not user_id:
        return jsonify({
            "status": "error",
            "message": "Authentication required to upload documents."
        }), 401

    if "file" not in request.files:
        return jsonify({
            "status": "error",
            "message": "No file part in the request."
        }), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({
            "status": "error",
            "message": "No file selected for upload."
        }), 400

    original_filename = file.filename

    if not _allowed_rag_file(original_filename):
        allowed_str = ", ".join(sorted(RAG_ALLOWED_EXTENSIONS))
        return jsonify({
            "status": "error",
            "message": f"File type not supported. Allowed types: {allowed_str}"
        }), 400

    file_path = None

    try:
        safe_name = secure_filename(original_filename)
        unique_name = f"{uuid.uuid4().hex}_{safe_name}"

        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        os.makedirs(upload_folder, exist_ok=True)

        file_path = os.path.join(upload_folder, unique_name)
        file.save(file_path)
    except Exception as e:
        current_app.logger.error(f"RAG file save error: {e}")
        return jsonify({
            "status": "error",
            "message": "Failed to save the uploaded file."
        }), 500

    try:
        indexed_chunks = process_and_index_file(file_path, original_filename, user_id)

        if indexed_chunks == 0:
            try:
                os.remove(file_path)
            except Exception:
                pass

            return jsonify({
                "status": "error",
                "message": "File uploaded but no indexable text was found. The file may be empty or unreadable."
            }), 422

        current_app.logger.info(
            f"RAG file indexed: {original_filename} ({indexed_chunks} chunks) by user: {user_id}"
        )

        return jsonify({
            "status": "success",
            "message": "File uploaded and indexed successfully. You can now ask questions about this document.",
            "filename": original_filename,
            "chunks_indexed": indexed_chunks
        }), 200

    except Exception as e:
        current_app.logger.error(f"RAG indexing error for {original_filename}: {e}")

        if file_path:
            try:
                os.remove(file_path)
            except Exception:
                pass

        return jsonify({
            "status": "error",
            "message": "File was uploaded but indexing failed. Please try again."
        }), 500


@rag_bp.route("/api/rag/documents", methods=["GET"])
@jwt_required()
def list_documents():
    user_id = str(get_jwt_identity())

    records = _load_index()

    docs = {}

    for record in records:
        if str(record.get("user_id")) != user_id:
            continue

        file_id = record["file_id"]

        if file_id not in docs:
            docs[file_id] = {
                "id": file_id,
                "filename": record["filename"]
            }

    return jsonify({
        "documents": list(docs.values())
    })


@rag_bp.route("/api/rag/document/<file_id>", methods=["DELETE"])
@jwt_required()
def delete_document(file_id):
    user_id = str(get_jwt_identity())

    records = _load_index()

    new_records = [
        r for r in records
        if not (
            r["file_id"] == file_id and
            str(r.get("user_id")) == user_id
        )
    ]

    _save_index(new_records)

    return jsonify({
        "message": "Document deleted successfully."
    })