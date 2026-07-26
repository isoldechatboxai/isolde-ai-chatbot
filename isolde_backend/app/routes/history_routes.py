from flask import Blueprint, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models import Conversation

history_bp = Blueprint("history", __name__)


@history_bp.route("/history", methods=["GET"])
@jwt_required()
def get_history():
    # FIX 1: Removed str() cast to maintain integer type from JWT
    user_id = get_jwt_identity()

    conversations = (
        Conversation.query
        .filter_by(user_id=user_id)
        .order_by(Conversation.created_at.desc())
        .all()
    )

    return jsonify({
        "conversations": [c.to_dict() for c in conversations]
    })


@history_bp.route("/history/<conversation_id>", methods=["GET"])
@jwt_required()
def get_conversation(conversation_id):
    # FIX 1: Removed str() cast
    user_id = get_jwt_identity()

    conversation = Conversation.query.filter_by(
        id=conversation_id,
        user_id=user_id
    ).first()

    if not conversation:
        return jsonify({"error": "Conversation not found."}), 404

    return jsonify({
        "conversation": conversation.to_dict(include_messages=True)
    })


@history_bp.route("/history/<conversation_id>", methods=["DELETE"])
@jwt_required()
def delete_conversation(conversation_id):
    # FIX 1: Removed str() cast
    user_id = get_jwt_identity()

    conversation = Conversation.query.filter_by(
        id=conversation_id,
        user_id=user_id
    ).first()

    if not conversation:
        return jsonify({"error": "Conversation not found."}), 404

    # FIX 2: Added try/except/rollback for safe deletion
    try:
        db.session.delete(conversation)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting conversation {conversation_id}: {e}")
        return jsonify({"error": "Failed to delete conversation due to a server error."}), 500

    return jsonify({
        "message": "Conversation deleted."
    })


@history_bp.route("/history", methods=["DELETE"])
@jwt_required()
def delete_all_history():
    # FIX 1: Removed str() cast
    user_id = get_jwt_identity()

    # FIX 2: Added try/except/rollback for safe bulk deletion
    try:
        Conversation.query.filter_by(user_id=user_id).delete()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting all history for user {user_id}: {e}")
        return jsonify({"error": "Failed to clear history due to a server error."}), 500

    return jsonify({
        "message": "All conversation history deleted."
    })