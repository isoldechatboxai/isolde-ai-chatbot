# app/models/intelligence_model.py
from datetime import datetime
from app.extensions import db

class AIInsight(db.Model):
    __tablename__ = 'ai_insights'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(50), nullable=False) # e.g., Knowledge Gap, Meeting Trend
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class Recommendation(db.Model):
    __tablename__ = 'ai_recommendations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    rec_type = db.Column(db.String(50), nullable=False) # Task, Meeting, Agent, Plugin
    content = db.Column(db.String(255), nullable=False)
    priority = db.Column(db.String(20), default='Medium') # High, Medium, Low
    is_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "rec_type": self.rec_type,
            "content": self.content,
            "priority": self.priority,
            "is_completed": self.is_completed,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class LearningProfile(db.Model):
    __tablename__ = 'learning_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, unique=True, nullable=False)
    favorite_agent = db.Column(db.String(100), default='Default Assistant')
    preferred_workspace = db.Column(db.String(100), default='General Workspace')
    frequent_prompts_count = db.Column(db.Integer, default=42)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "favorite_agent": self.favorite_agent,
            "preferred_workspace": self.preferred_workspace,
            "frequent_prompts_count": self.frequent_prompts_count,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }