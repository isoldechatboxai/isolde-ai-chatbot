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
    Validates an incoming plaintext API key.

    Checks:
     - key format
     - key exists by hash
     - key is active
     - key is not revoked
     - key is not expired
     - owning user exists
     - owning user is Active
     - admin permission is only valid for Admin users

    Updates last_used_at timestamp and request counter on successful validation.
    """
    if not raw_key or not isinstance(raw_key, str) or not raw_key.startswith("isk_"):
        return None

    key_hash = ApiKey.hash_key(raw_key)

    # Query database by hash only. The raw key is never stored.
    api_key_record = ApiKey.query.filter_by(key_hash=key_hash).first()
    if not api_key_record:
        return None

    # Key lifecycle checks.
    if not api_key_record.is_active or api_key_record.is_revoked:
        return None

    # Check expiration if set.
    if api_key_record.expires_at and datetime.utcnow() > api_key_record.expires_at:
        return None

    # Enforce owner account status.
    #
    # API-key authentication must not bypass the same account-status rules
    # that apply to JWT authentication.
    try:
        owner = db.session.get(User, api_key_record.user_id)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("API key owner lookup failed.")
        return None

    if not owner or owner.status != "Active":
        return None

    # Normalize key permissions.
    key_permissions = {
        permission.strip().lower()
        for permission in (api_key_record.permissions or "").split(",")
        if permission.strip()
    }

    # Do not allow admin API-key permissions unless the owning account is Admin.
    if "admin" in key_permissions and getattr(owner, "role", None) != "Admin":
        return None

    # Update usage metadata safely.
    try:
        api_key_record.last_used_at = datetime.utcnow()
        api_key_record.total_requests += 1
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.error(
            f"Failed to update API key stats for key prefix {api_key_record.key_prefix}"
        )

    return api_key_record


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