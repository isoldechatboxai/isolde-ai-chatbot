# app/services/api_key_service.py

from datetime import datetime
from flask import current_app
from app.extensions import db
from app.models.api_key_model import ApiKey

def create_api_key(user_id: str, name: str, permissions: str = "read,write", expires_at=None) -> tuple:
    """
    Generates a new API key for a developer, stores only its SHA-256 hash,
    and returns the PLAINTEXT key ONCE to the user along with metadata.
    """
    try:
        # Generate secure key, hash, and prefix
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

        current_app.logger.info(f"API Key created successfully for user {user_id} with name '{name}'")
        
        # Return plaintext key (crucial: this is the ONLY time the plaintext is visible)
        return raw_key, new_key.to_dict()

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to create API key for user {user_id}: {str(e)}")
        raise e

def verify_api_key(raw_key: str):
    """
    Validates an incoming plaintext API key.
    Checks if it exists, is active, not revoked, and not expired.
    Updates last_used_at timestamp on successful validation.
    """
    if not raw_key or not raw_key.startswith("isk_"):
        return None

    key_hash = ApiKey.hash_key(raw_key)
    
    # Query database by hash
    api_key_record = ApiKey.query.filter_by(key_hash=key_hash).first()

    if not api_key_record:
        return None

    # Security validations
    if not api_key_record.is_active or api_key_record.is_revoked:
        return None

    # Check expiration if set
    if api_key_record.expires_at and datetime.utcnow() > api_key_record.expires_at:
        return None

    # Update usage metadata safely
    try:
        api_key_record.last_used_at = datetime.utcnow()
        api_key_record.total_requests += 1
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update API key stats for hash {key_prefix_safe(key_hash)}: {str(e)}")

    return api_key_record

def track_api_usage(key_hash: str, tokens_used: int = 0, cost: float = 0.0):
    """Tracks token consumption, latency, and estimated cost per API key."""
    try:
        record = ApiKey.query.filter_by(key_hash=key_hash).first()
        if record:
            record.total_tokens_used += tokens_used
            record.total_cost += cost
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to track API usage: {str(e)}")

def revoke_api_key(key_id: int, user_id: str) -> bool:
    """Revokes an API key so it can no longer be used."""
    try:
        record = ApiKey.query.filter_by(id=key_id, user_id=user_id).first()
        if not record:
            return False

        record.is_revoked = True
        record.is_active = False
        db.session.commit()
        
        current_app.logger.info(f"API Key ID {key_id} revoked for user {user_id}")
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to revoke API key ID {key_id}: {str(e)}")
        return False

def list_user_keys(user_id: str) -> list:
    """Returns all API keys associated with a user (metadata only)."""
    records = ApiKey.query.filter_by(user_id=user_id).order_by(ApiKey.created_at.desc()).all()
    return [r.to_dict() for r in records]

def key_prefix_safe(key_hash: str) -> str:
    return key_hash[:8] if key_hash else "unknown"