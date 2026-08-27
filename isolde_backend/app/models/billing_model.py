from datetime import datetime
from app.extensions import db

class Subscription(db.Model):
    __tablename__ = 'billing_subscriptions'
    __table_args__ = (
        db.UniqueConstraint('provider_subscription_id', name='uq_billing_subscription_provider_id'),
        {'extend_existing': True},
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False, index=True)
    plan_name = db.Column(db.String(50), default='Free', nullable=False)
    status = db.Column(db.String(30), default='active', nullable=False)
    provider_subscription_id = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "plan_name": self.plan_name,
            "status": self.status,
            "provider_managed": bool(self.provider_subscription_id),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class CreditBalance(db.Model):
    __tablename__ = 'billing_credit_balances'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    credits = db.Column(db.Integer, default=100, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "credits": self.credits,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class Invoice(db.Model):
    __tablename__ = 'billing_invoices'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    invoice_uid = db.Column(db.String(64), unique=True, nullable=False)
    user_id = db.Column(db.String(100), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='USD', nullable=False)
    status = db.Column(db.String(30), default='generated', nullable=False)
    provider_payment_id = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "invoice_id": self.invoice_uid,
            "user_id": self.user_id,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class PaymentEvent(db.Model):
    __tablename__ = "billing_payment_events"

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(32), nullable=False)
    event_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    event_type = db.Column(db.String(100), nullable=False)
    processed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class CreditLedger(db.Model):
    __tablename__ = "billing_credit_ledger"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False, index=True)
    idempotency_key = db.Column(db.String(255), unique=True, nullable=False, index=True)
    credits_delta = db.Column(db.Integer, nullable=False)
    source = db.Column(db.String(50), nullable=False)
    provider_tokens = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
