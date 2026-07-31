import datetime
from flask import current_app
from app.extensions import db

# 1. Dynamic Token & Plan Enforcement Engine
def check_and_deduct_tokens(user_id, estimated_tokens=50):
    try:
        from app.models.user_model import User
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"
        
        # Check if user has active subscription or available tokens
        tokens_used = getattr(user, 'tokens_used', 0) or 0
        max_limit = getattr(user, 'token_limit', 10000) # Default free limit
        
        if tokens_used + estimated_tokens > max_limit:
            return False, "Token limit exceeded for your current plan. Please upgrade!"
        
        user.tokens_used = tokens_used + estimated_tokens
        db.session.commit()
        return True, "Success"
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Token deduction error: {e}")
        return True, "Bypassed on error"

# 2. Unified Chat History Logger
def save_chat_history(user_id, conversation_id, role, message):
    try:
        from app.models.chat_model import ChatMessage # Adjust model name if needed
        chat_entry = ChatMessage(
            user_id=user_id,
            conversation_id=conversation_id,
            role=role,
            content=message,
            timestamp=datetime.datetime.utcnow()
        )
        db.session.add(chat_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to save chat history: {e}")

# 3. Feedback Sync Handler
def process_user_feedback(user_id, message_id, rating, comments=""):
    try:
        from app.models.feedback_model import Feedback
        feedback = Feedback(
            user_id=user_id,
            message_id=message_id,
            rating=rating,
            comments=comments,
            created_at=datetime.datetime.utcnow()
        )
        db.session.add(feedback)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Feedback sync error: {e}")
        return False