from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models import Feedback
from app.utils.validators import sanitize_text, is_non_empty
from app.utils.logger import log_event

feedback_bp = Blueprint("feedback", __name__)


@feedback_bp.route("/feedback", methods=["POST"])
@jwt_required(optional=True)
def submit_feedback():
    data = request.get_json(silent=True) or {}
    question = sanitize_text(data.get("question", ""))
    bot_answer = sanitize_text(data.get("bot_answer", ""))
    is_correct = bool(data.get("is_correct"))
    correction_text = sanitize_text(data.get("correction_text", "")) or None
    message_id = data.get("message_id")

    if not is_non_empty(question) or not is_non_empty(bot_answer):
        return jsonify({"error": "question and bot_answer are required."}), 400

    if not is_correct and not correction_text:
        return jsonify({
            "error": "Please provide correction_text explaining the right answer "
                     "when marking a response incorrect."
        }), 400

    fb = Feedback(
        user_id=get_jwt_identity(),
        message_id=message_id,
        question=question,
        bot_answer=bot_answer,
        is_correct=is_correct,
        correction_text=correction_text,
    )
    db.session.add(fb)
    db.session.commit()

    log_event(current_app, "FEEDBACK", f"correct={is_correct}", get_jwt_identity())

    return jsonify({"message": "Thanks — feedback recorded.", "feedback": fb.to_dict()}), 201
