# app/routes/history_routes.py
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.conversation import Conversation
history_bp = Blueprint("history", __name__)


def _get_authenticated_user_id():
    user_id = get_jwt_identity()

    if user_id is None:
        return None

    return str(user_id)


def _to_bool(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}

    return bool(value)


def _escape_like(value):
    return (
        value
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def _get_owned_conversation(conversation_id, user_id):
    if not conversation_id or not user_id:
        return None

    return Conversation.query.filter_by(
        id=conversation_id,
        user_id=user_id
    ).first()


@history_bp.route("/history", methods=["GET"], strict_slashes=False)
@history_bp.route("/api/history", methods=["GET"], strict_slashes=False)
@jwt_required(optional=True)
def get_history():
    user_id = _get_authenticated_user_id()

    if not user_id:
        return jsonify({
            "status": "success",
            "conversations": []
        }), 200

    search_query = (
        request.args.get("q")
        or request.args.get("search")
        or request.args.get("query")
        or ""
    ).strip()

    try:
        query = Conversation.query.filter_by(user_id=user_id)

        if search_query:
            escaped_query = _escape_like(search_query)
            query = query.filter(
                Conversation.title.ilike(f"%{escaped_query}%", escape="\\")
            )

        conversations = (
            query
            .order_by(
                Conversation.is_pinned.desc(),
                Conversation.created_at.desc()
            )
            .all()
        )

        return jsonify({
            "status": "success",
            "conversations": [conversation.to_dict() for conversation in conversations]
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching history for user {user_id}: {e}")

        return jsonify({
            "status": "error",
            "message": "Failed to load chat history due to a server error."
        }), 500


@history_bp.route("/history/<conversation_id>", methods=["GET"], strict_slashes=False)
@history_bp.route("/api/history/<conversation_id>", methods=["GET"], strict_slashes=False)
@jwt_required(optional=True)
def get_conversation(conversation_id):
    user_id = _get_authenticated_user_id()

    if not user_id:
        return jsonify({
            "status": "error",
            "message": "Conversation not found."
        }), 404

    try:
        conversation = _get_owned_conversation(conversation_id, user_id)
    except Exception as e:
        current_app.logger.error(f"Error loading conversation {conversation_id}: {e}")

        return jsonify({
            "status": "error",
            "message": "Failed to load conversation due to a server error."
        }), 500

    if not conversation:
        return jsonify({
            "status": "error",
            "message": "Conversation not found."
        }), 404

    return jsonify({
        "status": "success",
        "conversation": conversation.to_dict(include_messages=True)
    }), 200


@history_bp.route(
    "/history/<conversation_id>/update",
    methods=["PATCH"],
    strict_slashes=False
)
@history_bp.route(
    "/api/history/<conversation_id>/update",
    methods=["PATCH"],
    strict_slashes=False
)
@jwt_required(optional=True)
def update_conversation(conversation_id):
    user_id = _get_authenticated_user_id()

    if not user_id:
        return jsonify({
            "status": "error",
            "message": "Conversation not found."
        }), 404

    data = request.get_json(silent=True) or {}

    try:
        conversation = _get_owned_conversation(conversation_id, user_id)
    except Exception as e:
        current_app.logger.error(f"Error finding conversation {conversation_id}: {e}")

        return jsonify({
            "status": "error",
            "message": "Failed to update conversation due to a server error."
        }), 500

    if not conversation:
        return jsonify({
            "status": "error",
            "message": "Conversation not found."
        }), 404

    try:
        if "title" in data:
            title = str(data.get("title") or "").strip()

            if title:
                conversation.title = title[:200]

        if "is_pinned" in data:
            conversation.is_pinned = _to_bool(data.get("is_pinned"))

        if "is_archived" in data:
            conversation.is_archived = _to_bool(data.get("is_archived"))

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating conversation {conversation_id}: {e}")

        return jsonify({
            "status": "error",
            "message": "Failed to update conversation due to a server error."
        }), 500

    return jsonify({
        "status": "success",
        "message": "Conversation updated.",
        "conversation": conversation.to_dict()
    }), 200


@history_bp.route("/history/<conversation_id>", methods=["DELETE"], strict_slashes=False)
@history_bp.route("/api/history/<conversation_id>", methods=["DELETE"], strict_slashes=False)
@jwt_required(optional=True)
def delete_conversation(conversation_id):
    user_id = _get_authenticated_user_id()

    if not user_id:
        return jsonify({
            "status": "error",
            "message": "Conversation not found."
        }), 404

    try:
        conversation = _get_owned_conversation(conversation_id, user_id)
    except Exception as e:
        current_app.logger.error(f"Error finding conversation {conversation_id}: {e}")

        return jsonify({
            "status": "error",
            "message": "Failed to delete conversation due to a server error."
        }), 500

    if not conversation:
        return jsonify({
            "status": "error",
            "message": "Conversation not found."
        }), 404

    try:
        db.session.delete(conversation)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting conversation {conversation_id}: {e}")

        return jsonify({
            "status": "error",
            "message": "Failed to delete conversation due to a server error."
        }), 500

    return jsonify({
        "status": "success",
        "message": "Conversation deleted."
    }), 200


@history_bp.route("/history", methods=["DELETE"], strict_slashes=False)
@history_bp.route("/api/history", methods=["DELETE"], strict_slashes=False)
@jwt_required()
def delete_all_history():
    user_id = _get_authenticated_user_id()

    if not user_id:
        return jsonify({
            "status": "error",
            "message": "Conversation history not found."
        }), 404

    try:
        conversations = Conversation.query.filter_by(user_id=user_id).all()

        for conversation in conversations:
            db.session.delete(conversation)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting all history for user {user_id}: {e}")

        return jsonify({
            "status": "error",
            "message": "Failed to clear history due to a server error."
        }), 500

    return jsonify({
        "status": "success",
        "message": "All conversation history deleted."
    }), 200


@history_bp.route(
    "/history/<conversation_id>/export",
    methods=["GET"],
    strict_slashes=False
)
@history_bp.route(
    "/api/history/<conversation_id>/export",
    methods=["GET"],
    strict_slashes=False
)
@jwt_required(optional=True)
def export_conversation(conversation_id):
    user_id = _get_authenticated_user_id()

    if not user_id:
        return jsonify({
            "status": "error",
            "message": "Conversation not found."
        }), 404

    try:
        conversation = _get_owned_conversation(conversation_id, user_id)
    except Exception as e:
        current_app.logger.error(f"Error exporting conversation {conversation_id}: {e}")

        return jsonify({
            "status": "error",
            "message": "Failed to export conversation due to a server error."
        }), 500

    if not conversation:
        return jsonify({
            "status": "error",
            "message": "Conversation not found."
        }), 404

    payload = {
        "status": "success",
        "export_version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "conversation": conversation.to_dict(include_messages=True)
    }

    response = jsonify(payload)
    response.headers["Content-Disposition"] = (
        f'attachment; filename="conversation-{conversation.id}.json"'
    )

    return response, 200