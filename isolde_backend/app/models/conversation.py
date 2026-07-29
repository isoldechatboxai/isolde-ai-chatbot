import uuid
from datetime import datetime, timezone
from app.extensions import db


def _uuid():
    return str(uuid.uuid4())


class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), default="New Conversation")
    
    # Module 1: Added Pin and Archive fields
    is_pinned = db.Column(db.Boolean, default=False)
    is_archived = db.Column(db.Boolean, default=False)
    
    # FIX 1: Ensure datetime is timezone-naive
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    messages = db.relationship(
        "Message", backref="conversation", lazy=True, cascade="all, delete-orphan",
        order_by="Message.created_at"
    )

    def to_dict(self, include_messages=False):
        data = {
            "id": self.id,
            "title": self.title,
            "is_pinned": self.is_pinned,
            "is_archived": self.is_archived,
            # FIX 2: Safe isoformat check to prevent AttributeError
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_messages:
            data["messages"] = [m.to_dict() for m in self.messages]
        return data


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    conversation_id = db.Column(
        db.String(36), db.ForeignKey("conversations.id"), nullable=False
    )
    role = db.Column(db.String(10), nullable=False)  # 'user' | 'bot'
    content = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(10), default="en")
    
    # FIX 1: Ensure datetime is timezone-naive
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "language": self.language,
            # FIX 2: Safe isoformat check to prevent AttributeError
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }