# app/routes/chat_extended_routes.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models import Conversation
from app.models.chat_extended_models import (
    PinnedChat,
    ChatFolder,
    ChatTag,
    ConversationTagMap,
)

chat_ext_bp = Blueprint("chat_ext", __name__)


@chat_ext_bp.route("/api/chat/pin", methods=["POST"], strict_slashes=False)
@jwt_required()
def toggle_pin_chat():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    conversation_id = data.get("conversation_id")

    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400

    try:
        conversation = Conversation.query.filter_by(
            id=conversation_id,
            user_id=user_id,
        ).first()

        if not conversation:
            return jsonify({"error": "Conversation not found."}), 404

        new_state = not bool(conversation.is_pinned)
        conversation.is_pinned = new_state

        pinned = PinnedChat.query.filter_by(
            user_id=user_id,
            conversation_id=conversation_id,
        ).first()

        if new_state:
            if not pinned:
                pinned = PinnedChat(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    is_favorite=True,
                )
                db.session.add(pinned)
        else:
            if pinned:
                db.session.delete(pinned)

        db.session.commit()

        return jsonify(
            {
                "status": "success",
                "message": "Chat pinned" if new_state else "Chat unpinned",
                "is_pinned": new_state,
            }
        ), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling pin: {e}")
        return jsonify({"error": "Failed to update pin status"}), 500


@chat_ext_bp.route("/api/chat/folder", methods=["POST", "GET"], strict_slashes=False)
@jwt_required()
def manage_folders():
    user_id = get_jwt_identity()

    if request.method == "GET":
        try:
            folders = ChatFolder.query.filter_by(user_id=user_id).all()
            folder_list = [{"id": folder.id, "name": folder.name} for folder in folders]

            return jsonify(
                {
                    "status": "success",
                    "folders": folder_list,
                }
            ), 200
        except Exception as e:
            current_app.logger.error(f"Error fetching folders: {e}")
            return jsonify({"error": "Failed to fetch folders"}), 500

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        folder_name = data.get("name")

        if not folder_name:
            return jsonify({"error": "Folder name is required"}), 400

        try:
            new_folder = ChatFolder(user_id=user_id, name=folder_name)
            db.session.add(new_folder)
            db.session.commit()

            return jsonify(
                {
                    "status": "success",
                    "message": "Folder created",
                    "folder": {
                        "id": new_folder.id,
                        "name": new_folder.name,
                    },
                }
            ), 201
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating folder: {e}")
            return jsonify({"error": "Failed to create folder"}), 500


@chat_ext_bp.route("/api/chat/tag", methods=["POST"], strict_slashes=False)
@jwt_required()
def add_tag():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    tag_name = data.get("name")
    color_code = data.get("color_code", "#808080")

    if not tag_name:
        return jsonify({"error": "Tag name is required"}), 400

    try:
        existing_tag = ChatTag.query.filter_by(
            user_id=user_id,
            name=tag_name,
        ).first()

        if not existing_tag:
            existing_tag = ChatTag(
                user_id=user_id,
                name=tag_name,
                color_code=color_code,
            )
            db.session.add(existing_tag)
            db.session.commit()

        return jsonify(
            {
                "status": "success",
                "message": "Tag ready",
                "tag": {
                    "id": existing_tag.id,
                    "name": existing_tag.name,
                },
            }
        ), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error managing tag: {e}")
        return jsonify({"error": "Failed to create tag"}), 500