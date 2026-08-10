"""
User account service layer.

Provides reusable account/profile operations for route handlers.
All functions return a consistent dictionary:

{
    "success": bool,
    "message": str,
    "data": dict | None
}
"""

from flask import current_app

from app.extensions import db
from app.models.user import User
from app.utils.validators import is_valid_email, is_valid_password


MAX_NAME_LENGTH = 120
MAX_EMAIL_LENGTH = 180
MAX_PASSWORD_LENGTH = 128
MAX_LANGUAGE_LENGTH = 10
MAX_VOICE_LENGTH = 50
MAX_PERSONA_NOTES_LENGTH = 5000


def _success(message, data=None):
    return {
        "success": True,
        "message": message,
        "data": data,
    }


def _failure(message):
    return {
        "success": False,
        "message": message,
        "data": None,
    }


def _commit(message, data=None):
    try:
        db.session.commit()
        return _success(message, data)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("User service database commit failed.")
        return _failure("Database operation failed. Please try again.")


def _get_user(user):
    """
    Return a fresh, session-bound User instance.

    Accepts either a User model instance or a raw user ID string.
    """
    if user is None:
        return None

    user_id = user if isinstance(user, str) else getattr(user, "id", None)

    if not user_id:
        return None

    return db.session.get(User, user_id)


def _email_exists(email, exclude_user_id=None):
    normalized_email = email.lower()

    query = db.session.query(User.id).filter(
        db.func.lower(User.email) == normalized_email
    )

    if exclude_user_id:
        query = query.filter(User.id != exclude_user_id)

    return db.session.query(query.exists()).scalar()


def _settings_payload(user):
    return {
        "user_id": user.id,
        "preferred_language": user.preferred_language or "en",
        "preferred_voice": user.preferred_voice or "default",
        "persona_notes": user.persona_notes or "",
    }


def get_user_profile(user):
    user = _get_user(user)

    if not user:
        return _failure("User not found.")

    try:
        payload = user.to_dict()
    except Exception:
        current_app.logger.exception("Failed to serialize user profile.")
        return _failure("Unable to load user profile.")

    return _success("User profile retrieved.", payload)


def update_profile(user, data):
    user = _get_user(user)

    if not user:
        return _failure("User not found.")

    if not isinstance(data, dict):
        return _failure("Invalid profile payload.")

    changed = False

    if "name" in data:
        name = data.get("name")

        if not isinstance(name, str) or not name.strip():
            return _failure("Name cannot be empty.")

        name = name.strip()

        if len(name) > MAX_NAME_LENGTH:
            return _failure(f"Name must be {MAX_NAME_LENGTH} characters or fewer.")

        if user.name != name:
            user.name = name
            changed = True

    if "email" in data:
        email = data.get("email")

        if not isinstance(email, str) or not email.strip():
            return _failure("Email cannot be empty.")

        email = email.strip().lower()

        if len(email) > MAX_EMAIL_LENGTH:
            return _failure(f"Email must be {MAX_EMAIL_LENGTH} characters or fewer.")

        if not is_valid_email(email):
            return _failure("Invalid email address.")

        current_email = (user.email or "").lower()

        if email != current_email:
            if _email_exists(email, exclude_user_id=user.id):
                return _failure("Email is already in use.")

            user.email = email
            changed = True

    if not changed:
        return _failure("No profile changes provided.")

    payload = user.to_dict()
    return _commit("Profile updated.", payload)


def get_user_settings(user):
    user = _get_user(user)

    if not user:
        return _failure("User not found.")

    return _success("User settings retrieved.", _settings_payload(user))


def update_settings(user, data):
    user = _get_user(user)

    if not user:
        return _failure("User not found.")

    if not isinstance(data, dict):
        return _failure("Invalid settings payload.")

    changed = False

    if "preferred_language" in data:
        preferred_language = data.get("preferred_language")

        if not isinstance(preferred_language, str) or not preferred_language.strip():
            return _failure("Preferred language cannot be empty.")

        preferred_language = preferred_language.strip().lower()

        if len(preferred_language) > MAX_LANGUAGE_LENGTH:
            return _failure(
                f"Preferred language must be {MAX_LANGUAGE_LENGTH} characters or fewer."
            )

        if user.preferred_language != preferred_language:
            user.preferred_language = preferred_language
            changed = True

    if "preferred_voice" in data:
        preferred_voice = data.get("preferred_voice")

        if not isinstance(preferred_voice, str) or not preferred_voice.strip():
            return _failure("Preferred voice cannot be empty.")

        preferred_voice = preferred_voice.strip()

        if len(preferred_voice) > MAX_VOICE_LENGTH:
            return _failure(
                f"Preferred voice must be {MAX_VOICE_LENGTH} characters or fewer."
            )

        if user.preferred_voice != preferred_voice:
            user.preferred_voice = preferred_voice
            changed = True

    if "persona_notes" in data:
        persona_notes = data.get("persona_notes")

        if persona_notes is None:
            cleaned_persona_notes = None
        elif isinstance(persona_notes, str):
            cleaned_persona_notes = persona_notes.strip()

            if len(cleaned_persona_notes) > MAX_PERSONA_NOTES_LENGTH:
                return _failure(
                    "Persona notes must be "
                    f"{MAX_PERSONA_NOTES_LENGTH} characters or fewer."
                )
        else:
            return _failure("Persona notes must be a string.")

        if user.persona_notes != cleaned_persona_notes:
            user.persona_notes = cleaned_persona_notes
            changed = True

    if not changed:
        return _failure("No setting changes provided.")

    payload = _settings_payload(user)
    return _commit("Settings updated.", payload)


def change_password(user, old_password, new_password):
    user = _get_user(user)

    if not user:
        return _failure("User not found.")

    if not isinstance(old_password, str) or not old_password:
        return _failure("Current password is required.")

    if not isinstance(new_password, str) or not new_password:
        return _failure("New password is required.")

    if len(old_password) > MAX_PASSWORD_LENGTH:
        return _failure("Current password is too long.")

    if len(new_password) > MAX_PASSWORD_LENGTH:
        return _failure(f"New password must be {MAX_PASSWORD_LENGTH} characters or fewer.")

    password_is_valid, password_reason = is_valid_password(new_password)

    if not password_is_valid:
        return _failure(password_reason)

    try:
        password_matches = user.check_password(old_password)
    except Exception:
        current_app.logger.exception("Password verification failed unexpectedly.")
        password_matches = False

    if not password_matches:
        return _failure("Current password is incorrect.")

    if old_password == new_password:
        return _failure("New password must be different from the current password.")

    user.set_password(new_password)

    return _commit("Password changed.", None)


def delete_account(user):
    user = _get_user(user)

    if not user:
        return _failure("User not found.")

    try:
        from app.models.memory_model import UserMemory

        UserMemory.query.filter_by(user_id=user.id).delete(
            synchronize_session=False
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to remove user memories during account deletion.")
        return _failure("Account deletion failed.")

    try:
        from app.models.chat_extended_models import (
            Bookmark,
            ChatFolder,
            ChatTag,
            ConversationTagMap,
            MessageReaction,
            PinnedChat,
        )
        from app.models.conversation import Conversation

        PinnedChat.query.filter_by(user_id=user.id).delete(
            synchronize_session=False
        )

        ChatFolder.query.filter_by(user_id=user.id).delete(
            synchronize_session=False
        )

        tag_ids = (
            db.session.query(ChatTag.id)
            .filter(ChatTag.user_id == user.id)
            .subquery()
        )

        ConversationTagMap.query.filter(
            ConversationTagMap.tag_id.in_(tag_ids.select())
        ).delete(synchronize_session=False)

        ChatTag.query.filter_by(user_id=user.id).delete(
            synchronize_session=False
        )

        conversation_ids = (
            db.session.query(Conversation.id)
            .filter(Conversation.user_id == user.id)
            .subquery()
        )

        ConversationTagMap.query.filter(
            ConversationTagMap.conversation_id.in_(conversation_ids.select())
        ).delete(synchronize_session=False)

        MessageReaction.query.filter_by(user_id=user.id).delete(
            synchronize_session=False
        )

        Bookmark.query.filter_by(user_id=user.id).delete(
            synchronize_session=False
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to remove extended chat data during account deletion.")
        return _failure("Account deletion failed.")

    try:
        from app.models.conversation import Conversation, Message
        from app.models.feedback import Feedback

        message_ids = (
            db.session.query(Message.id)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(Conversation.user_id == user.id)
            .subquery()
        )

        Feedback.query.filter(
            Feedback.message_id.in_(message_ids.select())
        ).update(
            {Feedback.message_id: None},
            synchronize_session=False,
        )

        Feedback.query.filter_by(user_id=user.id).update(
            {Feedback.user_id: None},
            synchronize_session=False,
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to detach feedback data during account deletion.")
        return _failure("Account deletion failed.")

    try:
        from app.models.uploaded_file import UploadedFile

        if hasattr(UploadedFile, "user_id"):
            UploadedFile.query.filter_by(user_id=user.id).delete(
                synchronize_session=False
            )
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to remove uploaded file metadata during account deletion."
        )
        return _failure("Account deletion failed.")

    try:
        db.session.delete(user)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to mark user for deletion.")
        return _failure("Account deletion failed.")

    return _commit("Account deleted.", None)