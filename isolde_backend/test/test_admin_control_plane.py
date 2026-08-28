from flask_jwt_extended import create_access_token

from app.models.auth_model import AuthSession
from app.models.enterprise_models import AuditLog
from app.models.user import Setting, User


def _user(db, email, role="Client"):
    user = User(name=role, email=email, role=role, status="Active", is_verified=True)
    user.set_password("StrongPass123!")
    db.session.add(user)
    db.session.commit()
    return user


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(identity=user.id)}"}


def test_public_product_configuration_is_safe_and_has_truthful_defaults(client, db):
    db.session.add(Setting(key="openai_api_key", value="enc:never-public"))
    db.session.commit()
    response = client.get("/api/product/config")
    assert response.status_code == 200
    data = response.get_json()
    assert data["features"]["image"] is True
    assert data["assets"]["upload_status"] == "NOT_CONFIGURED"
    assert "never-public" not in response.get_data(as_text=True)


def test_admin_configuration_is_authorized_validated_persisted_and_audited(client, db):
    member = _user(db, "member-control@example.com")
    assert client.get("/api/admin/v1/configuration", headers=_headers(member)).status_code == 403

    admin = _user(db, "admin-control@example.com", "Admin")
    headers = _headers(admin)
    invalid = client.patch(
        "/api/admin/v1/configuration", headers=headers,
        json={"branding": {"announcement": "<script>bad</script>"}},
    )
    assert invalid.status_code == 400
    updated = client.patch(
        "/api/admin/v1/configuration", headers=headers,
        json={
            "features": {"marketplace": True, "video": False},
            "branding": {"application_name": "ISOLDE", "announcement": "Scheduled maintenance"},
        },
    )
    assert updated.status_code == 200
    public = client.get("/api/product/config").get_json()
    assert public["features"]["marketplace"] is True
    assert public["features"]["video"] is False
    assert public["branding"]["application_name"] == "ISOLDE"
    audit = AuditLog.query.filter_by(action="ADMIN_CONFIGURATION_UPDATE").one()
    assert audit.actor_user_id == admin.id
    assert "Scheduled maintenance" not in audit.details


def test_provider_control_is_effective_but_never_returns_secrets(client, db):
    admin = _user(db, "provider-admin@example.com", "Admin")
    db.session.add(Setting(key="openai_api_key", value="unit-" + "credential"))
    db.session.commit()
    headers = _headers(admin)
    changed = client.patch(
        "/api/admin/v1/providers/configuration", headers=headers,
        json={"active_provider": "openai", "models": {"openai": "gpt-4o-mini"}},
    )
    assert changed.status_code == 200
    current = client.get("/api/admin/v1/providers/configuration", headers=headers)
    assert current.status_code == 200
    assert current.get_json()["configuration"]["active_provider"] == "openai"
    assert current.get_json()["configuration"]["models"]["openai"] == "gpt-4o-mini"
    assert "api_key" not in current.get_data(as_text=True)
    assert client.post(
        "/api/admin/settings", headers=headers,
        json={"key": "arbitrary_setting", "value": "unsafe"},
    ).status_code == 400

    unavailable = client.patch(
        "/api/admin/v1/providers/configuration", headers=headers,
        json={"active_provider": "claude"},
    )
    assert unavailable.status_code == 422
    assert unavailable.get_json()["capability"] == "NOT_CONFIGURED"


def test_admin_session_control_and_versioned_contract(client, app, db):
    admin = _user(db, "session-admin@example.com", "Admin")
    target = _user(db, "session-target@example.com")
    session = AuthSession.create(target.id, app.config["JWT_ACCESS_TOKEN_EXPIRES"])
    db.session.add(session)
    db.session.commit()
    headers = _headers(admin)
    assert client.get("/api/admin/v1/capabilities", headers=headers).status_code == 200
    assert client.get("/api/admin/v1/release", headers=headers).status_code == 200
    for path in (
        "/api/admin/v1/dashboard", "/api/admin/v1/users",
        "/api/admin/v1/organizations", "/api/admin/v1/projects",
        "/api/admin/v1/conversations", "/api/admin/v1/billing/summary",
        "/api/admin/v1/billing/subscriptions", "/api/admin/v1/providers/status",
        "/api/admin/v1/operations",
    ):
        assert client.get(path, headers=headers).status_code == 200
    listed = client.get(f"/api/admin/v1/users/{target.id}/sessions", headers=headers)
    assert listed.status_code == 200
    assert listed.get_json()["sessions"][0]["active"] is True
    revoked = client.post(f"/api/admin/v1/users/{target.id}/sessions/revoke-all", headers=headers)
    assert revoked.status_code == 200
    assert revoked.get_json()["revoked_sessions"] == 1
    assert db.session.get(AuthSession, session.id).is_valid is False
