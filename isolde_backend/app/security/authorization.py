"""
Authorization helpers for Isolde AI Part 1.

These helpers enforce:
- active account status
- admin role where required
- direct ownership checks for SQLAlchemy models

They are intentionally generic so they can be used by workspace, project,
agent, conversation, memory, file, and API-key routes without duplicating
existing authentication or AI architecture.
"""

from functools import wraps

from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, current_user

from app.extensions import db


def json_error(message, status_code):
    """
    Return the standard Isolde JSON error shape.

    Existing routes and JWT handlers already use:
    {
        "error": "..."
    }

    This preserves that response contract.
    """
    return jsonify({"error": message}), status_code


def _safe_current_user():
    """
    Safely resolve the Flask-JWT-Extended current_user proxy.

    Returns None when no authenticated user is available or when the
    user lookup failed / account is inactive.
    """
    try:
        return current_user._get_current_object()
    except Exception:
        return None


def active_user_required(fn):
    """
    Require a valid JWT and an Active user.

    This is stronger than @jwt_required() alone because it also verifies
    that the account is still Active at request time.

    If the user is Disabled or Deleted, the request is rejected with 401.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request(optional=False)
        except Exception:
            return json_error("Authentication required.", 401)

        user = _safe_current_user()

        if user is None:
            return json_error("Authentication required.", 401)

        if getattr(user, "status", None) != "Active":
            return json_error("Authentication required.", 401)

        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    """
    Require a valid JWT, an Active user, and role == "Admin".
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request(optional=False)
        except Exception:
            return json_error("Authentication required.", 401)

        user = _safe_current_user()

        if user is None:
            return json_error("Authentication required.", 401)

        if getattr(user, "status", None) != "Active":
            return json_error("Authentication required.", 401)

        if getattr(user, "role", None) != "Admin":
            return json_error("Admin access required.", 403)

        return fn(*args, **kwargs)

    return wrapper


def get_owned_object(
    model,
    object_id,
    user_id,
    user_field="user_id",
    id_field="id",
):
    """
    Return an object only when it belongs to the given user.

    This prevents client-supplied IDs from automatically granting access.

    Example:
        conversation = get_owned_object(Conversation, conversation_id, user_id)

    If the object does not exist or belongs to another user, returns None.
    """
    if object_id is None or user_id is None:
        return None

    try:
        return (
            db.session.query(model)
            .filter_by(**{id_field: object_id, user_field: user_id})
            .first()
        )
    except Exception:
        db.session.rollback()
        return None


def get_owned_object_or_error(
    model,
    object_id,
    user_id,
    user_field="user_id",
    id_field="id",
):
    """
    Ownership helper for route handlers.

    Returns:
        (object, None) when ownership is valid
        (None, error_response) when ownership is invalid or object is missing
    """
    owned_object = get_owned_object(
        model=model,
        object_id=object_id,
        user_id=user_id,
        user_field=user_field,
        id_field=id_field,
    )

    if owned_object is None:
        return None, json_error("Resource not found.", 404)

    return owned_object, None


def get_owned_object_or_none(
    model,
    object_id,
    user_id,
    user_field="user_id",
    id_field="id",
):
    """
    Alias-style helper for routes that prefer explicit None handling.
    """
    return get_owned_object(
        model=model,
        object_id=object_id,
        user_id=user_id,
        user_field=user_field,
        id_field=id_field,
    )