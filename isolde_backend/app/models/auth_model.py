import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def token_digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class AuthSession(db.Model):
    __tablename__ = "auth_sessions"

    id = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    last_seen_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)
    user_agent_hash = db.Column(db.String(64), nullable=True)
    ip_hash = db.Column(db.String(64), nullable=True)

    @classmethod
    def create(cls, user_id, lifetime, user_agent=None, ip_address=None):
        now = utcnow()
        return cls(
            id=secrets.token_urlsafe(32),
            user_id=str(user_id),
            created_at=now,
            last_seen_at=now,
            expires_at=now + lifetime,
            user_agent_hash=token_digest(user_agent) if user_agent else None,
            ip_hash=token_digest(ip_address) if ip_address else None,
        )

    @property
    def is_valid(self):
        return self.revoked_at is None and self.expires_at > utcnow()


class AuthToken(db.Model):
    __tablename__ = "auth_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = db.Column(db.String(32), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)

    @classmethod
    def issue(cls, user_id, purpose, lifetime_minutes):
        raw = secrets.token_urlsafe(32)
        record = cls(
            user_id=str(user_id),
            purpose=purpose,
            token_hash=token_digest(raw),
            expires_at=utcnow() + timedelta(minutes=lifetime_minutes),
        )
        return raw, record

    @property
    def is_valid(self):
        return self.used_at is None and self.expires_at > utcnow()


class OAuthAccount(db.Model):
    __tablename__ = "oauth_accounts"
    __table_args__ = (
        db.UniqueConstraint("provider", "provider_subject", name="uq_oauth_provider_subject"),
        db.UniqueConstraint("user_id", "provider", name="uq_oauth_user_provider"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = db.Column(db.String(32), nullable=False)
    provider_subject = db.Column(db.String(255), nullable=False)
    provider_email = db.Column(db.String(180), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    def to_dict(self):
        return {
            "provider": self.provider,
            "email": self.provider_email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RevokedToken(db.Model):
    __tablename__ = "revoked_tokens"

    jti = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.String(36), nullable=False, index=True)
    revoked_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
