from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models import User
from app.utils.validators import sanitize_text

profile_bp = Blueprint("profile", __name__)

ALLOWED_LANGUAGES = {"en", "ta"}
ALLOWED_VOICES = {"male", "female", "default"}


@profile_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    user = db.session.get(User, get_jwt_identity())

    if user is None:
        return jsonify({"error": "User not found."}), 404

    return jsonify({
        "user": user.to_dict()
    }), 200


@profile_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    user = db.session.get(User, get_jwt_identity())

    if user is None:
        return jsonify({"error": "User not found."}), 404

    data = request.get_json()

    if data is None:
        return jsonify({"error": "Invalid JSON payload."}), 400

    if "name" in data:
        name = sanitize_text(data["name"]).strip()
        if not name:
            return jsonify({"error": "Name cannot be empty."}), 400
        user.name = name

    if "preferred_language" in data:
        if data["preferred_language"] not in ALLOWED_LANGUAGES:
            return jsonify({"error": "Invalid preferred language."}), 400
        user.preferred_language = data["preferred_language"]

    if "preferred_voice" in data:
        if data["preferred_voice"] not in ALLOWED_VOICES:
            return jsonify({"error": "Invalid preferred voice."}), 400
        user.preferred_voice = data["preferred_voice"]

    if "persona_notes" in data:
        user.persona_notes = sanitize_text(data["persona_notes"])

    db.session.commit()

    return jsonify({
        "message": "Profile updated.",
        "user": user.to_dict()
    }), 200