from datetime import datetime
import hashlib
import secrets
import uuid

from werkzeug.security import generate_password_hash

from app.extensions import db


class Tenant(db.Model):
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    subdomain = db.Column(db.String(50), unique=True, nullable=False)
    plan_tier = db.Column(
        db.String(30),
        default='Free'
    )  # Free, Pro, Business, Enterprise
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "subdomain": self.subdomain,
            "plan_tier": self.plan_tier,
            "is_active": self.is_active,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
        }


class Subscription(db.Model):
    __tablename__ = 'subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'tenants.id',
            ondelete='CASCADE'
        ),
        nullable=False
    )
    plan_name = db.Column(
        db.String(50),
        nullable=False
    )
    status = db.Column(
        db.String(30),
        default='Active'
    )  # Active, PastDue, Canceled
    renewal_date = db.Column(
        db.DateTime,
        nullable=True
    )
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "plan_name": self.plan_name,
            "status": self.status,
            "renewal_date": (
                self.renewal_date.isoformat()
                if self.renewal_date
                else None
            ),
        }


class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'tenants.id',
            ondelete='CASCADE'
        ),
        nullable=False
    )
    amount = db.Column(
        db.Float,
        nullable=False
    )
    currency = db.Column(
        db.String(10),
        default='USD'
    )
    status = db.Column(
        db.String(30),
        default='Paid'
    )  # Paid, Pending, Failed
    invoice_date = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status,
            "invoice_date": (
                self.invoice_date.isoformat()
                if self.invoice_date
                else None
            ),
        }


class APIKey(db.Model):
    __tablename__ = 'saas_api_keys'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        nullable=False
    )

    key_name = db.Column(
        db.String(100),
        nullable=False
    )

    # Existing plaintext secret column.
    # PRESERVED intentionally.
    # Phase 4 legacy backfill/removal is out of scope.
    key_secret = db.Column(
        db.String(255),
        default=lambda: f"isk_{uuid.uuid4().hex}",
        unique=True,
        nullable=False
    )

    # Phase 2 / Phase 3 verification hash.
    key_hash = db.Column(
        db.String(255),
        nullable=True
    )

    # Safe non-secret identification prefix.
    key_prefix = db.Column(
        db.String(20),
        nullable=True
    )

    scopes = db.Column(
        db.String(255),
        default='read,write,ai'
    )

    is_active = db.Column(
        db.Boolean,
        default=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    @staticmethod
    def hash_key(raw_key):
        """
        Produce the non-recoverable SHA-256 hash used for
        Phase 3 API-key verification.

        Returns:
            SHA-256 hexadecimal digest or None for invalid input.
        """
        if not raw_key or not isinstance(raw_key, str):
            return None

        return hashlib.sha256(
            raw_key.encode("utf-8")
        ).hexdigest()

    @classmethod
    def generate_key(cls):
        """
        Phase 3 primary API-key generation.

        Returns:
            (raw_key, key_hash, key_prefix)

        Contract:
            raw_key    = "isk_" + 32 hex characters
            key_hash   = SHA-256(raw_key)
            key_prefix = first 10 characters of raw_key
        """
        raw_key = f"isk_{secrets.token_hex(16)}"

        key_hash = cls.hash_key(raw_key)

        key_prefix = raw_key[:10]

        return raw_key, key_hash, key_prefix

    @classmethod
    def generate_secure_key(cls):
        """
        Phase 2 backward-compatible API-key generation.

        IMPORTANT:
        This method is intentionally independent from generate_key().

        Phase 2 contract:

            raw_key, key_prefix, key_hash = (
                APIKey.generate_secure_key()
            )

        Contract:
            raw_key    = "isk_" + 32 hex characters
            key_prefix = first 12 characters of raw_key
            key_hash   = Werkzeug password hash of raw_key

        The returned key_hash is compatible with:

            check_password_hash(key_hash, raw_key)

        This method must NOT delegate to generate_key(), because
        Phase 2 and Phase 3 intentionally use different hash/prefix
        contracts.
        """
        raw_key = f"isk_{secrets.token_hex(16)}"

        key_prefix = raw_key[:12]

        key_hash = generate_password_hash(raw_key)

        return raw_key, key_prefix, key_hash

    @classmethod
    def verify_key(cls, raw_key):
        """
        Verify a supplied raw API key against the stored
        Phase 3 SHA-256 key_hash.

        Returns:
            Matching active APIKey record or None.

        No plaintext fallback is used.
        """
        if not raw_key or not isinstance(raw_key, str):
            return None

        key_hash = cls.hash_key(raw_key)

        if not key_hash:
            return None

        record = cls.query.filter_by(
            key_hash=key_hash
        ).first()

        if not record:
            return None

        if not record.is_active:
            return None

        return record

    def to_dict(self):
        """
        Serialize only safe API-key metadata.

        SECURITY CONTRACT:
        Never expose:
            - key_secret
            - key_hash

        key_prefix is safe to expose.
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "key_name": self.key_name,
            "key_prefix": self.key_prefix,
            "scopes": self.scopes,
            "is_active": self.is_active,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
        }