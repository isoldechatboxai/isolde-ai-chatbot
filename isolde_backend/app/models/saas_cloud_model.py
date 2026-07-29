# app/models/saas_cloud_model.py
from datetime import datetime
import uuid
from app.extensions import db

class Tenant(db.Model):
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    subdomain = db.Column(db.String(50), unique=True, nullable=False)
    plan_tier = db.Column(db.String(30), default='Free') # Free, Pro, Business, Enterprise
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "subdomain": self.subdomain,
            "plan_tier": self.plan_tier,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class Subscription(db.Model):
    __tablename__ = 'subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    plan_name = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(30), default='Active') # Active, PastDue, Canceled
    renewal_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "plan_name": self.plan_name,
            "status": self.status,
            "renewal_date": self.renewal_date.isoformat() if self.renewal_date else None
        }

class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='USD')
    status = db.Column(db.String(30), default='Paid') # Paid, Pending, Failed
    invoice_date = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status,
            "invoice_date": self.invoice_date.isoformat() if self.invoice_date else None
        }

class APIKey(db.Model):
    __tablename__ = 'saas_api_keys'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    key_name = db.Column(db.String(100), nullable=False)
    key_secret = db.Column(db.String(255), default=lambda: f"isk_{uuid.uuid4().hex}", unique=True, nullable=False)
    scopes = db.Column(db.String(255), default='read,write,ai')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "key_name": self.key_name,
            "key_secret": self.key_secret[:10] + "..." if self.key_secret else "",
            "scopes": self.scopes,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }