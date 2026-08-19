# app/routes/feedback_routes.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.feedback import Feedback
from app.models.conversation import Message
from app.models.user import User
from app.utils.validators import sanitize_text, is_non_empty
from app.utils.logger import log_event

feedback_bp = Blueprint("feedback", __name__)


def _get_json_payload():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return {}

    return payload


def _clean_text(value):
    if value is None:
        return sanitize_text("")

    return sanitize_text(str(value))


def _as_bool(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}

    return bool(value)


def _resolve_user_id():
    identity = get_jwt_identity()

    if identity is None:
        return None

    user_id = str(identity).strip()

    if not user_id:
        return None

    try:
        user = User.query.get(user_id)
    except Exception:
        return None

    if not user:
        return None

    return user_id


def _resolve_message_id(raw_message_id, user_id):
    if not user_id:
        return None

    if not raw_message_id:
        return None

    message_id = str(raw_message_id).strip()

    if not message_id:
        return None

    try:
        message = Message.query.filter_by(id=message_id).first()
    except Exception:
        return None

    if not message:
        return None

    try:
        owner_id = message.conversation.user_id if message.conversation else None
    except Exception:
        owner_id = None

    if owner_id is not None and str(owner_id) != str(user_id):
        return None

    return message_id


@feedback_bp.route("/feedback/correction", methods=["POST"], strict_slashes=False)
@jwt_required(optional=True)
def submit_feedback():
    data = _get_json_payload()

    question = _clean_text(data.get("question"))
    bot_answer = _clean_text(data.get("bot_answer"))
    is_correct = _as_bool(data.get("is_correct"))
    correction_text = _clean_text(data.get("correction_text")) or None

    user_id = _resolve_user_id()
    message_id = _resolve_message_id(data.get("message_id"), user_id)

    if not is_non_empty(question) or not is_non_empty(bot_answer):
        return jsonify({"error": "question and bot_answer are required."}), 400

    if not is_correct and not correction_text:
        return jsonify({
            "error": "Please provide correction_text explaining the right answer "
                     "when marking a response incorrect."
        }), 400

    try:
        fb = Feedback(
            user_id=user_id,
            message_id=message_id,
            question=question,
            bot_answer=bot_answer,
            is_correct=is_correct,
            correction_text=correction_text,
        )

        db.session.add(fb)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Feedback save error: {e}")

        return jsonify({
            "error": "Failed to record feedback due to a server error."
        }), 500

    try:
        log_event(current_app, "FEEDBACK", f"correct={is_correct}", user_id)
    except Exception:
        pass

    return jsonify({
        "message": "Thanks — feedback recorded.",
        "feedback": fb.to_dict()
    }), 201