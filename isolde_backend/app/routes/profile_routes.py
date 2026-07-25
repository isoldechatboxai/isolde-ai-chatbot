from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models import User
from app.utils.validators import sanitize_text

profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    user = User.query.get(get_jwt_identity())

    if not user:
        return jsonify({"error": "User not found."}), 404

    return jsonify({
        "user": user.to_dict()
    })


@profile_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    user = User.query.get(get_jwt_identity())

    if not user:
        return jsonify({"error": "User not found."}), 404

    data = request.get_json(silent=True) or {}

    if "name" in data:
        user.name = sanitize_text(data["name"])

    if "preferred_language" in data:
        user.preferred_language = data["preferred_language"]

    if "preferred_voice" in data:
        user.preferred_voice = data["preferred_voice"]

    if "persona_notes" in data:
        user.persona_notes = sanitize_text(data["persona_notes"])

    db.session.commit()

    return jsonify({
        "message": "Profile updated.",
        "user": user.to_dict()
    })