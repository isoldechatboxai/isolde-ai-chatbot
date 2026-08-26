from flask_jwt_extended import decode_token

from app.models.auth_model import AuthSession, AuthToken, OAuthAccount, token_digest
from app.models.user import User
from app.services.oauth_service import OAuthIdentity


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


def test_password_reset_is_hashed_single_use_and_revokes_sessions(client):
    _register(client)
    access_token = _login(client).get_json()["access_token"]
    reset = client.post("/api/forgot-password", json={"email": "auth@example.com"}).get_json()["reset_token"]
    record = AuthToken.query.filter_by(token_hash=token_digest(reset)).one()
    assert record.purpose == "password_reset"

    response = client.post("/api/reset-password", json={"token": reset, "new_password": "NewStrong456!"})
    assert response.status_code == 200
    assert client.post("/api/reset-password", json={"token": reset, "new_password": "Another789!"}).status_code == 400
    assert client.get("/api/sessions", headers={"Authorization": f"Bearer {access_token}"}).status_code == 401
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
