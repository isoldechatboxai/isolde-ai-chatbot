# app/models/enterprise_models.py
from datetime import datetime
from app.extensions import db

class PromptVersion(db.Model):
    __tablename__ = 'prompt_versions'
    id = db.Column(db.Integer, primary_key=True)
    prompt_key = db.Column(db.String(100), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TokenCostLog(db.Model):
    __tablename__ = 'token_cost_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, index=True)
    workspace_id = db.Column(db.Integer, index=True)
    organization_id = db.Column(db.Integer, index=True)
    provider = db.Column(db.String(50))
    model = db.Column(db.String(50))
    input_tokens = db.Column(db.Integer, default=0)
    output_tokens = db.Column(db.Integer, default=0)
    total_tokens = db.Column(db.Integer, default=0)
    cost = db.Column(db.Float, default=0.0)
    latency_ms = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class ScoredMemory(db.Model):
    __tablename__ = 'scored_memories'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, index=True)
    content = db.Column(db.Text, nullable=False)
    importance_score = db.Column(db.Float, default=0.0)
    confidence_score = db.Column(db.Float, default=0.0)
    recency_score = db.Column(db.Float, default=0.0)
    usage_score = db.Column(db.Float, default=0.0)
    final_score = db.Column(db.Float, default=0.0, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AuditLog(db.Model):
    __tablename__ = 'enterprise_audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, index=True)
    action = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(50))
    status = db.Column(db.String(20))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)