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

    # --- 🌟 ADMIN FIELDS ---
    role = db.Column(db.String(50), default="Client")
    status = db.Column(db.String(20), default="Active")
    tokens_used = db.Column(db.Integer, default=0) # புதுசு: AI Token usage-ஐ ட்ராக் செய்ய

    # personalization / long-term memory
    preferred_language = db.Column(db.String(10), default="en")
    preferred_voice = db.Column(db.String(50), default="default")
    persona_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

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
            "role": self.role,
            "status": self.status,
            "tokens_used": self.tokens_used,
            "preferred_language": self.preferred_language,
            "preferred_voice": self.preferred_voice,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ==========================================
# 🌟 CHAT MODEL
# ==========================================
class Chat(db.Model):
    __tablename__ = 'chats'
    
    id = db.Column(db.Integer, primary_key=True)
    user_message = db.Column(db.Text, nullable=False)
    ai_response = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self):
        return {
            "id": self.id,
            "user_message": self.user_message,
            "ai_response": self.ai_response,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else None
        }


# ==========================================
# 🌟 SETTING MODEL (Dynamic API & Model Save)
# ==========================================
class Setting(db.Model):
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            "key": self.key,
            "value": self.value
        }


# ==========================================
# 🌟 NEW: FEEDBACK MODEL (Real-time feedback)
# ==========================================
class Feedback(db.Model):
    __tablename__ = 'feedbacks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(120), nullable=False)
    rating = db.Column(db.String(50), nullable=False) 
    comment = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self):
        return {
            "id": self.id,
            "user": self.user_name,
            "rating": self.rating,
            "comment": self.comment,
            "date": self.timestamp.strftime("%Y-%m-%d") if self.timestamp else None
        }


# ==========================================
# 🌟 NEW: BROADCAST MODEL (Push Notifications)
# ==========================================
class Broadcast(db.Model):
    __tablename__ = 'broadcasts'
    
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    target = db.Column(db.String(50), default="All Users")
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self):
        return {
            "id": self.id,
            "message": self.message,
            "target": self.target,
            "date": self.timestamp.strftime("%Y-%m-%d") if self.timestamp else None
        }


# ==========================================
# 🌟 NEW: PROMO CODE MODEL (Marketing)
# ==========================================
class PromoCode(db.Model):
    __tablename__ = 'promo_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    discount = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default="Active")

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "discount": self.discount,
            "status": self.status
        }