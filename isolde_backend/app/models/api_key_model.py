import secrets
import hashlib
from datetime import datetime
from app.extensions import db


class ApiKey(db.Model):
    """
    Production-ready SQLAlchemy model for API Key management & Developer Platform.
    Stores ONLY hashed keys for maximum security.
    """
    __tablename__ = 'api_keys'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False, index=True)

    # Name/Label for the key (e.g., "Production Web App", "Mobile Client")
    name = db.Column(db.String(100), nullable=False)

    # Store ONLY the SHA-256 hash of the key, never the plaintext key
    key_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)

    # Hint for user identification (e.g., first 10 chars like 'isk_1ab23c')
    key_prefix = db.Column(db.String(12), nullable=False)

    # Role-Based Access Control (RBAC) & Permissions (comma-separated)
    permissions = db.Column(db.String(255), default="read,write", nullable=False)

    # Status flags
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_revoked = db.Column(db.Boolean, default=False, nullable=False)

    # Expiration and Tracking
    expires_at = db.Column(db.DateTime, nullable=True)
    last_used_at = db.Column(db.DateTime, nullable=True)

    # Usage and Analytics Counters
    total_requests = db.Column(db.Integer, default=0, nullable=False)
    total_tokens_used = db.Column(db.Integer, default=0, nullable=False)
    total_cost = db.Column(db.Float, default=0.0, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    @staticmethod
    def generate_key():
        """
        Generates a secure cryptographically random API key.
        Format: isk_<random hex>
        Returns: (raw_key, key_hash, key_prefix)
        """
        raw_key = f"isk_{secrets.token_hex(32)}"
        key_prefix = raw_key[:10]  # e.g., 'isk_1ab23c'
        key_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
        return raw_key, key_hash, key_prefix

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """Hashes a plaintext API key using SHA-256 for secure comparison."""
        return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

    def to_dict(self):
        """Returns safe metadata (excludes hash for security)."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "key_prefix": self.key_prefix,
            "permissions": self.permissions.split(",") if self.permissions else [],
            "is_active": self.is_active,
            "is_revoked": self.is_revoked,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "total_requests": self.total_requests,
            "total_tokens_used": self.total_tokens_used,
            "total_cost": self.total_cost,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else datetime.utcnow().isoformat()
            )
        }