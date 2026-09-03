from flask_jwt_extended import decode_token
from sqlalchemy.exc import OperationalError

from app.extensions import db as database
from app.models.auth_model import AuthSession, AuthToken, OAuthAccount, token_digest
from app.models.user import User
from app.services.oauth_service import OAuthIdentity
from app.services import oauth_service
from app.workers.email_worker import start_email_worker


def _register(client, email="auth@example.com"):
    return client.post("/api/register", json={
        "name": "Auth User", "email": email, "password": "StrongPass123!",
    })


def _login(client, email="auth@example.com", password="StrongPass123!"):
    return client.post("/api/login", json={"email": email, "password": password})


def test_password_hash_and_single_use_email_verification(client, db):
    response = _register(client)
    assert response.status_code == 201
    token = response.get_json()["verification_token"]
    user = User.query.filter_by(email="auth@example.com").first()
    assert user.password_hash != "StrongPass123!"
    assert AuthToken.query.filter_by(token_hash=token_digest(token)).one().purpose == "verify_email"

    assert client.post("/api/verify-email", json={"token": token}).status_code == 200
    assert client.post("/api/verify-email", json={"token": token}).status_code == 400
    db.session.refresh(user)
    assert user.is_verified is True


def test_auth_email_delivery_is_bounded_and_reports_result(app, monkeypatch):
    app.config.update({
        "MAIL_SERVER": "smtp.example.test", "MAIL_PORT": 587,
        "MAIL_USE_TLS": True, "MAIL_USERNAME": "mailer",
        "MAIL_PASSWORD": "secret", "MAIL_DEFAULT_SENDER": "noreply@example.test",
        "MAIL_TIMEOUT_SECONDS": 7,
    })
    captured = {}

    def fake_send(subject, recipient, body, html_body, smtp_config):
        captured.update(smtp_config)

    monkeypatch.setattr("app.workers.email_worker._send_email_task", fake_send)
    assert start_email_worker(app, "Verify", "user@example.test", "body") is True
    assert captured["MAIL_TIMEOUT_SECONDS"] == 7

    def failed_send(*args, **kwargs):
        raise OSError("unavailable")

    monkeypatch.setattr("app.workers.email_worker._send_email_task", failed_send)
    assert start_email_worker(app, "Verify", "user@example.test", "body") is False


def test_forgot_password_is_truthful_when_email_delivery_is_not_configured(client, app):
    app.config.update({
        "TESTING": False,
        "MAIL_SERVER": "",
        "MAIL_USERNAME": "",
        "MAIL_PASSWORD": "",
        "MAIL_DEFAULT_SENDER": "",
    })
    response = client.post("/api/forgot-password", json={"email": "unknown@example.test"})
    assert response.status_code == 503
    assert response.get_json() == {"error": "Password reset email delivery is not configured."}


def test_registration_requires_configured_delivery_when_verification_is_required(client, app, db):
    app.config.update({
        "TESTING": False,
        "REQUIRE_EMAIL_VERIFICATION": True,
        "MAIL_SERVER": "",
        "MAIL_USERNAME": "",
        "MAIL_PASSWORD": "",
        "MAIL_DEFAULT_SENDER": "",
    })

    response = _register(client, "verification-delivery-unavailable@example.test")

    assert response.status_code == 503
    assert response.get_json() == {"error": "Registration is temporarily unavailable. Please try again later."}
    assert User.query.filter_by(email="verification-delivery-unavailable@example.test").first() is None


def test_registration_database_outage_is_rolled_back_and_truthful(client, monkeypatch, caplog):
    original_rollback = database.session.rollback
    rolled_back = []

    def unavailable_flush():
        raise OperationalError("INSERT INTO users", {}, OSError("connection closed"))

    def rollback():
        rolled_back.append(True)
        original_rollback()

    monkeypatch.setattr(database.session, "flush", unavailable_flush)
    monkeypatch.setattr(database.session, "rollback", rollback)
    response = client.post("/api/register", json={
        "name": "Unavailable Database", "email": "outage@example.test", "password": "StrongPass123!",
    })
    assert response.status_code == 503
    assert response.get_json() == {"error": "Registration is temporarily unavailable. Please try again later."}
    assert rolled_back == [True]
    assert "category=DATABASE_UNAVAILABLE" in caplog.text
    assert "request_id=" in caplog.text


def test_logout_revokes_current_session(client):
    _register(client)
    login = _login(client).get_json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    assert client.get("/api/sessions", headers=headers).status_code == 200
    assert client.post("/api/logout", headers=headers).status_code == 200
    assert client.get("/api/sessions", headers=headers).status_code == 401


def test_logout_all_revokes_every_database_session(client):
    _register(client)
    first = _login(client).get_json()["access_token"]
    second = _login(client).get_json()["access_token"]
    assert client.post("/api/logout-all", headers={"Authorization": f"Bearer {first}"}).status_code == 200
    assert client.get("/api/sessions", headers={"Authorization": f"Bearer {second}"}).status_code == 401
    assert all(not item.is_valid for item in AuthSession.query.all())


def test_password_reset_is_hashed_single_use_and_revokes_sessions(client, db):
    _register(client)
    user = User.query.filter_by(email="auth@example.com").one()
    access_token = _login(client).get_json()["access_token"]
    reset = client.post("/api/forgot-password", json={"email": "auth@example.com"}).get_json()["reset_token"]
    record = AuthToken.query.filter_by(token_hash=token_digest(reset)).one()
    assert record.purpose == "password_reset"

    assert client.post("/api/reset-password", json={
        "token": reset, "new_password": "NewStrong456!", "confirm_password": "Different456!",
    }).status_code == 400
    response = client.post("/api/reset-password", json={
        "token": reset, "new_password": "NewStrong456!", "confirm_password": "NewStrong456!",
    })
    assert response.status_code == 200
    db.session.refresh(user)
    assert user.is_verified is True
    assert client.post("/api/reset-password", json={
        "token": reset, "new_password": "Another789!", "confirm_password": "Another789!",
    }).status_code == 400
    assert client.get("/api/sessions", headers={"Authorization": f"Bearer {access_token}"}).status_code == 401
    assert _login(client, password="NewStrong456!").status_code == 200


def test_change_password_requires_matching_confirmation(client):
    _register(client)
    access_token = _login(client).get_json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    assert client.post("/api/settings/password", headers=headers, json={
        "old_password": "StrongPass123!",
        "new_password": "NewStrong456!",
        "confirm_password": "Different456!",
    }).status_code == 400

    assert client.post("/api/settings/password", headers=headers, json={
        "old_password": "StrongPass123!",
        "new_password": "NewStrong456!",
        "confirm_password": "NewStrong456!",
    }).status_code == 200
    assert _login(client, password="NewStrong456!").status_code == 200


def test_oauth_start_uses_state_nonce_and_pkce(client, app):
    app.config.update({
        "GOOGLE_OAUTH_CLIENT_ID": "test-client",
        "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
        "GOOGLE_OAUTH_REDIRECT_URI": "https://example.test/api/oauth/google/callback",
    })
    response = client.get("/api/oauth/google/start")
    assert response.status_code == 302
    location = response.headers["Location"]
    assert "state=" in location
    assert "nonce=" in location
    assert "code_challenge=" in location
    assert "client_secret" not in location


def test_oauth_start_is_truthful_when_configuration_is_incomplete(client, app):
    app.config.update({
        "GOOGLE_OAUTH_CLIENT_ID": "client-only",
        "GOOGLE_OAUTH_CLIENT_SECRET": "",
        "GOOGLE_OAUTH_REDIRECT_URI": "https://example.test/api/oauth/google/callback",
    })
    response = client.get("/api/oauth/google/start")
    assert response.status_code == 503
    assert response.get_json() == {"error": "OAuth provider is not configured."}


def test_oidc_jwks_uses_the_configured_timeout(app, monkeypatch):
    captured = {}

    class JwkClient:
        def __init__(self, url, timeout):
            captured.update(url=url, timeout=timeout)

        def get_signing_key_from_jwt(self, token):
            return type("Key", (), {"key": "public-key"})()

    monkeypatch.setattr(oauth_service.jwt, "PyJWKClient", JwkClient)
    monkeypatch.setattr(oauth_service.jwt, "decode", lambda *args, **kwargs: {
        "sub": "subject", "email": "user@example.test", "email_verified": True,
        "nonce": "nonce", "name": "User",
    })
    app.config["OAUTH_HTTP_TIMEOUT_SECONDS"] = 4
    identity = oauth_service._verified_oidc_identity(
        "google", {"jwks": "https://example.test/jwks", "client_id": "client", "issuer": "issuer"},
        "token", "nonce",
    )
    assert identity.subject == "subject"
    assert captured == {"url": "https://example.test/jwks", "timeout": 4}


def test_registration_reports_delivery_failure_and_resend_is_enumeration_safe(client, app, monkeypatch):
    app.config.update({
        "TESTING": False, "REQUIRE_EMAIL_VERIFICATION": True,
        "MAIL_SERVER": "smtp.example.test", "MAIL_USERNAME": "mailer",
        "MAIL_PASSWORD": "mail-secret", "MAIL_DEFAULT_SENDER": "noreply@example.test",
    })
    monkeypatch.setattr("app.routes.auth_routes._deliver_auth_email", lambda *args: False)
    registration = _register(client, "delivery-failed@example.test")
    assert registration.status_code == 503
    assert registration.get_json()["verification_required"] is True
    assert User.query.filter_by(email="delivery-failed@example.test").one()

    known = client.post("/api/resend-verification", json={"email": "delivery-failed@example.test"})
    unknown = client.post("/api/resend-verification", json={"email": "unknown@example.test"})
    assert known.status_code == unknown.status_code == 200
    assert known.get_json() == unknown.get_json()


def test_authentication_endpoints_reject_non_object_json(client):
    for path in ("/api/forgot-password", "/api/reset-password", "/api/resend-verification", "/api/verify-email"):
        response = client.post(path, json=["not", "an", "object"])
        assert response.status_code == 400
        assert response.get_json() == {"error": "Invalid JSON payload."}


def test_oauth_provider_status_exposes_configuration_without_secrets(client, app):
    app.config.update({
        "GOOGLE_OAUTH_CLIENT_ID": "test-client",
        "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
        "GOOGLE_OAUTH_REDIRECT_URI": "https://example.test/api/oauth/google/callback",
    })
    response = client.get("/api/oauth/providers")
    assert response.status_code == 200
    assert response.get_json() == {"providers": {
        "google": True, "github": False, "apple": False, "microsoft": False,
    }}
    assert "test-secret" not in response.get_data(as_text=True)


def test_oauth_browser_exchange_is_http_only_and_single_use(client, db, monkeypatch):
    user = User(name="OAuth User", email="oauth@example.com", is_verified=True)
    db.session.add(user)
    db.session.flush()
    db.session.add(OAuthAccount(
        user_id=user.id, provider="google", provider_subject="subject-existing",
        provider_email=user.email,
    ))
    db.session.commit()
    identity = OAuthIdentity("google", "subject-existing", user.email, True, user.name)
    monkeypatch.setattr(
        "app.routes.auth_routes.complete_authorization", lambda provider, code, state: (identity, None)
    )

    callback = client.get("/api/oauth/google/callback?code=test&state=test")
    assert callback.status_code == 302
    assert callback.headers["Location"].endswith("/login.html?oauth=complete")
    cookie = callback.headers["Set-Cookie"]
    assert "oauth_exchange=" in cookie
    assert "HttpOnly" in cookie
    assert "Path=/api/oauth/session" in cookie
    assert not any(item.is_valid for item in AuthSession.query.all())

    exchange = client.post("/api/oauth/session")
    assert exchange.status_code == 200
    payload = exchange.get_json()
    assert payload["user"]["id"] == user.id
    decoded = decode_token(payload["access_token"])
    assert decoded["sub"] == user.id
    assert AuthSession.query.filter_by(id=decoded["sid"], user_id=user.id).one().is_valid
    assert client.post("/api/oauth/session").status_code == 401


def test_oauth_does_not_auto_merge_matching_email(client, monkeypatch):
    _register(client, "existing@example.com")
    identity = OAuthIdentity("google", "subject-1", "existing@example.com", True, "Existing")
    monkeypatch.setattr(
        "app.routes.auth_routes.complete_authorization", lambda provider, code, state: (identity, None)
    )
    response = client.get("/api/oauth/google/callback?code=test&state=test")
    assert response.status_code == 409
    assert OAuthAccount.query.count() == 0


def test_oauth_account_cannot_be_linked_to_second_user(client, db, monkeypatch):
    _register(client, "first@example.com")
    first = User.query.filter_by(email="first@example.com").one()
    db.session.add(OAuthAccount(
        user_id=first.id, provider="google", provider_subject="subject-1",
        provider_email="first@example.com",
    ))
    second_response = _register(client, "second@example.com")
    assert second_response.status_code == 201
    second_token = _login(client, "second@example.com").get_json()["access_token"]
    second_id = decode_token(second_token)["sub"]
    identity = OAuthIdentity("google", "subject-1", "first@example.com", True, "First")
    monkeypatch.setattr(
        "app.routes.auth_routes.complete_authorization", lambda provider, code, state: (identity, second_id)
    )
    response = client.get("/api/oauth/google/callback?code=test&state=test")
    assert response.status_code == 409


def test_oauth_link_does_not_complete_for_disabled_user(client, db, monkeypatch):
    user = User(name="Disabled", email="disabled-link@example.com", is_verified=True, status="Disabled")
    db.session.add(user)
    db.session.commit()
    identity = OAuthIdentity("google", "subject-disabled", "disabled-link@example.com", True, "Disabled")
    monkeypatch.setattr(
        "app.routes.auth_routes.complete_authorization", lambda provider, code, state: (identity, user.id)
    )

    response = client.get("/api/oauth/google/callback?code=test&state=test")

    assert response.status_code == 401
    assert OAuthAccount.query.filter_by(provider="google", provider_subject="subject-disabled").first() is None


def test_oauth_upstream_failure_is_normalized_without_details(client, monkeypatch, caplog):
    secret_detail = "upstream-secret-response"
    monkeypatch.setattr(
        "app.routes.auth_routes.complete_authorization",
        lambda *args: (_ for _ in ()).throw(oauth_service.OAuthProviderError(secret_detail)),
    )
    response = client.get("/api/oauth/google/callback?code=test&state=test")
    assert response.status_code == 502
    assert response.get_json() == {"error": "OAuth provider is temporarily unavailable."}
    assert secret_detail not in caplog.text
