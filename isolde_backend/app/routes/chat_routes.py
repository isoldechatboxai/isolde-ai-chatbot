from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models import Conversation, Message
from app.models.user import User, Setting, Feedback, Broadcast
from app.models.memory_model import UserMemory  # 🌟 NEW: Added UserMemory model
from app.services.gemini_service import generate_reply
from app.services.rag_service import search as rag_search, build_context_block
from app.services.feedback_service import find_relevant_corrections, build_correction_context
from app.services.language_service import detect_language, language_instruction
from app.utils.validators import sanitize_text, is_non_empty
from app.utils.logger import log_event

chat_bp = Blueprint("chat", __name__)


def _extract_and_save_memory(user_id: str, message: str):
    """🌟 NEW: Smart helper to auto-extract and store user memories from chat"""
    if not user_id:
        return
    
    text_lower = message.lower()
    memory_to_save = None
    category = "Other"

    # Simple smart extraction rules
    if "my name is" in text_lower or "i am" in text_lower:
        memory_to_save = message.strip()
        category = "Personal"
    elif "my business" in text_lower or "i have business" in text_lower or "company" in text_lower or "vilvarai" in text_lower or "chocolate" in text_lower or "cashews" in text_lower or "dry fruits" in text_lower:
        memory_to_save = message.strip()
        category = "Business"
    elif "i like" in text_lower or "i prefer" in text_lower or "my favorite" in text_lower:
        memory_to_save = message.strip()
        category = "Preferences"

    if memory_to_save:
        try:
            # Check if similar memory already exists
            existing = UserMemory.query.filter_by(user_id=user_id).all()
            exists = any(m.memory.lower() == memory_to_save.lower() for m in existing)
            
            if not exists:
                new_mem = UserMemory(user_id=user_id, memory=memory_to_save, category=category)
                db.session.add(new_mem)
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error auto-saving memory: {e}")


def _get_or_create_conversation(user_id: str, conversation_id: str | None) -> Conversation:
    if conversation_id:
        convo = Conversation.query.filter_by(id=conversation_id, user_id=user_id).first()
        if convo:
            return convo
            
    convo = Conversation(user_id=user_id, title="New Conversation")
    
    try:
        db.session.add(convo)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating conversation: {e}")
        raise
        
    return convo


def _history_for_gemini(convo: Conversation, limit: int = 20):
    """Convert stored messages into Universal AI chat-history format."""
    recent = convo.messages[-limit:] if convo.messages else []
    history = []
    for m in recent:
        role = "user" if m.role == "user" else "model"
        history.append({"role": role, "parts": [m.content]})
    return history


@chat_bp.route("/chat", methods=["POST"], strict_slashes=False)
@jwt_required(optional=True)
def chat():
    try:
        maintenance = Setting.query.filter_by(key="maintenance_mode").first()
        if maintenance and maintenance.value == "True":
            return jsonify({"error": "Site Under Maintenance. We will be back shortly!"}), 503
    except Exception as e:
        current_app.logger.error(f"Maintenance check error: {e}")

    data = request.get_json(silent=True) or {}
    raw_message = data.get("message", "")
    conversation_id = data.get("conversation_id")

    if not is_non_empty(raw_message):
        return jsonify({"error": "Message cannot be empty."}), 400

    message = sanitize_text(raw_message)
    user_id = get_jwt_identity()  # None for anonymous guests

    # 🌟 NEW: Extract memory from user message
    if user_id:
        _extract_and_save_memory(user_id, message)

    # 1. Language detection (multilingual support)
    lang_code = detect_language(message)
    lang_instruction = language_instruction(lang_code)

    # 🌟 NEW: Fetch saved user memories to inject into system context
    memory_context = ""
    if user_id:
        try:
            memories = UserMemory.query.filter_by(user_id=user_id).all()
            if memories:
                mem_texts = [f"- [{m.category}] {m.memory}" for m in memories]
                memory_context = "User Memory / Profile Context:\n" + "\n".join(mem_texts)
        except Exception:
            pass

    # 2. RAG: search uploaded documents / knowledge base
    rag_chunks = rag_search(message, top_k=4, user_id=user_id)
    rag_context = build_context_block(rag_chunks)

    # 3. Self-correction pipeline: check past feedback corrections
    corrections = find_relevant_corrections(message)
    correction_context = build_correction_context(corrections)

    system_context = "\n\n".join(
        part for part in [memory_context, rag_context, correction_context, lang_instruction] if part
    )

    # 4. Conversation memory (only for authenticated users; guests are stateless)
    history = []
    convo = None
    if user_id:
        try:
            convo = _get_or_create_conversation(user_id, conversation_id)
            history = _history_for_gemini(convo)
        except Exception:
            return jsonify({"error": "Database error while loading conversation."}), 500

    # 5. Generate the answer
    try:
        reply_text = generate_reply(message, history=history, system_context=system_context)
    except RuntimeError as e:
        current_app.logger.error(f"AI Service not configured: {e}")
        return jsonify({"error": "AI service is not configured on the server."}), 503
    except Exception as e:
        current_app.logger.error(f"AI generation failed: {e}")
        return jsonify({"error": "The AI service is temporarily unavailable."}), 502

    # 6. Persist conversation memory
    if user_id and convo:
        user_msg = Message(conversation_id=convo.id, role="user", content=message, language=lang_code)
        bot_msg = Message(conversation_id=convo.id, role="bot", content=reply_text, language=lang_code)
        
        try:
            db.session.add_all([user_msg, bot_msg])
            if convo.title == "New Conversation":
                convo.title = message[:50]
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving messages: {e}")

        try:
            user = User.query.get(user_id)
            if user:
                estimated_tokens = (len(message) + len(reply_text)) // 4
                user.tokens_used = (user.tokens_used or 0) + estimated_tokens
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating token analytics: {e}")

    log_event(current_app, "CHAT", f"lang={lang_code} rag_hits={len(rag_chunks)}", user_id)

    broadcast_msg = None
    try:
        latest_broadcast = Broadcast.query.order_by(Broadcast.id.desc()).first()
        if latest_broadcast:
            broadcast_msg = latest_broadcast.message
    except Exception:
        pass

    return jsonify({
        "reply": reply_text,
        "conversation_id": convo.id if convo else None,
        "language": lang_code,
        "sources": [c["filename"] for c in rag_chunks] if rag_chunks else [],
        "broadcast": broadcast_msg
    })


@chat_bp.route("/voice-chat", methods=["POST"], strict_slashes=False)
@jwt_required(optional=True)
def voice_chat():
    try:
        maintenance = Setting.query.filter_by(key="maintenance_mode").first()
        if maintenance and maintenance.value == "True":
            return jsonify({"error": "Site Under Maintenance. Voice Chat offline."}), 503
    except Exception:
        pass

    data = request.get_json(silent=True) or {}
    transcript = sanitize_text(data.get("transcript", ""))

    if not is_non_empty(transcript):
        return jsonify({"error": "No speech transcript received."}), 400

    user_id = get_jwt_identity()

    if user_id:
        _extract_and_save_memory(user_id, transcript)

    lang_code = detect_language(transcript)
    lang_instruction = language_instruction(lang_code)
    
    memory_context = ""
    if user_id:
        try:
            memories = UserMemory.query.filter_by(user_id=user_id).all()
            if memories:
                mem_texts = [f"- [{m.category}] {m.memory}" for m in memories]
                memory_context = "User Memory / Profile Context:\n" + "\n".join(mem_texts)
        except Exception:
            pass

    rag_chunks = rag_search(transcript, top_k=4, user_id=user_id)
    rag_context = build_context_block(rag_chunks)

    system_context = "\n\n".join(
        part for part in [memory_context, rag_context, lang_instruction] if part
    )

    try:
        reply_text = generate_reply(transcript, system_context=system_context)
    except Exception as e:
        current_app.logger.error(f"Voice chat generation failed: {e}")
        return jsonify({"error": "The AI service is temporarily unavailable."}), 502

    if user_id:
        try:
            user = User.query.get(user_id)
            if user:
                estimated_tokens = (len(transcript) + len(reply_text)) // 4
                user.tokens_used = (user.tokens_used or 0) + estimated_tokens
                db.session.commit()
        except Exception as e:
            db.session.rollback()

    return jsonify({
        "reply": reply_text,
        "language": lang_code,
        "speak": True,
    })


@chat_bp.route("/feedback", methods=["POST"], strict_slashes=False)
@jwt_required(optional=True)
def submit_feedback():
    data = request.get_json(silent=True) or {}
    rating = data.get("rating")
    comment = data.get("comment", "")

    if not rating:
        return jsonify({"error": "Rating is required"}), 400

    user_id = get_jwt_identity()
    user_name = "Guest"
    
    if user_id:
        try:
            user = User.query.get(user_id)
            if user:
                user_name = user.name or user.email
        except Exception:
            pass
            
    try:
        fb = Feedback(user_name=user_name, rating=rating, comment=comment)
        db.session.add(fb)
        db.session.commit()
        return jsonify({"status": "success", "message": "Feedback saved for Admin Panel!"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Feedback save error: {e}")
        return jsonify({"status": "error", "message": "Failed to save feedback."}), 500