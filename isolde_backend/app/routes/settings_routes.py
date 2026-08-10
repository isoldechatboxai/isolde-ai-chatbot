from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.user_service import (
    get_user_settings,
    update_settings,
    change_password,
)

settings_bp = Blueprint("settings_bp", __name__)

ALLOWED_SETTING_FIELDS = {
    "preferred_language",
    "preferred_voice",
    "persona_notes",
    "email_notifications",
    "push_notifications",
    "mfa_enabled",
}

BOOLEAN_SETTING_FIELDS = {
    "email_notifications",
    "push_notifications",
    "mfa_enabled",
}


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

    if "Database operation failed" in message:
        return 500

    return 400


def _respond(result):
    return jsonify(result), _http_status(result)


def _current_user_id():
    user_id = get_jwt_identity()

    if user_id is None:
        return None

    user_id = str(user_id).strip()

    if not user_id:
        return None

    return user_id


def _normalize_boolean(value):
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}

    return bool(value)


def _build_settings_payload(data):
    if not isinstance(data, dict):
        return None, "Request body must be a JSON object."

    payload = {}

    for field in ALLOWED_SETTING_FIELDS:
        if field not in data:
            continue

        value = data[field]

        if field in BOOLEAN_SETTING_FIELDS:
            payload[field] = _normalize_boolean(value)
            continue

        if field == "persona_notes" and value is not None and not isinstance(value, str):
            return None, "persona_notes must be a string."

        payload[field] = value

    if not payload:
        return None, "No valid settings fields provided."

    return payload, None


@settings_bp.route("/settings", methods=["GET"], strict_slashes=False)
@jwt_required()
def get_settings():
    try:
        user_id = _current_user_id()

        if not user_id:
            return _error("Authentication token is invalid.", 401)

        result = get_user_settings(user_id)
        return _respond(result)
    except Exception:
        current_app.logger.exception("Unexpected error while fetching user settings.")
        return _error("Unable to fetch settings.", 500)


@settings_bp.route("/settings", methods=["PATCH"], strict_slashes=False)
@jwt_required()
def patch_settings():
    try:
        user_id = _current_user_id()

        if not user_id:
            return _error("Authentication token is invalid.", 401)

        data = request.get_json(silent=True)

        if data is None:
            return _error("Request body must be valid JSON.", 400)

        payload, error = _build_settings_payload(data)

        if error:
            return _error(error, 400)

        result = update_settings(user_id, payload)
        return _respond(result)
    except Exception:
        current_app.logger.exception("Unexpected error while updating user settings.")
        return _error("Unable to update settings.", 500)


@settings_bp.route("/settings/password", methods=["POST"], strict_slashes=False)
@jwt_required()
def change_user_password():
    try:
        user_id = _current_user_id()

        if not user_id:
            return _error("Authentication token is invalid.", 401)

        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return _error("Request body must be a JSON object.", 400)

        old_password = data.get("old_password") or data.get("current_password")
        new_password = data.get("new_password") or data.get("password")

        if not isinstance(old_password, str) or not old_password:
            return _error("Old password is required.", 400)

        if not isinstance(new_password, str) or not new_password:
            return _error("New password is required.", 400)

        result = change_password(user_id, old_password, new_password)
        return _respond(result)
    except Exception:
        current_app.logger.exception("Unexpected error while changing password.")
        return _error("Unable to change password.", 500)