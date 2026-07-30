# app/routes/upload_routes.py

import os
import uuid
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models import UploadedFile
from app.services.file_service import extract_text
from app.services.provider_router import analyze_image
from app.utils.validators import allowed_file
from app.utils.logger import log_event

# 🌟 Phase 4: Import the new Background Worker
from app.workers.embedding_worker import start_embedding_worker

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
        
    unique_name = f"{uuid.uuid4()}_{filename}"
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_name)
    os.makedirs(current_app.config["UPLOAD_FOLDER"], exist_ok=True)
    file.save(save_path)

    user_id = get_jwt_identity()
    question = request.form.get("question", "").strip()

    record = UploadedFile(
        user_id=user_id,
        filename=filename,
        stored_path=save_path,
        file_type=file_type,
    )
    
    # Handle database commit errors with rollback
    try:
        db.session.add(record)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Database error while saving file metadata: {e}")
        return jsonify({"error": "Failed to save file record in database."}), 500

    # --- Images: answer directly via Gemini Vision, skip text indexing ---
    if file_type in IMAGE_TYPES:
        if not question:
            return jsonify({
                "message": "Image uploaded.",
                "file": record.to_dict(),
                "note": "Include a 'question' form field to ask about this image.",
            }), 201

        # IMPROVEMENT: Verify file size before reading the image into memory
        max_size = current_app.config.get("MAX_CONTENT_LENGTH")
        if max_size and os.path.getsize(save_path) > max_size:
            return jsonify({"error": "Image file size exceeds the configured limit."}), 413

        with open(save_path, "rb") as f:
            image_bytes = f.read()
        try:
            answer = analyze_image(image_bytes, MIME_MAP[file_type], question)
        except Exception as e:
            current_app.logger.error(f"Image analysis failed: {e}")
            return jsonify({"error": "Image analysis failed."}), 502

        log_event(current_app, "IMAGE_UPLOAD", filename, user_id)
        return jsonify({"message": "Image analyzed.", "file": record.to_dict(), "answer": answer}), 201

    # --- Documents: extract text, start background embedding ---
    try:
        text = extract_text(save_path, file_type)
    except Exception as e:
        current_app.logger.error(f"Text extraction failed for {filename}: {e}")
        return jsonify({"error": "Could not extract text from this file."}), 422

    record.extracted_chars = len(text)

    if text.strip():
        # 🌟 Phase 4: Pass to the Background Worker instead of waiting synchronously
        start_embedding_worker(
            current_app._get_current_object(), 
            text, 
            filename, 
            user_id
        )
        record.indexed = True

    # Handle second database commit with rollback
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Database error after file indexing: {e}")

    log_event(current_app, "FILE_UPLOAD", f"{filename} ({file_type})", user_id)

    return jsonify({
        "message": "File uploaded successfully. Processing in background.",
        "file": record.to_dict(),
    }), 201