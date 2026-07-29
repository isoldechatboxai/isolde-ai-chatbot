# app/models/memory_model.py
from datetime import datetime
from app import db
import json

class UserMemory(db.Model):
    __tablename__ = 'user_memory'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False, default='Other')
    key = db.Column(db.String(100), nullable=True)     # e.g., "Name", "City", "Company"
    value = db.Column(db.Text, nullable=True)          # e.g., "Vikraman", "Chennai", "Google"
    memory = db.Column(db.Text, nullable=False)        # Raw / Display text
    confidence_score = db.Column(db.Float, default=1.0) # AI extraction confidence
    is_pinned = db.Column(db.Boolean, default=False)   # Pinned status
    version_history = db.Column(db.Text, nullable=True) # JSON list of past values
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        history = []
        try:
            if self.version_history:
                history = json.loads(self.version_history)
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
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }