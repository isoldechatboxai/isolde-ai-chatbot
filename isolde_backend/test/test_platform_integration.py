from app.extensions import db
from app.models.api_key_model import ApiKey
from app.models.user import User
from app.routes import chat_routes
from app.services import research_service
from app.services.provider_router import ProviderManager
from app.services.rag_service import RAGEmbeddingUnavailable
from flask_jwt_extended import create_access_token


def _api_key(permissions="read,write"):
    user = User(name="API User", email=f"api-{permissions.replace(',', '-')}@example.com", status="Active")
    user.set_password("StrongPass123!")
    db.session.add(user)
    db.session.flush()
    raw, key_hash, prefix = ApiKey.generate_key()
    record = ApiKey(user_id=user.id, name="Integration", key_hash=key_hash, key_prefix=prefix, permissions=permissions)
    db.session.add(record)
    db.session.commit()
    return raw, record


def test_intent_router_automatically_selects_research_for_current_questions():
    assert chat_routes._should_use_research({"research_mode": "auto"}, "What are the latest API changes?") is True
    assert chat_routes._should_use_research({"research_mode": "auto"}, "Explain photosynthesis") is False
    assert chat_routes._should_use_research({"research_mode": "off", "web_search": False}, "latest news") is False


def test_research_context_uses_fetched_evidence_and_explicit_untrusted_boundary(app):
    result = {
        "sources": [{"id": "web-1", "title": "Source", "url": "https://example.test", "snippet": "weak snippet"}],
        "evidence": [{"source_id": "web-1", "evidence": "verified full page evidence"}],
        "cross_check": {"status": "INSUFFICIENT_EVIDENCE"},
    }
    with app.app_context():
        context = chat_routes._web_search_context("question", result=result)
    assert "verified full page evidence" in context
    assert "weak snippet" not in context
    assert "BEGIN UNTRUSTED EVIDENCE" in context
    assert "INSUFFICIENT_EVIDENCE" in context


def test_research_provider_selection_is_truthful_and_single_provider(app, monkeypatch):
    app.config["TAVILY_API_KEY"] = ""
    with app.app_context():
        try:
            research_service.select_research_provider(research_service.classify_intent("latest news"))
        except research_service.ResearchUnavailable as error:
            assert str(error) == "RESEARCH_PROVIDER_NOT_CONFIGURED"
        else:
            raise AssertionError("unconfigured research provider was selected")


def test_versioned_rag_api_enforces_scope_owner_and_top_k(client, monkeypatch):
    raw, record = _api_key("read")
    captured = {}
    monkeypatch.setattr(
        "app.routes.public_api_routes.rag_search",
        lambda query, top_k, user_id, require_embedding: captured.update(
            query=query, top_k=top_k, user_id=user_id, require_embedding=require_embedding
        ) or [],
    )
    response = client.post("/api/v1/rag/query", headers={"X-API-Key": raw}, json={"query": "owned", "top_k": 3})
    assert response.status_code == 200
    assert captured == {"query": "owned", "top_k": 3, "user_id": record.user_id, "require_embedding": True}
    db.session.refresh(record)
    assert record.total_requests == 1
    assert record.last_used_at is not None
    assert client.post("/api/v1/rag/query", headers={"X-API-Key": raw}, json={"query": "x", "top_k": 11}).status_code == 400


def test_versioned_chat_requires_write_scope(client):
    raw, _record = _api_key("read")
    response = client.post("/api/v1/chat", headers={"X-API-Key": raw}, json={"message": "hello"})
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "FORBIDDEN"
    assert response.get_json()["request_id"]


def test_versioned_research_reports_not_configured_safely(client, app):
    raw, _record = _api_key("read")
    app.config["TAVILY_API_KEY"] = ""
    response = client.post("/api/v1/research", headers={"X-API-Key": raw}, json={"question": "latest release"})
    assert response.status_code == 503
    payload = response.get_json()
    assert payload["error"]["code"] == "RESEARCH_PROVIDER_NOT_CONFIGURED"
    assert payload["request_id"]


def test_versioned_capabilities_alias(client):
    legacy = client.get("/api/capabilities")
    versioned = client.get("/api/v1/capabilities")
    assert versioned.status_code == 200
    assert versioned.get_json() == legacy.get_json()
    assert versioned.get_json()["capabilities"]["api_access"] == "AVAILABLE"


def test_versioned_api_rejects_oversized_prompts_before_external_work(client, app):
    raw, _record = _api_key("read,write")
    headers = {"X-API-Key": raw}
    app.config.update({"CHAT_MAX_PROMPT_CHARS": 5, "RESEARCH_QUERY_MAX_CHARS": 5, "RAG_QUERY_MAX_CHARS": 5})
    assert client.post("/api/v1/chat", headers=headers, json={"message": "123456"}).status_code == 400
    assert client.post("/api/v1/research", headers=headers, json={"question": "123456"}).status_code == 400
    assert client.post("/api/v1/rag/query", headers=headers, json={"query": "123456"}).status_code == 400
    invalid = client.post("/api/v1/chat", headers=headers, json=["not-an-object"])
    assert invalid.status_code == 400
    assert invalid.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_versioned_rag_reports_embedding_unavailability_truthfully(client, monkeypatch):
    raw, _record = _api_key("read")
    monkeypatch.setattr(
        "app.routes.public_api_routes.rag_search",
        lambda *args, **kwargs: (_ for _ in ()).throw(RAGEmbeddingUnavailable()),
    )
    response = client.post(
        "/api/v1/rag/query", headers={"X-API-Key": raw}, json={"query": "knowledge"},
    )
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "RAG_UNAVAILABLE"


def test_provider_failures_are_categorized_without_logging_secrets(caplog, monkeypatch):
    manager = ProviderManager()
    secret = "sk-never-log-this-value"
    monkeypatch.setattr("app.services.provider_router.time.sleep", lambda _seconds: None)

    result = manager._execute_with_retry(
        lambda _timeout: (_ for _ in ()).throw(RuntimeError(f"openai API Error (429): {secret}")),
        "openai",
    )

    assert result.error == "PROVIDER_RATE_LIMITED"
    assert secret not in caplog.text
    assert "PROVIDER_RATE_LIMITED" in caplog.text


def test_stream_response_close_cleans_cancellation_state(client, monkeypatch):
    user = User(name="Stream User", email="stream-close@example.com", status="Active")
    user.set_password("StrongPass123!")
    db.session.add(user)
    db.session.commit()
    token = create_access_token(identity=user.id)
    monkeypatch.setattr(chat_routes, "_extract_and_save_memory", lambda *args: None)
    monkeypatch.setattr(chat_routes, "rag_search", lambda *args, **kwargs: [])

    response = client.post(
        "/api/chat/stream", headers={"Authorization": f"Bearer {token}"},
        json={"message": "hello", "research_mode": "off"}, buffered=False,
    )
    generation_id = response.headers["X-Generation-ID"]
    response.close()

    assert generation_id not in chat_routes._ACTIVE_GENERATIONS
