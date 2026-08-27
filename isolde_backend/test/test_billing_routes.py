import pytest
import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from app import create_app
from app.extensions import db
from app.models.user import User
from flask_jwt_extended import create_access_token
from config import Config
from app.models.billing_model import CreditBalance, CreditLedger, Invoice, Subscription
from app.services.credit_service import deduct_authoritative_usage


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    # Override engine options for SQLite in-memory compatibility
    SQLALCHEMY_ENGINE_OPTIONS = {}


@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        user = User(name="Billing User", email="billing@example.com", status="Active")
        user.set_password("StrongPass123!")
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=user.id)
        test_client = app.test_client()
        test_client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        yield test_client
        db.session.remove()
        db.drop_all()


def test_get_subscription_default(client):
    res = client.get("/api/billing/subscription")
    assert res.status_code == 200
    data = res.get_json()
    assert data["subscription"]["plan_name"] == "Free"


def test_assign_subscription(client):
    res = client.post("/api/billing/subscription", json={"plan_name": "Pro"})
    assert res.status_code == 501


def test_get_credits_default(client):
    res = client.get("/api/billing/credits")
    assert res.status_code == 200
    assert res.get_json()["credits"] == 100


@pytest.mark.parametrize("amount", [20, 99999, -20])
def test_browser_cannot_deduct_credits(client, amount):
    res = client.post("/api/billing/credits/deduct", json={"amount": amount})
    assert res.status_code == 403
    assert client.get("/api/billing/credits").get_json()["credits"] == 100


def test_checkout_fails_honestly_when_payment_provider_is_not_configured(client):
    response = client.post("/api/billing/checkout", json={"plan": "Pro"})
    assert response.status_code == 503
    assert "not configured" in response.get_json()["error"].lower()


def test_verified_payment_webhook_is_authoritative_and_idempotent(client):
    client.application.config.update({"PAYMENT_PROVIDER": "stripe", "STRIPE_SECRET_KEY": "sk_test_local", "STRIPE_WEBHOOK_SECRET": "whsec_test"})
    user_id = client.get("/api/billing/credits").get_json()["user_id"]
    event = {
        "id": "evt_verified_1", "type": "checkout.session.completed",
        "data": {"object": {"payment_status": "paid", "metadata": {"user_id": user_id, "plan": "Pro"}}},
    }
    payload = json.dumps(event, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    signature = hmac.new(b"whsec_test", timestamp.encode() + b"." + payload, hashlib.sha256).hexdigest()
    headers = {"Stripe-Signature": f"t={timestamp},v1={signature}", "Content-Type": "application/json"}

    first = client.post("/api/billing/webhook", data=payload, headers=headers)
    second = client.post("/api/billing/webhook", data=payload, headers=headers)
    assert first.status_code == 200
    assert first.get_json()["status"] == "processed"
    assert second.get_json()["status"] == "already_processed"
    assert client.get("/api/billing/subscription").get_json()["subscription"]["plan_name"] == "Pro"
    assert client.get("/api/billing/credits").get_json()["credits"] == 2000


def test_payment_webhook_rejects_invalid_signature(client):
    client.application.config.update({"PAYMENT_PROVIDER": "stripe", "STRIPE_SECRET_KEY": "sk_test_local", "STRIPE_WEBHOOK_SECRET": "whsec_test"})
    response = client.post(
        "/api/billing/webhook", data=b'{"id":"evt_bad","type":"test"}',
        headers={"Stripe-Signature": "t=1,v1=invalid", "Content-Type": "application/json"},
    )
    assert response.status_code == 400


def test_subscription_cancellation_is_scoped_to_authenticated_owner(client, monkeypatch):
    user_id = client.get("/api/billing/credits").get_json()["user_id"]
    db.session.add(Subscription(
        user_id=user_id, plan_name="Pro", status="active", provider_subscription_id="sub_owned",
    ))
    db.session.commit()
    provider = SimpleNamespace(cancel_subscription=lambda value: {"id": value, "status": "canceled"})
    monkeypatch.setattr("app.routes.billing_routes.get_payment_provider", lambda: provider)
    response = client.post("/api/billing/subscription/cancel")
    assert response.status_code == 200
    assert response.get_json()["subscription"]["status"] == "canceled"

    other = User(name="Other", email="other-billing@example.com", status="Active")
    other.set_password("StrongPass123!")
    db.session.add(other)
    db.session.commit()
    other_token = create_access_token(identity=other.id)
    assert client.post(
        "/api/billing/subscription/cancel", headers={"Authorization": f"Bearer {other_token}"}
    ).status_code == 404


def test_refund_uses_owned_invoice_amount_and_is_idempotent(client, monkeypatch):
    user_id = client.get("/api/billing/credits").get_json()["user_id"]
    invoice = Invoice(
        invoice_uid="in_owned", user_id=user_id, amount=42.50, currency="USD",
        status="paid", provider_payment_id="pi_owned",
    )
    db.session.add(invoice)
    db.session.commit()
    calls = []
    provider = SimpleNamespace(refund_payment=lambda payment_id, key: calls.append((payment_id, key)) or {"status": "succeeded"})
    monkeypatch.setattr("app.routes.billing_routes.get_payment_provider", lambda: provider)
    assert client.post(f"/api/billing/invoices/{invoice.id}/refund", json={"amount": 0.01}).status_code == 200
    assert client.post(f"/api/billing/invoices/{invoice.id}/refund", json={"amount": 999999}).get_json()["status"] == "already_refunded"
    assert calls == [("pi_owned", f"invoice-refund-{invoice.id}")]


def test_authoritative_credit_deduction_is_non_negative_and_idempotent(client):
    user_id = client.get("/api/billing/credits").get_json()["user_id"]
    balance = CreditBalance.query.filter_by(user_id=user_id).one()
    balance.credits = 2
    assert deduct_authoritative_usage(user_id, 1500, "usage-1", 1000) == 2
    db.session.commit()
    assert deduct_authoritative_usage(user_id, 1500, "usage-1", 1000) == 2
    assert CreditBalance.query.filter_by(user_id=user_id).one().credits == 0
    assert CreditLedger.query.filter_by(idempotency_key="usage-1").count() == 1
    with pytest.raises(ValueError):
        deduct_authoritative_usage(user_id, -1, "negative", 1000)


def test_generate_and_list_invoice(client):
    res = client.post("/api/billing/invoices", json={"amount": 9.99, "currency": "USD"})
    assert res.status_code == 501
    assert client.get("/api/billing/invoices").get_json()["invoices"] == []


def test_billing_requires_authentication(client):
    client.environ_base.pop("HTTP_AUTHORIZATION")
    assert client.get("/api/billing/subscription").status_code == 401
