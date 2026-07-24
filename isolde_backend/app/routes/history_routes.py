from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models import Conversation

history_bp = Blueprint("history", __name__)


@history_bp.route("/history", methods=["GET"])
@jwt_required()
def get_history():
    user_id = get_jwt_identity()
    conversations = (
        Conversation.query.filter_by(user_id=user_id)
        .order_by(Conversation.created_at.desc())
        .all()
    )
    return jsonify({"conversations": [c.to_dict() for c in conversations]})


@history_bp.route("/history/<conversation_id>", methods=["GET"])
@jwt_required()
def get_conversation(conversation_id):
    user_id = get_jwt_identity()
    convo = Conversation.query.filter_by(id=conversation_id, user_id=user_id).first()
    if not convo:
        return jsonify({"error": "Conversation not found."}), 404
    return jsonify({"conversation": convo.to_dict(include_messages=True)})


@history_bp.route("/history/<conversation_id>", methods=["DELETE"])
@jwt_required()
def delete_conversation(conversation_id):
    user_id = get_jwt_identity()
    convo = Conversation.query.filter_by(id=conversation_id, user_id=user_id).first()
    if not convo:
        return jsonify({"error": "Conversation not found."}), 404
    db.session.delete(convo)
    db.session.commit()
    return jsonify({"message": "Conversation deleted."})


@history_bp.route("/history", methods=["DELETE"])
@jwt_required()
def delete_all_history():
    user_id = get_jwt_identity()
    Conversation.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    return jsonify({"message": "All conversation history deleted."})
