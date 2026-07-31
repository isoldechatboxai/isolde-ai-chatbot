# app/models/analytics_model.py

from datetime import datetime
from app.extensions import db

class AnalyticsModel(db.Model):
    """
    SQLAlchemy database model for tracking AI provider usage, token consumption, 
    costs, latency, and operational system metrics.
    """
    __tablename__ = 'analytics_metrics'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), nullable=True, index=True)
    workspace_id = db.Column(db.String(64), nullable=True, index=True)
    provider = db.Column(db.String(64), nullable=True)
    model_name = db.Column(db.String(64), nullable=True)
    prompt_tokens = db.Column(db.Integer, default=0)
    completion_tokens = db.Column(db.Integer, default=0)
    total_tokens = db.Column(db.Integer, default=0)
    cost = db.Column(db.Float, default=0.0)
    latency = db.Column(db.Float, default=0.0)  # Execution latency in seconds
    status = db.Column(db.String(32), default="success")  # success, error, rate_limited
    extra_metadata = db.Column(db.Text, nullable=True)  # JSON-encoded extra telemetry details
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self) -> dict:
        """Converts model instance to a dictionary for API serialization."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "provider": self.provider,
            "model_name": self.model_name,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "latency": self.latency,
            "status": self.status,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }   