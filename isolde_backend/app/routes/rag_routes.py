from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import os
from werkzeug.utils import secure_filename

# Blueprint உருவாக்கம்
rag_bp = Blueprint("rag", __name__)

# ஃபைல்களை சேமிக்க Uploads ஃபோல்டர் (உங்களிடம் ஏற்கனவே ரூட் டைரக்டரியில் uploads ஃபோல்டர் உள்ளது)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@rag_bp.route("/api/rag/upload", methods=["POST"], strict_slashes=False)
@jwt_required(optional=True)
def upload_rag_file():
    user_id = get_jwt_identity()
    
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file part in the request."}), 400
        
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "No file selected for upload."}), 400

    try:
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        
        # ஃபைலை சேமிக்கிறோம்
        file.save(file_path)

        # 🌟 எதிர்காலத்தில் இங்கே RAG (Vector Database Indexing) லாஜிக் எழுதப்படும்
        # உதாரணம்: rag_service.index_document(file_path)
        
        current_app.logger.info(f"File uploaded successfully for RAG: {filename} by user: {user_id}")

        return jsonify({
            "status": "success",
            "message": "File uploaded and indexed successfully! You can now chat with this document.",
            "filename": filename
        }), 200

    except Exception as e:
        current_app.logger.error(f"RAG file upload error: {e}")
        return jsonify({"status": "error", "message": "Failed to process and upload file."}), 500