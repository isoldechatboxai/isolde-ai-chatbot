"""Regression coverage for production audit findings; no external services."""
from datetime import timedelta

import pytest
from flask_jwt_extended import create_access_token

from app.models.auth_model import AuthSession, AuthToken
from app.models.user import User
from app.models.workspace_model import Workspace
from app.services.provider_router import ProviderManager


def _user_headers(db):
    user = User(name="Recovery", email="recovery@example.test", is_verified=True)
    user.set_password("OriginalPassword123!")
    db.session.add(user)
    db.session.flush()
    session = AuthSession.create(user.id, timedelta(hours=1))
    db.session.add(session)
    db.session.commit()
    return user, {"Authorization": "Bearer " + create_access_token(
        identity=user.id, additional_claims={"sid": session.id}
    )}


def test_reset_user_revokes_sessions_and_pending_tokens(app, client, db):
    user, headers = _user_headers(db)
    raw, token = AuthToken.issue(user.id, "password_reset", 15)
    db.session.add(token)
    db.session.commit()
    assert client.get("/api/profile", headers=headers).status_code == 200
    result = app.test_cli_runner().invoke(args=[
        "reset-user", "--email", "  RECOVERY@EXAMPLE.TEST  ", "--password", "RecoveredPassword123!",
    ])
    assert result.exit_code == 0, result.output
    # The CLI uses a separate application context/session from this fixture.
    db.session.expire_all()
    assert client.get("/api/profile", headers=headers).status_code == 401
    assert client.post("/api/reset-password", json={
        "token": raw, "new_password": "AttackerPassword123!", "confirm_password": "AttackerPassword123!",
    }).status_code == 400
    assert client.post("/api/login", json={
        "email": user.email, "password": "RecoveredPassword123!",
    }).status_code == 200


def test_reset_user_creates_real_verified_account(app, client):
    result = app.test_cli_runner().invoke(args=[
        "reset-user", "--email", "new-recovery@example.test", "--password", "RecoveredPassword123!",
    ])
    assert result.exit_code == 0, result.output
    login = client.post("/api/login", json={"email": "new-recovery@example.test", "password": "RecoveredPassword123!"})
    assert login.status_code == 200
    assert login.json["user"]["is_verified"] is True


def test_jwt_session_must_belong_to_subject(client, db):
    user, _ = _user_headers(db)
    other = User(name="Other", email="other-session@example.test", is_verified=True)
    db.session.add(other)
    db.session.commit()
    session = AuthSession.query.filter_by(user_id=user.id).one()
    token = create_access_token(identity=other.id, additional_claims={"sid": session.id})
    assert client.get("/api/profile", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_apple_form_callback_reaches_state_validation(client):
    response = client.post("/api/oauth/apple/callback", data={"code": "untrusted", "state": "untrusted"})
    assert response.status_code in {400, 503}
    assert response.status_code != 415
    assert client.post("/api/login", data={"email": "untrusted"}).status_code == 415


def test_readiness_checks_separate_rate_limit_redis(app, client, monkeypatch):
    import redis
    app.config.update(RATELIMIT_STORAGE_URI="redis://rate-limit.invalid/0", CANCELLATION_REDIS_URL="")
    def unavailable(*args, **kwargs):
        raise redis.ConnectionError("private connection detail")
    monkeypatch.setattr(redis.Redis, "from_url", unavailable)
    response = client.get("/api/ready")
    assert response.status_code == 503
    assert response.json["checks"]["rate_limiting"] is False
    assert "private connection detail" not in response.text
    assert client.get("/api/live").status_code == 200


def test_stream_failure_after_output_never_calls_fallback(app, monkeypatch):
    manager = ProviderManager()
    calls = []
    def broken(*args):
        calls.append("primary")
        yield "partial answer"
        raise RuntimeError("sensitive upstream body")
    def fallback(*args):
        calls.append("fallback")
        yield "different answer"
    monkeypatch.setattr(manager, "get_available_providers", lambda: ["openai", "claude"])
    monkeypatch.setattr(manager, "_get_stream_fn", lambda name: broken if name == "openai" else fallback)
    stream = manager.generate_stream("question")
    assert next(stream) == "partial answer"
    with pytest.raises(RuntimeError, match="PROVIDER_STREAM_INTERRUPTED"):
        next(stream)
    assert calls == ["primary"]


def test_closing_outer_stream_closes_upstream(app, monkeypatch):
    closed = []
    def upstream(*args):
        try:
            yield "first"
            yield "second"
        finally:
            closed.append(True)
    manager = ProviderManager()
    monkeypatch.setattr(manager, "get_available_providers", lambda: ["openai"])
    monkeypatch.setattr(manager, "_get_stream_fn", lambda name: upstream)
    stream = manager.generate_stream("question")
    assert next(stream) == "first"
    stream.close()
    assert closed == [True]


def test_unavailable_stream_raises_instead_of_returning_fake_text(app, monkeypatch):
    manager = ProviderManager()
    monkeypatch.setattr(manager, "get_available_providers", lambda: [])
    with pytest.raises(RuntimeError, match="PROVIDER_STREAM_UNAVAILABLE"):
        list(manager.generate_stream("question"))


def test_agent_validation_and_default_unset(client, db):
    user, headers = _user_headers(db)
    workspace = Workspace(user_id=user.id, name="Owned")
    db.session.add(workspace)
    db.session.commit()
    endpoint = f"/api/workspace/{workspace.id}/agents"
    for payload in ([1], {"name": 7}, {"is_default": "false"}, {"avatar_emoji": "x" * 11}):
        assert client.post(endpoint, headers=headers, json=payload).status_code == 400
    response = client.post(endpoint, headers=headers, json={"name": "Agent", "system_prompt": "Help", "is_default": True})
    assert response.status_code == 201
    agent_id = response.json["agent"]["id"]
    response = client.put(f"/api/agent/{agent_id}", headers=headers, json={"is_default": False})
    assert response.status_code == 200
    assert response.json["agent"]["is_default"] is False


def test_task_completion_persists_timestamp(client, db):
    _, headers = _user_headers(db)
    response = client.post("/api/productivity/tasks", headers=headers, json={"title": "Complete"})
    assert response.status_code == 201
    task_id = response.json["task"]["id"]
    response = client.put(f"/api/productivity/tasks/{task_id}", headers=headers, json={"status": "Completed"})
    assert response.status_code == 200
    assert response.json["task"]["completed_at"]


def test_password_change_revokes_current_and_legacy_jwt(client, db):
    user, headers = _user_headers(db)
    legacy = create_access_token(identity=user.id)
    response = client.post("/api/settings/password", headers=headers, json={
        "old_password": "OriginalPassword123!", "new_password": "ChangedPassword123!",
        "confirm_password": "ChangedPassword123!",
    })
    assert response.status_code == 200
    assert client.get("/api/profile", headers=headers).status_code == 401
    assert client.get("/api/profile", headers={"Authorization": f"Bearer {legacy}"}).status_code == 401
    assert client.post("/api/login", json={"email": user.email, "password": "ChangedPassword123!"}).status_code == 200


def test_unified_auth_does_not_swallow_route_errors(app, db):
    from app.routes.unified_chat_engine import unified_auth_required
    _, headers = _user_headers(db)
    calls = []
    @unified_auth_required("read")
    def failing_route():
        calls.append(True)
        raise ValueError("route failure")
    with app.test_request_context(headers=headers), pytest.raises(ValueError, match="route failure"):
        failing_route()
    assert calls == [True]


def test_api_key_identity_obeys_tenant_provider_policy(app, monkeypatch):
    from flask import g
    from app.services import organization_policy_service
    manager = ProviderManager()
    monkeypatch.setattr(manager, "resolve_active_provider", lambda: "gemini")
    monkeypatch.setattr(manager, "_get_provider_priority", lambda: ["openai"])
    def policy(user_id):
        assert user_id == "api-key-owner"
        return {"allowed_providers": ["openai"]}
    monkeypatch.setattr(organization_policy_service, "effective_policy_for_user", policy)
    with app.test_request_context():
        g.auth_user_id = "api-key-owner"
        assert manager.get_available_providers() == ["openai"]


def test_research_transport_pins_ip_and_verifies_hostname(monkeypatch):
    from app.services import research_service
    captured = {}
    class Raw:
        status = 200
        headers = {"Content-Type": "text/plain"}
        def close(self): captured["closed"] = True
        def release_conn(self): pass
    class Pool:
        def __init__(self, address, **kwargs): captured.update(address=address, **kwargs)
        def urlopen(self, method, path, **kwargs):
            captured.update(path=path, request=kwargs)
            return Raw()
        def close(self): captured["pool_closed"] = True
    monkeypatch.setattr(research_service.urllib3, "HTTPSConnectionPool", Pool)
    response = research_service._open_evidence("https://public.example.test/path?q=1", "8.8.8.8", 4)
    assert captured["address"] == "8.8.8.8"
    assert captured["server_hostname"] == captured["assert_hostname"] == "public.example.test"
    assert captured["cert_reqs"] == "CERT_REQUIRED"
    assert captured["request"]["redirect"] is False
    response.close()
    assert captured["closed"] and captured["pool_closed"]


@pytest.mark.parametrize("vector", [[float("nan")], [float("inf")], [0, 0], [[1, 2]], [1e100]])
def test_rag_rejects_malformed_provider_vectors(app, monkeypatch, vector):
    from app.services import rag_service
    monkeypatch.setattr(rag_service, "embed_text", lambda _: vector)
    with pytest.raises(rag_service.RAGEmbeddingUnavailable):
        rag_service.search("query", user_id="owner", require_embedding=True)


def test_legacy_import_populates_native_vector(app, db, tmp_path):
    import json
    from app.services import rag_service
    from app.models.rag_model import RAGChunk
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps([{"id": "chunk", "file_id": "document", "filename": "old.txt", "user_id": "owner", "text": "evidence", "vector": [1, 0]}]))
    assert rag_service.import_legacy_json(str(path))["chunks"] == 1
    assert list(db.session.get(RAGChunk, "chunk").embedding_vector) == [1, 0]
