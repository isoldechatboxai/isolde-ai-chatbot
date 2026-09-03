"""
Unified Chat Engine — production-hardened rebuild.
Endpoint:
POST /api/engine/chat          (blueprint registered with url_prefix="/api")
Security:
• JWT required  (@jwt_required)
• User identity from token, never from request body
• Conversation ownership enforced
Token limits:
• check_and_deduct_tokens is called as a BEST-EFFORT usage tracker.
• It NEVER blocks or rejects a chat request.
• When hard billing is enabled in the future, flip the guard below.
History:
• Uses the existing Conversation / Message models.
• Retrieves the last 20 messages and passes them to generate_reply.
• Saves both user and assistant messages after generation.
"""
from functools import wraps
from flask import Blueprint, request, jsonify, current_app, g
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

from app.extensions import db
from app.models.conversation import Conversation, Message
from app.services.provider_router import generate_reply_with_usage
from app.services.saas_engine import check_and_deduct_tokens, save_chat_history
from app.utils.validators import sanitize_text, is_non_empty

unified_engine_bp = Blueprint("unified_engine_bp", __name__)

# Maximum number of recent messages to include as conversation history.
HISTORY_LIMIT = 20


# ---------------------------------------------------------------------------
# Unified Authentication Decorator
# ---------------------------------------------------------------------------
def unified_auth_required(required_permission=None):
    """
    Allows access via either:
    1. Valid JWT token (internal/admin access)
    2. Valid Isolde API key (external developer access)

    Sets g.auth_user_id to the authenticated user's ID in both cases.
    Sets g.auth_method to 'jwt' or 'api_key'.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Try JWT authentication first
            try:
                verify_jwt_in_request(optional=True)
                jwt_identity = get_jwt_identity()
                if jwt_identity:
                    g.auth_user_id = str(jwt_identity)
                    g.auth_method = 'jwt'
                    return f(*args, **kwargs)
            except Exception:
                pass

            # 2. Try API key authentication
            api_key = None
            if 'X-API-Key' in request.headers:
                api_key = request.headers['X-API-Key']
            elif 'Authorization' in request.headers:
                auth_header = request.headers['Authorization']
                if auth_header.startswith('Bearer '):
                    token = auth_header.split(' ', 1)[1]
                    if token.startswith('isk_'):
                        api_key = token

            if api_key:
                from app.services.api_key_service import verify_api_key
                key_record = verify_api_key(api_key)
                if key_record:
                    permissions = {
                        item.strip().lower()
                        for item in (key_record.permissions or "").split(",")
                        if item.strip()
                    }
                    if required_permission and required_permission not in permissions and "admin" not in permissions:
                        return jsonify({
                            "error": "Forbidden",
                            "message": f"API key lacks required permission: '{required_permission}'.",
                        }), 403
                    g.auth_user_id = key_record.user_id
                    g.auth_method = 'api_key'
                    g.api_key = key_record
                    return f(*args, **kwargs)

            return jsonify({
                "error": "Authentication required. Provide a valid JWT or Isolde API key."
            }), 401

        return decorated_function
    return decorator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_or_create_conversation(user_id: str, conversation_id: str | None) -> Conversation:
    """
    Return the existing conversation if it belongs to user_id,
    otherwise create a new one.  Mirrors the logic in chat_routes.py.
    """
    if conversation_id:
        convo = Conversation.query.filter_by(
            id=conversation_id, user_id=user_id
        ).first()
        if convo:
            return convo
        # conversation_id supplied but not found (or belongs to another user)
        # → fall through and create a fresh conversation.

    convo = Conversation(user_id=user_id, title="New Conversation")
    db.session.add(convo)
    db.session.commit()
    return convo


def _history_for_provider(convo: Conversation, limit: int = HISTORY_LIMIT) -> list:
    """
    Build the history list expected by provider_router.generate_reply().
    Uses the same { "role": ..., "parts": [...]} shape that
    chat_routes._history_for_gemini produces, which is understood by
    every provider implementation in provider_router.
    """
    recent = convo.messages[-limit:] if convo.messages else []
    history: list[dict] = []
    for m in recent:
        role = "user" if m.role == "user" else "model"
        history.append({"role": role, "parts": [m.content]})
    return history


def _save_message(conversation_id: str, role: str, content: str) -> None:
    """Persist a single message to the Message table."""
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
    )
    db.session.add(msg)
    db.session.commit()


def _try_legacy_history_save(user_id, conversation_id, role, content):
    """
    Best-effort call to the legacy saas_engine.save_chat_history.
    Kept for backward compatibility; failures are logged and swallowed.
    """
    try:
        save_chat_history(user_id, conversation_id, role, content)
    except Exception as exc:
        current_app.logger.debug(
            f"Legacy save_chat_history skipped (non-fatal): {exc}"
        )


def _try_token_tracking(user_id: str, tokens_used) -> None:
    """
    Best-effort token usage tracking.
    NEVER blocks the chat request.  When hard billing is required in
    the future, replace the body with a mandatory check.
    """
    try:
        if tokens_used is None:
            return
        allowed, reason = check_and_deduct_tokens(user_id, estimated_tokens=tokens_used)
        if not allowed:
            current_app.logger.warning(
                f"Token quota note for user {user_id}: {reason} "
                "(chat continues — hard limits are not yet enforced)"
            )
    except Exception as exc:
        current_app.logger.debug(
            f"Token tracking skipped (non-fatal): {exc}"
        )


def _track_api_key_usage(tokens_used=None) -> None:
    """
    Best-effort API key usage tracking.
    Updates total_requests counter for the authenticated API key.
    NEVER blocks the chat request.
    """
    api_key_record = getattr(g, "api_key", None)
    if not api_key_record:
        return
    try:
        from app.services.api_key_service import track_api_usage
        track_api_usage(api_key_record.key_hash, tokens_used=tokens_used or 0, cost=0.0)
    except Exception as exc:
        current_app.logger.debug(
            f"API key usage tracking skipped (non-fatal): {exc}"
        )


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------
@unified_engine_bp.route("/engine/chat", methods=["POST"], strict_slashes=False)
@unified_engine_bp.route("/v1/chat", methods=["POST"], strict_slashes=False)
@unified_auth_required("write")
def handle_unified_chat():
    """
    POST /api/engine/chat
    Body: { "message": "...", "conversation_id": "..." (optional)}

    Supports both JWT and Isolde API key authentication.
    """
    # -- 1. Identify the authenticated user --------------------------------
    current_user_id = getattr(g, 'auth_user_id', None)
    if not current_user_id:
        return jsonify({"error": "Authentication required."}), 401

    # -- 2. Parse & validate the request body ------------------------------
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    raw_message = data.get("message", "")
    conversation_id = data.get("conversation_id")  # may be None

    if not is_non_empty(raw_message):
        return jsonify({"error": "Message cannot be empty."}), 400

    message = sanitize_text(raw_message)

    # -- 3. Resolve or create the conversation -----------------------------
    try:
        convo = _get_or_create_conversation(current_user_id, conversation_id)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"Conversation resolution failed: {exc}")
        return jsonify({"error": "Failed to resolve conversation."}), 500

    # -- 6. Build conversation history for the provider --------------------
    try:
        history = _history_for_provider(convo)
    except Exception as exc:
        current_app.logger.warning(f"History load failed (continuing without): {exc}")
        history = []

    # -- 7. Save the user message BEFORE generation ------------------------
    try:
        _save_message(convo.id, "user", message)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"Failed to save user message: {exc}")
        return jsonify({"error": "Failed to save message."}), 500

    _try_legacy_history_save(current_user_id, convo.id, "user", message)

    # -- 8. Generate the AI reply ------------------------------------------
    try:
        provider_result = generate_reply_with_usage(message, history=history)
        ai_reply = provider_result.text
    except RuntimeError as exc:
        current_app.logger.error(f"AI service not configured: {exc}")
        return jsonify({"error": "AI service is not configured on the server."}), 503
    except Exception as exc:
        current_app.logger.error(f"Unified Engine AI Error: {exc}")
        return jsonify({"error": "The AI service is temporarily unavailable."}), 502

    # -- 9. Save the assistant reply ----------------------------------------
    try:
        _save_message(convo.id, "bot", ai_reply)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"Failed to save assistant message: {exc}")
        # The reply was generated successfully; still return it to the caller.

    _try_legacy_history_save(current_user_id, convo.id, "assistant", ai_reply)

    _try_token_tracking(current_user_id, provider_result.tokens_used)
    _track_api_key_usage(provider_result.tokens_used)

    # -- 10. Auto-title the conversation on first exchange -------------------
    try:
        if convo.title == "New Conversation":
            convo.title = message[:50]
            db.session.commit()
    except Exception:
        db.session.rollback()

    # -- 11. Return the response --------------------------------------------
    return jsonify({
        "status": "success",
        "reply": ai_reply,
        "conversation_id": convo.id,
        "provider": provider_result.provider,
        "usage": {
            "input_tokens": provider_result.input_tokens,
            "output_tokens": provider_result.output_tokens,
            "total_tokens": provider_result.tokens_used,
        } if provider_result.tokens_used is not None else "Usage unavailable",
    }), 200
