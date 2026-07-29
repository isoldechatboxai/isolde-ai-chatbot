from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models import Conversation

history_bp = Blueprint("history", __name__)


@history_bp.route("/api/history", methods=["GET"], strict_slashes=False)
@jwt_required(optional=True)
def get_history():
    user_id = get_jwt_identity()

    query = Conversation.query
    if user_id:
        query = query.filter_by(user_id=user_id)
        
    conversations = (
        query.order_by(Conversation.created_at.desc()).all()
    )

    return jsonify({
        "status": "success",
        "conversations": [c.to_dict() for c in conversations]
    }), 200


@history_bp.route("/api/history/<conversation_id>", methods=["GET"], strict_slashes=False)
@jwt_required(optional=True)
def get_conversation(conversation_id):
    user_id = get_jwt_identity()

    if user_id:
        conversation = Conversation.query.filter_by(id=conversation_id, user_id=user_id).first()
    else:
        conversation = Conversation.query.filter_by(id=conversation_id).first()

    if not conversation:
        return jsonify({"status": "error", "message": "Conversation not found."}), 404

    return jsonify({
        "status": "success",
        "conversation": conversation.to_dict(include_messages=True)
    }), 200


# 🌟 MODULE 1 ADDITION: Update Conversation Meta (Rename, Pin, Archive)
@history_bp.route("/api/history/<conversation_id>/update", methods=["PATCH"], strict_slashes=False)
@jwt_required(optional=True)
def update_conversation(conversation_id):
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    if user_id:
        conversation = Conversation.query.filter_by(id=conversation_id, user_id=user_id).first()
    else:
        conversation = Conversation.query.filter_by(id=conversation_id).first()

    if not conversation:
        return jsonify({"status": "error", "message": "Conversation not found."}), 404

    try:
        if "title" in data:
            conversation.title = data["title"]
        if "is_pinned" in data:
            conversation.is_pinned = bool(data["is_pinned"])
        if "is_archived" in data:
            conversation.is_archived = bool(data["is_archived"])

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating conversation {conversation_id}: {e}")
        return jsonify({"status": "error", "message": "Failed to update conversation due to a server error."}), 500

    return jsonify({
        "status": "success",
        "message": "Conversation updated.",
        "conversation": conversation.to_dict()
    }), 200


@history_bp.route("/api/history/<conversation_id>", methods=["DELETE"], strict_slashes=False)
@jwt_required(optional=True)
def delete_conversation(conversation_id):
    user_id = get_jwt_identity()

    if user_id:
        conversation = Conversation.query.filter_by(id=conversation_id, user_id=user_id).first()
    else:
        conversation = Conversation.query.filter_by(id=conversation_id).first()

    if not conversation:
        return jsonify({"status": "error", "message": "Conversation not found."}), 404

    try:
        db.session.delete(conversation)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting conversation {conversation_id}: {e}")
        return jsonify({"status": "error", "message": "Failed to delete conversation due to a server error."}), 500

    return jsonify({
        "status": "success",
        "message": "Conversation deleted."
    }), 200


@history_bp.route("/api/history", methods=["DELETE"], strict_slashes=False)
@jwt_required()
def delete_all_history():
    user_id = get_jwt_identity()

    try:
        Conversation.query.filter_by(user_id=user_id).delete()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting all history for user {user_id}: {e}")
        return jsonify({"status": "error", "message": "Failed to clear history due to a server error."}), 500

    return jsonify({
        "status": "success",
        "message": "All conversation history deleted."
    }), 200 