import pytest
from app import create_app
from app.extensions import db
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_get_subscription_default(client):
    res = client.get("/api/billing/subscription")
    assert res.status_code == 200
    data = res.get_json()
    assert data["subscription"]["plan_name"] == "Free"


def test_assign_subscription(client):
    res = client.post("/api/billing/subscription", json={"plan_name": "Pro"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["subscription"]["plan_name"] == "Pro"


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


def test_generate_and_list_invoice(client):
    res = client.post("/api/billing/invoices", json={"amount": 9.99, "currency": "USD"})
    assert res.status_code == 201
    invoice_id = res.get_json()["invoice"]["invoice_id"]

    res = client.get("/api/billing/invoices")
    assert res.status_code == 200
    ids = [i["invoice_id"] for i in res.get_json()["invoices"]]
    assert invoice_id in ids