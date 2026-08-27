from flask_jwt_extended import decode_token

from app.models.auth_model import AuthSession
from app.models.user import User
from app.models.collaboration_model import Organization
from app.models.user import Setting
from app.services.provider_router import ProviderManager


def test_admin_login_creates_revocable_database_session(client, db):
    admin = User(name="Admin User", email="admin-login@example.com", role="Admin", status="Active")
    admin.set_password("StrongAdminPass123!")
    db.session.add(admin)
    db.session.commit()

    login = client.post("/api/admin/login", json={
        "email": admin.email, "password": "StrongAdminPass123!",
    })
    assert login.status_code == 200
    token = login.get_json()["access_token"]
    claims = decode_token(token)
    session = AuthSession.query.filter_by(id=claims["sid"], user_id=admin.id).one()
    assert session.is_valid

    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/admin/dashboard", headers=headers).status_code == 200
    assert client.get("/api/admin/tenants", headers=headers).status_code == 200
    providers = client.get("/api/admin/provider-status", headers=headers)
    assert providers.status_code == 200
    assert all(value in {"Configured", "Not configured"} for value in providers.get_json()["providers"].values())
    assert client.get("/api/admin/billing-summary", headers=headers).status_code == 200
    operations = client.get("/api/admin/operations", headers=headers)
    assert operations.status_code == 200
    assert "operations" in operations.get_json()
    assert client.get("/api/admin/operations/log-summary", headers=headers).status_code == 200

    tenant = Organization(name="Admin Managed", owner_id=admin.id)
    db.session.add(tenant)
    db.session.commit()
    updated = client.patch(
        f"/api/admin/tenants/{tenant.id}", headers=headers, json={"status": "Suspended"}
    )
    assert updated.status_code == 200
    assert updated.get_json()["tenant"]["status"] == "Suspended"

    saved = client.post(
        "/api/admin/settings", headers=headers,
        json={"key": "openai_api_key", "value": "provider-secret-value"},
    )
    assert saved.status_code == 200
    stored = Setting.query.filter_by(key="openai_api_key").one()
    assert stored.value.startswith("enc:")
    assert "provider-secret-value" not in client.get("/api/admin/settings", headers=headers).get_data(as_text=True)
    assert ProviderManager()._get_setting("openai_api_key") == "provider-secret-value"
    assert client.post("/api/logout", headers=headers).status_code == 200
    assert client.get("/api/admin/dashboard", headers=headers).status_code == 401


def test_phase7_pages_are_real_api_clients_without_fake_paid_actions(client):
    admin_page = client.get("/admin.html")
    assert admin_page.status_code == 200
    assert b"admin.js" in admin_page.data

    billing_page = client.get("/billing.html")
    assert billing_page.status_code == 200
    assert b"Generate Test Invoice" not in billing_page.data
    assert b"Subscribe" not in billing_page.data

    studio_page = client.get("/ai_studio.html")
    assert studio_page.status_code == 200
    assert b"Create Model" not in studio_page.data
    assert b"Fine-tuning is not configured" in studio_page.data


def test_frontend_scripts_use_server_authoritative_product_endpoints(client):
    billing_script = client.get("/billing.js")
    assert billing_script.status_code == 200
    assert b"/api/billing/credits/deduct" not in billing_script.data
    assert b"/api/billing/invoices" in billing_script.data

    admin_script = client.get("/admin.js")
    assert admin_script.status_code == 200
    assert b"/api/admin/login" in admin_script.data
    assert b"/api/admin/dashboard" in admin_script.data
    assert b"/api/admin/users" in admin_script.data
