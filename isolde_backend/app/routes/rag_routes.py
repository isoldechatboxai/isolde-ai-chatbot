# app/routes/rag_routes.py
import os
import uuid

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from app.services.rag_service import (
    process_and_index_file,
    list_documents as list_owned_documents,
    get_document as get_owned_document,
    delete_document as delete_owned_document,
)

rag_bp = Blueprint("rag", __name__)

RAG_ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "csv", "xlsx"}
# The temporary name has a 32-character UUID plus an underscore prefix.  Keep
# the client-visible portion below Windows' 255-character component limit as
# well as the 255-character database column limit.
RAG_MAX_FILENAME_LENGTH = 220


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

    # Keep the database-visible filename and temporary path independent of
    # client-controlled path syntax.  ``secure_filename`` can legitimately
    # produce an empty value for a filename made only of unsafe characters.
    if "\x00" in original_filename:
        return jsonify({"status": "error", "message": "Invalid filename."}), 400
    safe_name = secure_filename(original_filename)
    if not safe_name:
        return jsonify({"status": "error", "message": "Invalid filename."}), 400
    if len(safe_name) > RAG_MAX_FILENAME_LENGTH:
        stem, extension = os.path.splitext(safe_name)
        safe_name = stem[: RAG_MAX_FILENAME_LENGTH - len(extension)] + extension

    if not _allowed_rag_file(safe_name):
        allowed_str = ", ".join(sorted(RAG_ALLOWED_EXTENSIONS))
        return jsonify({
            "status": "error",
            "message": f"File type not supported. Allowed types: {allowed_str}"
        }), 400

    file_path = None

    try:
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
        indexed_chunks = process_and_index_file(file_path, safe_name, user_id)

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
            "RAG file indexed: %s (%s chunks) by user: %s", safe_name, indexed_chunks, user_id
        )

        try:
            os.remove(file_path)
            file_path = None
        except OSError as cleanup_error:
            current_app.logger.warning("Indexed RAG upload cleanup failed: %s", cleanup_error)

        return jsonify({
            "status": "success",
            "message": "File uploaded and indexed successfully. You can now ask questions about this document.",
            "filename": original_filename,
            "chunks_indexed": indexed_chunks
        }), 200

    except Exception as e:
        current_app.logger.error("RAG indexing error for %s: %s", safe_name, e)

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

    return jsonify({
        "documents": [
            {
                "id": document.id,
                "filename": document.filename,
                "chunks": document.chunk_count,
                "status": "indexed",
                "created_at": document.created_at.isoformat() if document.created_at else None,
            }
            for document in list_owned_documents(user_id)
        ]
    })


@rag_bp.route("/api/rag/document/<file_id>", methods=["GET"])
@jwt_required()
def get_document(file_id):
    document = get_owned_document(file_id, str(get_jwt_identity()))
    if not document:
        return jsonify({"error": "Document not found."}), 404
    return jsonify({"document": {
        "id": document.id,
        "filename": document.filename,
        "chunks": document.chunk_count,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "status": "indexed",
    }}), 200


@rag_bp.route("/api/rag/document/<file_id>", methods=["DELETE"])
@jwt_required()
def delete_document(file_id):
    user_id = str(get_jwt_identity())

    deleted = delete_owned_document(file_id, user_id)
    if not deleted:
        return jsonify({"error": "Document not found."}), 404

    return jsonify({
        "message": "Document deleted successfully."
    })
