# app/routes/upload_routes.py

import os
import uuid
from io import BytesIO
import mimetypes
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify, current_app, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.uploaded_file import UploadedFile
from app.services.file_service import extract_text
from app.services.provider_router import analyze_image
from app.utils.validators import allowed_file
from app.utils.logger import log_event

from app.services.rag_service import index_document
from app.services.storage_service import get_storage, StorageNotConfigured

upload_bp = Blueprint("upload", __name__)

IMAGE_TYPES = {"png", "jpg", "jpeg"}
MIME_MAP = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}


@upload_bp.route("/upload", methods=["POST"])
@jwt_required()
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request."}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    allowed = current_app.config["ALLOWED_EXTENSIONS"]

    if not allowed_file(file.filename, allowed):
        return jsonify({"error": f"File type not allowed. Allowed: {sorted(allowed)}"}), 400

    # Safely handle secure_filename stripping the extension dot
    filename = secure_filename(file.filename)
    if "." in filename:
        file_type = filename.rsplit(".", 1)[1].lower()
    else:
        # Fallback to the original filename's extension if secure_filename stripped the dot
        file_type = file.filename.rsplit(".", 1)[-1].lower()
        filename = f"{filename}.{file_type}" if filename else f"file.{file_type}"

    user_id = str(get_jwt_identity())
    record_id = str(uuid.uuid4())
    unique_name = f"incoming_{record_id}_{filename}"
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_name)
    os.makedirs(current_app.config["UPLOAD_FOLDER"], exist_ok=True)
    file.save(save_path)
    question = request.form.get("question", "").strip()
    object_key = f"users/{user_id}/{record_id}/{filename}"

    record = UploadedFile(
        id=record_id,
        user_id=user_id,
        filename=filename,
        stored_path=object_key,
        file_type=file_type,
    )

    # --- Images: answer directly via Gemini Vision, skip text indexing ---
    answer = None
    if file_type in IMAGE_TYPES:
        max_size = current_app.config.get("MAX_CONTENT_LENGTH")
        if max_size and os.path.getsize(save_path) > max_size:
            os.remove(save_path)
            return jsonify({"error": "Image file size exceeds the configured limit."}), 413
        if question:
            try:
                with open(save_path, "rb") as image_file:
                    answer = analyze_image(image_file.read(), MIME_MAP[file_type], question)
            except Exception as error:
                os.remove(save_path)
                current_app.logger.error("Image analysis failed: %s", error)
                return jsonify({"error": "Image analysis failed."}), 502
    else:
        try:
            text = extract_text(save_path, file_type)
        except Exception as error:
            os.remove(save_path)
            current_app.logger.error("Text extraction failed for %s: %s", filename, error)
            return jsonify({"error": "Could not extract text from this file."}), 422
        record.extracted_chars = len(text)

    storage = None
    metadata_committed = False
    try:
        storage = get_storage()
        storage.put_file(
            object_key, save_path,
            MIME_MAP.get(file_type) or mimetypes.guess_type(filename)[0] or "application/octet-stream",
        )
        if os.path.exists(save_path):
            os.remove(save_path)
        db.session.add(record)
        db.session.commit()
        metadata_committed = True
        if file_type not in IMAGE_TYPES and text.strip():
            record.indexed = index_document(record.id, filename, text, user_id) > 0
            db.session.commit()
    except StorageNotConfigured as error:
        db.session.rollback()
        if os.path.exists(save_path):
            os.remove(save_path)
        current_app.logger.error("Upload storage is not configured: %s", error)
        return jsonify({"error": "File storage is not configured."}), 503
    except Exception as error:
        db.session.rollback()
        if metadata_committed:
            try:
                db.session.delete(record)
                db.session.commit()
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Failed to clean up upload metadata after processing failure.")
        if os.path.exists(save_path):
            os.remove(save_path)
        if storage:
            try:
                storage.delete(object_key)
            except Exception:
                current_app.logger.exception("Failed to clean up object after upload failure.")
        current_app.logger.error("File upload failed: %s", error)
        return jsonify({"error": "File upload failed."}), 500

    log_event(current_app, "FILE_UPLOAD", f"{filename} ({file_type})", user_id)
    payload = {"message": "File uploaded successfully.", "file": record.to_dict()}
    if answer is not None:
        payload.update({"message": "Image analyzed.", "answer": answer})
    elif file_type in IMAGE_TYPES:
        payload["note"] = "Include a 'question' form field to ask about this image."
    return jsonify(payload), 201


@upload_bp.route("/uploads", methods=["GET"])
@jwt_required()
def list_uploads():
    records = UploadedFile.query.filter_by(user_id=str(get_jwt_identity())).order_by(UploadedFile.created_at.desc()).all()
    return jsonify({"files": [record.to_dict() for record in records]}), 200


@upload_bp.route("/uploads/<file_id>", methods=["GET"])
@jwt_required()
def download_upload(file_id):
    record = UploadedFile.query.filter_by(id=file_id, user_id=str(get_jwt_identity())).first()
    if not record:
        return jsonify({"error": "File not found."}), 404
    try:
        content = get_storage().read_bytes(record.stored_path)
    except StorageNotConfigured:
        return jsonify({"error": "File storage is not configured."}), 503
    except Exception:
        current_app.logger.exception("Stored file could not be read.")
        return jsonify({"error": "Stored file is unavailable."}), 503
    return send_file(
        BytesIO(content), download_name=record.filename, as_attachment=True,
        mimetype=MIME_MAP.get(record.file_type) or "application/octet-stream",
    )


@upload_bp.route("/uploads/<file_id>", methods=["DELETE"])
@jwt_required()
def delete_upload(file_id):
    record = UploadedFile.query.filter_by(id=file_id, user_id=str(get_jwt_identity())).first()
    if not record:
        return jsonify({"error": "File not found."}), 404
    try:
        get_storage().delete(record.stored_path)
    except StorageNotConfigured:
        return jsonify({"error": "File storage is not configured."}), 503
    except Exception:
        current_app.logger.exception("Stored file deletion failed.")
        return jsonify({"error": "File could not be deleted."}), 503
    db.session.delete(record)
    db.session.commit()
    return jsonify({"message": "File deleted."}), 200
