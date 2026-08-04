# app/routes/history_routes.py
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models import Conversation

history_bp = Blueprint("history", __name__)


@history_bp.route("/history", methods=["GET"], strict_slashes=False)
@jwt_required(optional=True)
def get_history():
    user_id = get_jwt_identity()

    if not user_id:
        return jsonify({"status": "success", "conversations": []}), 200

    q = request.args.get("q", "").strip()

    query = Conversation.query.filter_by(user_id=user_id)

    if q:
        query = query.filter(Conversation.title.ilike(f"%{q}%"))

    try:
        conversations = (
            query.order_by(
                Conversation.is_pinned.desc(),
                Conversation.created_at.desc(),
            ).all()
        )

        return jsonify(
            {
                "status": "success",
                "conversations": [conversation.to_dict() for conversation in conversations],
            }
        ), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching history: {e}")
        return jsonify(
            {
                "status": "error",
                "message": "Failed to load chat history.",
            }
        ), 500


@history_bp.route("/history/<conversation_id>", methods=["GET"], strict_slashes=False)
@jwt_required(optional=True)
def get_conversation(conversation_id):
    user_id = get_jwt_identity()

    if not user_id:
        return jsonify({"status": "error", "message": "Conversation not found."}), 404

    conversation = Conversation.query.filter_by(
        id=conversation_id,
        user_id=user_id,
    ).first()

    if not conversation:
        return jsonify({"status": "error", "message": "Conversation not found."}), 404

    return jsonify(
        {
            "status": "success",
            "conversation": conversation.to_dict(include_messages=True),
        }
    ), 200


@history_bp.route(
    "/history/<conversation_id>/update",
    methods=["PATCH"],
    strict_slashes=False,
)
@jwt_required(optional=True)
def update_conversation(conversation_id):
    user_id = get_jwt_identity()

    if not user_id:
        return jsonify({"status": "error", "message": "Conversation not found."}), 404

    data = request.get_json(silent=True) or {}

    conversation = Conversation.query.filter_by(
        id=conversation_id,
        user_id=user_id,
    ).first()

    if not conversation:
        return jsonify({"status": "error", "message": "Conversation not found."}), 404

    try:
        if "title" in data:
            title = str(data.get("title") or "").strip()

            if not title:
                return jsonify(
                    {
                        "status": "error",
                        "message": "Conversation title cannot be empty.",
                    }
                ), 400

            if len(title) > 200:
                title = title[:200]

            conversation.title = title

        if "is_pinned" in data:
            conversation.is_pinned = bool(data.get("is_pinned"))

        if "is_archived" in data:
            conversation.is_archived = bool(data.get("is_archived"))

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating conversation {conversation_id}: {e}")
        return jsonify(
            {
                "status": "error",
                "message": "Failed to update conversation due to a server error.",
            }
        ), 500

    return jsonify(
        {
            "status": "success",
            "message": "Conversation updated.",
            "conversation": conversation.to_dict(),
        }
    ), 200


@history_bp.route("/history/<conversation_id>", methods=["DELETE"], strict_slashes=False)
@jwt_required(optional=True)
def delete_conversation(conversation_id):
    user_id = get_jwt_identity()

    if not user_id:
        return jsonify({"status": "error", "message": "Conversation not found."}), 404

    conversation = Conversation.query.filter_by(
        id=conversation_id,
        user_id=user_id,
    ).first()

    if not conversation:
        return jsonify({"status": "error", "message": "Conversation not found."}), 404

    try:
        db.session.delete(conversation)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting conversation {conversation_id}: {e}")
        return jsonify(
            {
                "status": "error",
                "message": "Failed to delete conversation due to a server error.",
            }
        ), 500

    return jsonify(
        {
            "status": "success",
            "message": "Conversation deleted.",
        }
    ), 200


@history_bp.route("/history", methods=["DELETE"], strict_slashes=False)
@jwt_required()
def delete_all_history():
    user_id = get_jwt_identity()

    try:
        conversations = Conversation.query.filter_by(user_id=user_id).all()

        for conversation in conversations:
            db.session.delete(conversation)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting all history for user {user_id}: {e}")
        return jsonify(
            {
                "status": "error",
                "message": "Failed to clear history due to a server error.",
            }
        ), 500

    return jsonify(
        {
            "status": "success",
            "message": "All conversation history deleted.",
        }
    ), 200


@history_bp.route(
    "/history/<conversation_id>/export",
    methods=["GET"],
    strict_slashes=False,
)
@jwt_required(optional=True)
def export_conversation(conversation_id):
    user_id = get_jwt_identity()

    if not user_id:
        return jsonify({"status": "error", "message": "Conversation not found."}), 404

    conversation = Conversation.query.filter_by(
        id=conversation_id,
        user_id=user_id,
    ).first()

    if not conversation:
        return jsonify({"status": "error", "message": "Conversation not found."}), 404

    payload = {
        "export_version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "conversation": conversation.to_dict(include_messages=True),
    }

    return jsonify(payload), 200