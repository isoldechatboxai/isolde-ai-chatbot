"""
Isolde SaaS Engine — Usage Tracking & Analytics.
Refactored for compatibility with the current Unified Chat Engine.

IMPORTANT:
- Message persistence is handled by the Unified Chat Engine (Conversation/Message models).
- This module focuses ONLY on usage analytics and billing hooks.
- All functions are BEST-EFFORT and MUST NOT block or crash the chat request.
"""
import logging
from datetime import datetime, timezone
from flask import current_app
from app.extensions import db

logger = logging.getLogger(__name__)


def check_and_deduct_tokens(user_id: str, estimated_tokens: int = 0) -> tuple:
    """
    Best-effort token tracking.
    Updates the user's token usage counter if the field exists.
    NEVER rejects a request in development/free mode.
    
    Returns:
        (allowed: bool, reason: str)
    """
    try:
        from app.models.user import User
        
        user = db.session.get(User, user_id)
        if not user:
            return True, "user_not_found_but_allowed"

        # Update usage stats if the model supports it
        if hasattr(user, 'tokens_used'):
            current_usage = getattr(user, 'tokens_used', 0) or 0
            user.tokens_used = current_usage + int(estimated_tokens)
            db.session.commit()
            
        return True, "ok"
        
    except Exception as e:
        # Log but do not crash
        logger.warning(f"Token tracking failed (non-fatal): {str(e)}")
        return True, "tracking_error_non_fatal"


def save_chat_history(user_id: str, conversation_id: str, role: str, content: str) -> bool:
    """
    Legacy compatibility hook.
    
    The Unified Chat Engine already persists messages to the Message table.
    This function acts as a post-save hook to update conversation metadata
    (e.g., last_active timestamp) without creating duplicate message records.
    """
    try:
        from app.models.conversation import Conversation
        
        convo = db.session.get(Conversation, conversation_id)
        if convo:
            convo.updated_at = datetime.now(timezone.utc)
            # Optional: Update title if it's still default and this is the first user msg
            if role == 'user' and convo.title == "New Conversation":
                convo.title = content[:50].strip()
            db.session.commit()
        return True
        
    except Exception as e:
        logger.debug(f"Legacy history hook skipped (non-fatal): {str(e)}")
        return True

