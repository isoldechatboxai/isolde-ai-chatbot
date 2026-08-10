# app/models/memory_model.py
from datetime import datetime, timezone

import json

from app.extensions import db


class UserMemory(db.Model):
    __tablename__ = "user_memory"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.String(100), nullable=False, index=True)

    category = db.Column(db.String(50), nullable=False, default="Other")

    # e.g., "Name", "City", "Company"
    key = db.Column(db.String(100), nullable=True)

    # e.g., "Vikraman", "Chennai", "Google"
    value = db.Column(db.Text, nullable=True)

    # Raw / Display text
    memory = db.Column(db.Text, nullable=False)

    # AI extraction confidence
    confidence_score = db.Column(db.Float, default=1.0)

    # Pinned status
    is_pinned = db.Column(db.Boolean, default=False)

    # JSON list of past values
    version_history = db.Column(db.Text, nullable=True)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    def to_dict(self):
        history = []

        try:
            if self.version_history:
                parsed_history = json.loads(self.version_history)

                if isinstance(parsed_history, list):
                    history = parsed_history
        except Exception:
            history = []

        return {
            "id": self.id,
            "user_id": self.user_id,
            "category": self.category,
            "key": self.key or "General",
            "value": self.value or self.memory,
            "memory": self.memory,
            "confidence_score": self.confidence_score,
            "is_pinned": self.is_pinned,
            "version_history": history,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }