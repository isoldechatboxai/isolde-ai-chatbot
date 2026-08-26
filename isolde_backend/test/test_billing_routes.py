import pytest
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


def test_deduct_credits_success(client):
    res = client.post("/api/billing/credits/deduct", json={"amount": 20})
    assert res.status_code == 200
    assert res.get_json()["remaining_credits"] == 80


def test_deduct_credits_insufficient(client):
    res = client.post("/api/billing/credits/deduct", json={"amount": 99999})
    assert res.status_code == 400


def test_deduct_credits_rejects_negative_amount(client):
    res = client.post("/api/billing/credits/deduct", json={"amount": -20})
    assert res.status_code == 400
    assert client.get("/api/billing/credits").get_json()["credits"] == 100


def test_generate_and_list_invoice(client):
    res = client.post("/api/billing/invoices", json={"amount": 9.99, "currency": "USD"})
    assert res.status_code == 501
    assert client.get("/api/billing/invoices").get_json()["invoices"] == []


def test_billing_requires_authentication(client):
    client.environ_base.pop("HTTP_AUTHORIZATION")
    assert client.get("/api/billing/subscription").status_code == 401
