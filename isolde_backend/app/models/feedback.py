import uuid
from datetime import datetime, timezone
from app.extensions import db


def _uuid():
    return str(uuid.uuid4())


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    message_id = db.Column(db.String(36), db.ForeignKey("messages.id"), nullable=True)

    question = db.Column(db.Text, nullable=False)
    bot_answer = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    correction_text = db.Column(db.Text, nullable=True)  # user-supplied correction

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "question": self.question,
            "bot_answer": self.bot_answer,
            "is_correct": self.is_correct,
            "correction_text": self.correction_text,
            "created_at": self.created_at.isoformat(),
        }
