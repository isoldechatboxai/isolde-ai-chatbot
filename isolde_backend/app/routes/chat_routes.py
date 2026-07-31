from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models import Conversation, Message
from app.models.user import User, Setting, Feedback, Broadcast
from app.models.memory_model import UserMemory  # 🌟 Phase 2: Smart UserMemory model
from app.services.provider_router import generate_reply
from app.services.rag_service import search as rag_search, build_context_block
from app.services.feedback_service import find_relevant_corrections, build_correction_context
from app.services.language_service import detect_language, language_instruction
from app.utils.validators import sanitize_text, is_non_empty
from app.utils.logger import log_event

import json
import time

chat_bp = Blueprint("chat", __name__)


def _extract_and_save_memory(user_id: str, message: str):
    """🌟 Auto-extract and store structured user memories and auto-train context"""
    if not user_id or len(message.strip()) < 3:
        return

    try:
        prompt = f"""
        Analyze the following user statement. If it contains personal facts, preferences, work details, business info, goals, or corrections, extract it.
        Return strictly a JSON object with keys:
        "category" (e.g., Personal, Location, Work, Business, Preferences, Correction),
        "key" (e.g., Name, City, Company, Business Type, Feedback Correction),
        "value" (the actual fact),
        "confidence" (float between 0.0 and 1.0).
        If no clear personal fact is found, return {{"confidence": 0.0}}.
        Statement: "{message}"
        """
        
        response_text = generate_reply(prompt, system_context="You are a precise data extractor and auto-trainer. Return only valid JSON.")
        
        text = response_text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:].strip()
                
        data = json.loads(text)
        confidence = float(data.get("confidence", 0.0))
        
        if confidence >= 0.75:
            category = data.get("category", "Personal")
            key = data.get("key", "Fact")
            value = str(data.get("value", "")).strip()
            
            if not key or not value:
                return

            existing = UserMemory.query.filter_by(user_id=user_id, key=key).first()
            if existing:
                if existing.value.lower() != value.lower():
                    history = []
                    try:
                        if existing.version_history:
                            history = json.loads(existing.version_history)
                    except Exception:
                        pass
                    
                    history.append({
                        "value": existing.value, 
                        "updated_at": existing.updated_at.isoformat() if existing.updated_at else ""
                    })
                    
                    existing.version_history = json.dumps(history)
                    existing.value = value
                    existing.memory = f"{key}: {value}"
                    existing.category = category
                    existing.confidence_score = confidence
                    db.session.commit()
            else:
                new_mem = UserMemory(
                    user_id=user_id, 
                    category=category, 
                    key=key, 
                    value=value, 
                    memory=f"{key}: {value}",
                    confidence_score=confidence,
                    is_pinned=False
                )
                db.session.add(new_mem)
                db.session.commit()
                
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in Auto-Training / Memory Extraction: {e}")


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
    user_id = get_jwt_identity() 

    if user_id:
        _extract_and_save_memory(user_id, message)

    lang_code = detect_language(message)
    lang_instruction = language_instruction(lang_code)

    memory_context = ""
    if user_id:
        try:
            memories = UserMemory.query.filter_by(user_id=user_id).order_by(UserMemory.is_pinned.desc(), UserMemory.updated_at.desc()).limit(30).all()
            if memories:
                mem_texts = [f"- [{m.category}]{' [PINNED]' if m.is_pinned else ''} {m.key}: {m.value}" for m in memories]
                memory_context = "User Profile & Context (Auto-learned facts):\n" + "\n".join(mem_texts)
        except Exception as e:
            current_app.logger.error(f"Error building memory context: {e}")

    rag_chunks = rag_search(message, top_k=4, user_id=user_id)
    rag_context = build_context_block(rag_chunks)

    corrections = find_relevant_corrections(message)
    correction_context = build_correction_context(corrections)

    system_context = "\n\n".join(
        part for part in [memory_context, rag_context, correction_context, lang_instruction] if part
    )

    history = []
    convo = None
    if user_id:
        try:
            convo = _get_or_create_conversation(user_id, conversation_id)
            history = _history_for_gemini(convo)
        except Exception:
            return jsonify({"error": "Database error while loading conversation."}), 500

    try:
        reply_text = generate_reply(message, history=history, system_context=system_context)
    except RuntimeError as e:
        current_app.logger.error(f"AI Service not configured: {e}")
        return jsonify({"error": "AI service is not configured on the server."}), 503
    except Exception as e:
        current_app.logger.error(f"AI generation failed: {e}")
        return jsonify({"error": "The AI service is temporarily unavailable."}), 502

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


@chat_bp.route("/chat/stream", methods=["POST"], strict_slashes=False)
@jwt_required(optional=True)
def stream_chat():
    data = request.get_json(silent=True) or {}
    raw_message = data.get("message", "")
    conversation_id = data.get("conversation_id")
    selected_model = data.get("model", "default-ai")

    if not is_non_empty(raw_message):
        return jsonify({"error": "Message cannot be empty."}), 400

    message = sanitize_text(raw_message)
    user_id = get_jwt_identity()

    if user_id:
        _extract_and_save_memory(user_id, message)

    lang_code = detect_language(message)
    lang_instruction = language_instruction(lang_code)

    memory_context = ""
    if user_id:
        try:
            memories = UserMemory.query.filter_by(user_id=user_id).order_by(UserMemory.is_pinned.desc(), UserMemory.updated_at.desc()).limit(30).all()
            if memories:
                mem_texts = [f"- [{m.category}]{' [PINNED]' if m.is_pinned else ''} {m.key}: {m.value}" for m in memories]
                memory_context = "User Profile & Context:\n" + "\n".join(mem_texts)
        except Exception:
            pass

    rag_chunks = rag_search(message, top_k=4, user_id=user_id)
    rag_context = build_context_block(rag_chunks)
    system_context = "\n\n".join(part for part in [memory_context, rag_context, lang_instruction] if part)

    history = []
    convo = None
    if user_id:
        try:
            convo = _get_or_create_conversation(user_id, conversation_id)
            history = _history_for_gemini(convo)
        except Exception:
            pass

    def generate():
        try:
            reply_text = generate_reply(message, history=history, system_context=system_context)
            words = reply_text.split(" ")
            for word in words:
                yield f"data: {word} \n\n"
                time.sleep(0.02)
            yield "data: [DONE]\n\n"

            if user_id and convo:
                user_msg = Message(conversation_id=convo.id, role="user", content=message, language=lang_code)
                bot_msg = Message(conversation_id=convo.id, role="bot", content=reply_text, language=lang_code)
                db.session.add_all([user_msg, bot_msg])
                if convo.title == "New Conversation":
                    convo.title = message[:50]
                db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Streaming error: {e}")
            yield f"data: [ERROR]\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


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