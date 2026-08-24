from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, current_user

from app.services.api_key_service import (
    create_api_key,
    list_user_keys,
    revoke_api_key
)

api_key_bp = Blueprint("api_key_bp", __name__)

ALLOWED_PERMISSIONS = {
    "read",
    "write",
    "admin",
}

MAX_KEY_NAME_LENGTH = 100
MAX_EXPIRY_DAYS = 3650


def _json_error(message, status_code, details=None):
    payload = {
        "error": message
    }
    if details:
        payload["details"] = details
    return jsonify(payload), status_code


def _get_current_user_safe():
    """
    Safely resolve the Flask-JWT-Extended current_user proxy.
    This route is already protected by @jwt_required(). This helper only
    avoids unexpected proxy errors while reading role information.
    """
    try:
        return current_user._get_current_object()
    except Exception:
        return None


def _sanitize_permissions(raw_permissions, is_admin_user):
    """
    Normalize and validate API-key permissions.
    Allowed permissions:
      - read
      - write
      - admin
    Admin permission may only be assigned by an Admin user.
    """
    if raw_permissions is None:
        return "read,write", None

    if not isinstance(raw_permissions, str):
        return None, _json_error(
            "Permissions must be a comma-separated string.",
            400
        )

    permissions = {
        permission.strip().lower()
        for permission in raw_permissions.split(",")
        if permission.strip()
    }

    if not permissions:
        return None, _json_error(
            "Permissions cannot be empty.",
            400
        )

    if not permissions.issubset(ALLOWED_PERMISSIONS):
        return None, _json_error(
            "Permissions must be one or more of: read, write, admin.",
            400
        )

    if "admin" in permissions and not is_admin_user:
        return None, _json_error(
            "Admin permission is not allowed for this account.",
            403
        )

    return ",".join(sorted(permissions)), None


@api_key_bp.route("/keys/generate", methods=["POST"])
@jwt_required()
def generate_key():
    """
    Endpoint for developers to generate a new API key.
    Returns the PLAINTEXT key ONCE.
    """
    user_id = get_jwt_identity()
    if not user_id:
        return _json_error("Authentication required.", 401)

    data = request.get_json(silent=True) or {}

    name = data.get("name")
    if name is None:
        name = "Default API Key"

    if not isinstance(name, str):
        return _json_error("API key name must be a string.", 400)

    name = name.strip()

    if not name:
        return _json_error("API key name cannot be empty.", 400)

    if len(name) > MAX_KEY_NAME_LENGTH:
        return _json_error(
            f"API key name must be {MAX_KEY_NAME_LENGTH} characters or fewer.",
            400
        )

    current_user_obj = _get_current_user_safe()
    is_admin_user = getattr(current_user_obj, "role", None) == "Admin"

    permissions, permission_error = _sanitize_permissions(
        data.get("permissions"),
        is_admin_user
    )
    if permission_error:
        return permission_error

    expires_in_days = data.get("expires_in_days")
    expires_at = None

    if expires_in_days is not None:
        try:
            expires_in_days = int(expires_in_days)
        except (TypeError, ValueError):
            return _json_error(
                "expires_in_days must be a positive integer.",
                400
            )

        if expires_in_days <= 0:
            return _json_error(
                "expires_in_days must be a positive integer.",
                400
            )

        if expires_in_days > MAX_EXPIRY_DAYS:
            return _json_error(
                f"expires_in_days must be {MAX_EXPIRY_DAYS} or fewer.",
                400
            )

        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

    try:
        raw_key, key_metadata = create_api_key(
            user_id=user_id,
            name=name,
            permissions=permissions,
            expires_at=expires_at
        )
        return jsonify({
            "message": "API key generated successfully. Save this key now; it will never be shown again!",
            "api_key": raw_key,
            "metadata": key_metadata
        }), 201
    except Exception:
        current_app.logger.exception("Failed to generate API key.")
        return _json_error(
            "Failed to generate API key.",
            500,
            details="Internal server error."
        )


@api_key_bp.route("/keys", methods=["GET"])
@jwt_required()
def get_user_keys():
    """
    Lists all API keys metadata and analytics belonging to the authenticated user.
    """
    user_id = get_jwt_identity()
    if not user_id:
        return _json_error("Authentication required.", 401)

    try:
        keys = list_user_keys(user_id)
        return jsonify({"keys": keys}), 200
    except Exception:
        current_app.logger.exception("Failed to fetch API keys.")
        return _json_error(
            "Failed to fetch API keys.",
            500,
            details="Internal server error."
        )


@api_key_bp.route("/keys/<int:key_id>", methods=["DELETE"])
@jwt_required()
def delete_key(key_id):
    """
    Revokes an API key so it can no longer be used for authentication.
    Ownership is enforced by requiring both key_id and authenticated user_id.
    """
    user_id = get_jwt_identity()
    if not user_id:
        return _json_error("Authentication required.", 401)

    try:
        success = revoke_api_key(key_id, user_id)
        if not success:
            return _json_error("API key not found or unauthorized.", 404)
        return jsonify({
            "message": f"API key ID {key_id} has been revoked successfully."
        }), 200
    except Exception:
        current_app.logger.exception(
            f"Failed to revoke API key ID {key_id}."
        )
        return _json_error(
            "Failed to revoke API key.",
            500,
            details="Internal server error."
        )