from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models import Conversation, Message
from app.services.gemini_service import generate_reply
from app.services.rag_service import search as rag_search, build_context_block
from app.services.feedback_service import find_relevant_corrections, build_correction_context
from app.services.language_service import detect_language, language_instruction
from app.utils.validators import sanitize_text, is_non_empty
from app.utils.logger import log_event

chat_bp = Blueprint("chat", __name__)


def _get_or_create_conversation(user_id: str, conversation_id: str | None) -> Conversation:
    if conversation_id:
        convo = Conversation.query.filter_by(id=conversation_id, user_id=user_id).first()
        if convo:
            return convo
    convo = Conversation(user_id=user_id, title="New Conversation")
    db.session.add(convo)
    db.session.commit()
    return convo


def _history_for_gemini(convo: Conversation, limit: int = 20):
    """Convert stored messages into Gemini's chat-history format."""
    recent = convo.messages[-limit:] if convo.messages else []
    history = []
    for m in recent:
        role = "user" if m.role == "user" else "model"
        history.append({"role": role, "parts": [m.content]})
    return history


@chat_bp.route("/chat", methods=["POST"])
@jwt_required(optional=True)
def chat():
    data = request.get_json(silent=True) or {}
    raw_message = data.get("message", "")
    conversation_id = data.get("conversation_id")

    if not is_non_empty(raw_message):
        return jsonify({"error": "Message cannot be empty."}), 400

    message = sanitize_text(raw_message)
    user_id = get_jwt_identity()  # None for anonymous guests

    # 1. Language detection (multilingual support)
    lang_code = detect_language(message)
    lang_instruction = language_instruction(lang_code)

    # 2. RAG: search uploaded documents / knowledge base
    rag_chunks = rag_search(message, top_k=4, user_id=user_id)
    rag_context = build_context_block(rag_chunks)

    # 3. Self-correction pipeline: check past feedback corrections
    corrections = find_relevant_corrections(message)
    correction_context = build_correction_context(corrections)

    system_context = "\n\n".join(
        part for part in [rag_context, correction_context, lang_instruction] if part
    )

    # 4. Conversation memory (only for authenticated users; guests are stateless)
    history = []
    convo = None
    if user_id:
        convo = _get_or_create_conversation(user_id, conversation_id)
        history = _history_for_gemini(convo)

    # 5. Generate the answer
    try:
        reply_text = generate_reply(message, history=history, system_context=system_context)
    except RuntimeError as e:
        current_app.logger.error(f"Gemini not configured: {e}")
        return jsonify({"error": "AI service is not configured on the server."}), 503
    except Exception as e:
        current_app.logger.error(f"Gemini generation failed: {e}")
        return jsonify({"error": "The AI service is temporarily unavailable."}), 502

    # 6. Persist conversation memory
    if user_id and convo:
        user_msg = Message(conversation_id=convo.id, role="user", content=message, language=lang_code)
        bot_msg = Message(conversation_id=convo.id, role="bot", content=reply_text, language=lang_code)
        db.session.add_all([user_msg, bot_msg])
        if convo.title == "New Conversation":
            convo.title = message[:50]
        db.session.commit()

    log_event(current_app, "CHAT", f"lang={lang_code} rag_hits={len(rag_chunks)}", user_id)

    return jsonify({
        "reply": reply_text,
        "conversation_id": convo.id if convo else None,
        "language": lang_code,
        "sources": [c["filename"] for c in rag_chunks] if rag_chunks else [],
    })


@chat_bp.route("/voice-chat", methods=["POST"])
@jwt_required(optional=True)
def voice_chat():
    """
    Accepts a transcribed message from the frontend's Web Speech API
    (browser-side Speech-to-Text) and returns a text reply that the
    frontend can pass to the browser's Text-to-Speech (SpeechSynthesis).

    Doing STT/TTS in the browser avoids extra paid API dependencies;
    swap this for a server-side STT/TTS provider if you need it
    server-driven (e.g. Google Cloud Speech, Whisper, ElevenLabs).
    """
    data = request.get_json(silent=True) or {}
    transcript = sanitize_text(data.get("transcript", ""))

    if not is_non_empty(transcript):
        return jsonify({"error": "No speech transcript received."}), 400

    lang_code = detect_language(transcript)
    rag_chunks = rag_search(transcript, top_k=4)
    system_context = build_context_block(rag_chunks)

    try:
        reply_text = generate_reply(transcript, system_context=system_context)
    except Exception as e:
        current_app.logger.error(f"Voice chat generation failed: {e}")
        return jsonify({"error": "The AI service is temporarily unavailable."}), 502

    return jsonify({
        "reply": reply_text,
        "language": lang_code,
        "speak": True,  # signal to frontend to invoke TTS
    })
