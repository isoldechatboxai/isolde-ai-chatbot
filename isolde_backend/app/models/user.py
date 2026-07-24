import uuid
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


def _uuid():
    return str(uuid.uuid4())


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(64), nullable=True)
    reset_otp = db.Column(db.String(10), nullable=True)
    reset_otp_expires = db.Column(db.DateTime, nullable=True)

    # personalization / long-term memory
    preferred_language = db.Column(db.String(10), default="en")
    preferred_voice = db.Column(db.String(50), default="default")
    persona_notes = db.Column(db.Text, nullable=True)  # freeform long-term memory

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    conversations = db.relationship(
        "Conversation", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "is_verified": self.is_verified,
            "preferred_language": self.preferred_language,
            "preferred_voice": self.preferred_voice,
            "created_at": self.created_at.isoformat(),
        }
