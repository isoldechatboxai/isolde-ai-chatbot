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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    messages = db.relationship(
        "Message", backref="conversation", lazy=True, cascade="all, delete-orphan",
        order_by="Message.created_at"
    )

    def to_dict(self, include_messages=False):
        data = {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "language": self.language,
            "created_at": self.created_at.isoformat(),
        }
