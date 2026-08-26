import pytest
import hashlib
import hmac
import json
import time
from app import create_app
from app.extensions import db
from app.models.user import User
from flask_jwt_extended import create_access_token
from config import Config


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


def test_generate_and_list_invoice(client):
    res = client.post("/api/billing/invoices", json={"amount": 9.99, "currency": "USD"})
    assert res.status_code == 501
    assert client.get("/api/billing/invoices").get_json()["invoices"] == []


def test_billing_requires_authentication(client):
    client.environ_base.pop("HTTP_AUTHORIZATION")
    assert client.get("/api/billing/subscription").status_code == 401
