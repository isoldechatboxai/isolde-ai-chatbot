from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.provider_router import generate_reply
from app.services.saas_engine import check_and_deduct_tokens, save_chat_history
from app.utils.validators import sanitize_text, is_non_empty

unified_engine_bp = Blueprint("unified_engine_bp", __name__)

@unified_engine_bp.route("/engine/chat", methods=["POST"])
@jwt_required()
def handle_unified_chat():
    current_user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    
    raw_message = data.get("message", "")
    conversation_id = data.get("conversation_id", "default-conv")
    
    if not is_non_empty(raw_message):
        return jsonify({"error": "Message cannot be empty."}), 400

    message = sanitize_text(raw_message)

    # 1. Check Plan & Token Quota
    allowed, reason = check_and_deduct_tokens(current_user_id, estimated_tokens=len(message))
    if not allowed:
        return jsonify({"error": reason}), 403

    # 2. Save User Message to History
    save_chat_history(current_user_id, conversation_id, "user", message)

    try:
        # 3. Generate AI Reply using Provider Router
        ai_reply = generate_reply(message)
    except Exception as e:
        current_app.logger.error(f"Unified Engine AI Error: {e}")
        return jsonify({"error": "AI service unavailable."}), 502

    # 4. Save AI Reply to History
    save_chat_history(current_user_id, conversation_id, "assistant", ai_reply)

    return jsonify({
        "status": "success",
        "reply": ai_reply,
        "conversation_id": conversation_id
    }), 200