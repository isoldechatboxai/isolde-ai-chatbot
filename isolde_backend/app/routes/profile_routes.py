from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.user_service import (
    get_user_profile,
    get_user_settings,
    update_profile,
    delete_account,
)

profile_bp = Blueprint("profile_bp", __name__)

DEFAULT_TOKEN_LIMIT = 10000

DEFAULT_PROFILE_FLAGS = {
    "email_notifications": True,
    "push_notifications": True,
    "mfa_enabled": False,
}


def _success(message, data=None):
    return jsonify({
        "success": True,
        "message": message,
        "data": data,
    })


def _error(message, status=400):
    return jsonify({
        "success": False,
        "message": message,
        "data": None,
    }), status


def _http_status(result):
    if result.get("success"):
        return 200

    message = str(result.get("message", ""))

    if "User not found" in message:
        return 404

    if "Database operation failed" in message or "Account deletion failed" in message:
        return 500

    return 400


def _respond(result):
    return jsonify(result), _http_status(result)


def _current_user_id():
    user_id = get_jwt_identity()

    if user_id is None:
        return None

    if isinstance(user_id, str):
        user_id = user_id.strip()
        return user_id or None

    if isinstance(user_id, int):
        return str(user_id)

    return None


def _normalize_profile_data(profile_data, settings_data, user_id):
    payload = dict(profile_data or {})

    if isinstance(settings_data, dict):
        if "preferred_language" in settings_data:
            payload["preferred_language"] = settings_data.get("preferred_language")

        if "preferred_voice" in settings_data:
            payload["preferred_voice"] = settings_data.get("preferred_voice")

        if "persona_notes" in settings_data:
            payload["persona_notes"] = settings_data.get("persona_notes")

    payload.setdefault("id", user_id)
    payload.setdefault("name", "")
    payload.setdefault("email", "")
    payload.setdefault("role", "Client")
    payload.setdefault("status", "Active")
    payload.setdefault("token_limit", DEFAULT_TOKEN_LIMIT)
    payload.setdefault("tokens_used", 0)
    payload.setdefault("preferred_language", "en")
    payload.setdefault("preferred_voice", "default")
    payload.setdefault("persona_notes", "")
    payload.setdefault("created_at", None)

    for key, value in DEFAULT_PROFILE_FLAGS.items():
        payload.setdefault(key, value)

    return payload


@profile_bp.route("/profile", methods=["GET"], strict_slashes=False)
@jwt_required()
def get_profile():
    try:
        user_id = _current_user_id()

        if not user_id:
            return _error("Authentication token is invalid.", 401)

        profile_result = get_user_profile(user_id)

        if not profile_result.get("success"):
            return _respond(profile_result)

        settings_result = get_user_settings(user_id)
        settings_data = None

        if settings_result.get("success"):
            settings_data = settings_result.get("data")

        profile_data = _normalize_profile_data(
            profile_result.get("data"),
            settings_data,
            user_id,
        )

        return _success("User profile retrieved.", profile_data), 200
    except Exception:
        current_app.logger.exception("Unexpected error while fetching profile.")
        return _error("Unable to fetch profile.", 500)


@profile_bp.route("/profile", methods=["PATCH"], strict_slashes=False)
@jwt_required()
def update_profile_endpoint():
    try:
        user_id = _current_user_id()

        if not user_id:
            return _error("Authentication token is invalid.", 401)

        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return _error("Request body must be a JSON object.", 400)

        payload = {}

        if "name" in data:
            payload["name"] = data.get("name")

        if "email" in data:
            payload["email"] = data.get("email")

        if not payload:
            return _error("No valid profile fields provided.", 400)

        result = update_profile(user_id, payload)
        return _respond(result)
    except Exception:
        current_app.logger.exception("Unexpected error while updating profile.")
        return _error("Unable to update profile.", 500)


@profile_bp.route("/account", methods=["DELETE"], strict_slashes=False)
@jwt_required()
def delete_user_account():
    try:
        user_id = _current_user_id()

        if not user_id:
            return _error("Authentication token is invalid.", 401)

        result = delete_account(user_id)

        if result.get("success"):
            result["data"] = {
                "deleted": True,
                "token_revoked": True,
            }

        return _respond(result)
    except Exception:
        current_app.logger.exception("Unexpected error while deleting account.")
        return _error("Unable to delete account.", 500)