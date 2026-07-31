from datetime import datetime
from app.extensions import db


class CustomModel(db.Model):
    __tablename__ = 'custom_models'

    id = db.Column(db.Integer, primary_key=True)
    model_uid = db.Column(db.String(120), unique=True, nullable=False)
    user_id = db.Column(db.String(100), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    base_model = db.Column(db.String(100), nullable=False)
    dataset_uri = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(30), default='training', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "model_id": self.model_uid,
            "user_id": self.user_id,
            "name": self.name,
            "base_model": self.base_model,
            "dataset_uri": self.dataset_uri,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class PlaygroundRun(db.Model):
    __tablename__ = 'playground_runs'

    id = db.Column(db.Integer, primary_key=True)
    model_uid = db.Column(db.String(120), nullable=False, index=True)
    user_id = db.Column(db.String(100), nullable=False, index=True)
    prompt = db.Column(db.Text, nullable=False)
    output = db.Column(db.Text, nullable=True)
    parameters = db.Column(db.Text, nullable=True)
    tokens_used = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "model_id": self.model_uid,
            "user_id": self.user_id,
            "prompt": self.prompt,
            "output": self.output,
            "tokens_used": self.tokens_used,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }