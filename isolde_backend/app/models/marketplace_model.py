# app/models/marketplace_model.py
from datetime import datetime
import uuid
from app.extensions import db

class Developer(db.Model):
    __tablename__ = 'developers'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    developer_name = db.Column(db.String(100), nullable=False)
    api_key = db.Column(db.String(255), default=lambda: f"ilk_{uuid.uuid4().hex}", unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "developer_name": self.developer_name,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class Plugin(db.Model):
    __tablename__ = 'plugins'

    id = db.Column(db.Integer, primary_key=True)
    developer_id = db.Column(db.Integer, db.ForeignKey('developers.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    plugin_key = db.Column(db.String(100), unique=True, nullable=False) # e.g. "github-sync-pro"
    version = db.Column(db.String(20), default='1.0.0')
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), default='Productivity') # Productivity, Coding, Finance, etc.
    status = db.Column(db.String(30), default='Published') # Published, Pending, Rejected
    downloads_count = db.Column(db.Integer, default=0)
    rating_avg = db.Column(db.Float, default=5.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "developer_id": self.developer_id,
            "name": self.name,
            "plugin_key": self.plugin_key,
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "status": self.status,
            "downloads_count": self.downloads_count,
            "rating_avg": self.rating_avg,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class PluginInstallation(db.Model):
    __tablename__ = 'plugin_installations'

    id = db.Column(db.Integer, primary_key=True)
    plugin_id = db.Column(db.Integer, db.ForeignKey('plugins.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, nullable=True)
    org_id = db.Column(db.Integer, nullable=True) # Optional organization scope
    is_enabled = db.Column(db.Boolean, default=True)
    installed_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "plugin_id": self.plugin_id,
            "user_id": self.user_id,
            "org_id": self.org_id,
            "is_enabled": self.is_enabled,
            "installed_at": self.installed_at.isoformat() if self.installed_at else None
        }