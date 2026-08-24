# app/services/api_key_service.py
from datetime import datetime

from flask import current_app

from app.extensions import db
from app.models.api_key_model import ApiKey
from app.models.user import User


def create_api_key(user_id: str, name: str, permissions: str = "read,write", expires_at=None) -> tuple:
    """
    Generates a new API key for a developer, stores only its SHA-256 hash,
    and returns the PLAINTEXT key ONCE to the user along with metadata.
    """
    try:
        raw_key, key_hash, key_prefix = ApiKey.generate_key()

        new_key = ApiKey(
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            permissions=permissions,
            expires_at=expires_at,
            is_active=True,
            is_revoked=False
        )
        db.session.add(new_key)
        db.session.commit()

        current_app.logger.info(
            f"API Key created successfully for user {user_id} with name '{name}'"
        )

        # Return plaintext key once. This is intentional and must remain the only
        # point where the raw key is exposed.
        return raw_key, new_key.to_dict()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            f"Failed to create API key for user {user_id}"
        )
        raise


def verify_api_key(raw_key: str):
    """
    Verify an Isolde-owned API key.

    Flow:
    raw key -> SHA/hash -> database lookup -> status/expiry checks -> record.
    Never stores or returns the raw API key.
    """
    if not raw_key or not isinstance(raw_key, str):
        return None

    raw_key = raw_key.strip()

    if not raw_key:
        return None

    try:
        key_hash = ApiKey.hash_key(raw_key)
    except Exception:
        return None

    try:
        record = (
            ApiKey.query
            .filter(ApiKey.key_hash == key_hash)
            .first()
        )
    except Exception:
        return None

    if record is None:
        return None

    # Explicit revocation check.
    if bool(getattr(record, "is_revoked", False)):
        return None

    # Explicit active check.
    if hasattr(record, "is_active"):
        if not bool(getattr(record, "is_active")):
            return None

    # Optional expiration check.
    expires_at = getattr(record, "expires_at", None)

    if expires_at is not None:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)

        try:
            if expires_at.tzinfo is None:
                now = datetime.now()
            if expires_at <= now:
                return None
        except TypeError:
            # Handle legacy naive/aware datetime combinations safely.
            try:
                if expires_at <= datetime.now():
                    return None
            except Exception:
                return None

    return record

def track_api_usage(key_hash: str, tokens_used: int = 0, cost: float = 0.0):
    """
    Tracks token consumption and estimated cost per API key.
    """
    try:
        record = ApiKey.query.filter_by(key_hash=key_hash).first()
        if record:
            record.total_tokens_used += int(tokens_used or 0)
            record.total_cost += float(cost or 0.0)
            db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to track API usage.")


def revoke_api_key(key_id: int, user_id: str) -> bool:
    """
    Revokes an API key so it can no longer be used.
    Ownership is enforced by filtering on both key_id and user_id.
    """
    try:
        record = ApiKey.query.filter_by(id=key_id, user_id=user_id).first()
        if not record:
            return False

        record.is_revoked = True
        record.is_active = False
        db.session.commit()

        current_app.logger.info(
            f"API Key ID {key_id} revoked for user {user_id}"
        )
        return True
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            f"Failed to revoke API key ID {key_id}"
        )
        return False


def list_user_keys(user_id: str) -> list:
    """
    Returns all API keys associated with a user.
    Returns metadata only. The raw key and key hash are never returned.
    """
    records = (
        ApiKey.query
        .filter_by(user_id=user_id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )
    return [record.to_dict() for record in records]


def key_prefix_safe(key_hash: str) -> str:
    """
    Compatibility helper.

    This should no longer be required for secure logging because API key
    records now provide a non-secret key_prefix field.
    """
    return key_hash[:8] if key_hash else "unknown"