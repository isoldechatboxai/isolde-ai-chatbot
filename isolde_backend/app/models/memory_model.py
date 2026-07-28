# app/models/memory_model.py
from app import db
from datetime import datetime
from app.models.user import User  # 🌟 Imported from user.py

class UserMemory(db.Model):
    __tablename__ = 'user_memory'

    id = db.Column(db.Integer, primary_key=True)
    # 🌟 FIX: User model uses String(36) UUID for primary key, so user_id must match String(36)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    memory = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='Other', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "memory": self.memory,
            "category": self.category,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }