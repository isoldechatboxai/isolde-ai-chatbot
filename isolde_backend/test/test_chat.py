import json
import uuid
import pytest
from flask_jwt_extended import create_access_token

from app.models.user import User
from app.routes import chat_routes
from app.services.cancellation_service import cancellation_store


def _auth_client(client, db, email="stream-tester@example.com"):
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(name="Stream Tester", email=email, status="Active")
        user.set_password("StrongPass123!")
        db.session.add(user)
        db.session.commit()
    token = create_access_token(identity=user.id)
    return user, {"Authorization": f"Bearer {token}"}


def test_chat_stream_headers_and_initial_bytes(client, db, monkeypatch):
    user, headers = _auth_client(client, db, "test-stream-headers@example.com")
    monkeypatch.setattr(chat_routes, "_extract_and_save_memory", lambda *args: None)
    monkeypatch.setattr(chat_routes, "rag_search", lambda *args, **kwargs: [])

    # Mock provider stream to yield test chunks
    test_chunks = ["Hello", " world", "!"]
    monkeypatch.setattr(
        chat_routes,
        "generate_reply_stream",
        lambda *args, **kwargs: (c for c in test_chunks),
    )

    response = client.post(
        "/api/chat/stream",
        headers=headers,
        json={"message": "hello", "research_mode": "off"},
        buffered=False,
    )

    assert response.status_code == 200
    assert response.headers.get("Content-Type") == "text/event-stream; charset=utf-8"
    assert "no-transform" in response.headers.get("Cache-Control", "")
    assert response.headers.get("X-Accel-Buffering") == "no"
    assert response.headers.get("Connection") == "keep-alive"
    gen_id = response.headers.get("X-Generation-ID")
    assert gen_id is not None and len(gen_id) > 0

    raw_data = response.get_data(as_text=True)
    # 1. Must start with : ping\n\n
    assert raw_data.startswith(": ping\n\n")

    # 2. Must contain initial event with generation_id
    assert f'"event": "generation_started"' in raw_data
    assert f'"generation_id": "{gen_id}"' in raw_data

    # 3. Must contain token deltas formatted with delta and generation_id
    for chunk in test_chunks:
        expected = json.dumps({"delta": chunk, "generation_id": gen_id}, ensure_ascii=False)
        assert f"data: {expected}\n\n" in raw_data

    # 4. Must end with [DONE]
    assert raw_data.endswith("data: [DONE]\n\n")

    # 5. Generation must be released in finally block
    assert gen_id not in chat_routes._ACTIVE_GENERATIONS


def test_chat_stream_via_chat_endpoint_with_stream_true(client, db, monkeypatch):
    user, headers = _auth_client(client, db, "test-chat-stream-flag@example.com")
    monkeypatch.setattr(chat_routes, "_extract_and_save_memory", lambda *args: None)
    monkeypatch.setattr(chat_routes, "rag_search", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        chat_routes,
        "generate_reply_stream",
        lambda *args, **kwargs: (c for c in ["Streaming", " response"]),
    )

    response = client.post(
        "/api/chat",
        headers=headers,
        json={"message": "hello", "stream": True, "research_mode": "off"},
        buffered=False,
    )

    assert response.status_code == 200
    assert response.headers.get("Content-Type") == "text/event-stream; charset=utf-8"
    assert response.headers.get("X-Accel-Buffering") == "no"
    raw_data = response.get_data(as_text=True)
    assert raw_data.startswith(": ping\n\n")
    assert "data: [DONE]\n\n" in raw_data


def test_chat_cancel_endpoint_contracts(client, db):
    user, headers = _auth_client(client, db, "test-cancel-contracts@example.com")

    # 400 when missing generation_id
    resp_empty = client.post("/api/chat/cancel", headers=headers, json={})
    assert resp_empty.status_code == 400
    assert "generation_id is required" in resp_empty.get_json()["error"]

    # 404 when unknown generation_id
    unknown_id = str(uuid.uuid4())
    resp_unknown = client.post("/api/chat/cancel", headers=headers, json={"generation_id": unknown_id})
    assert resp_unknown.status_code == 404
    assert resp_unknown.get_json()["ok"] is False

    # 200 when cancelling active registered generation
    active_id = f"test-active-{uuid.uuid4()}"
    owner = f"user:{user.id}"
    cancellation_store.register(active_id, owner, conversation_id="conv-1")
    try:
        resp_cancel = client.post("/api/chat/cancel", headers=headers, json={"generation_id": active_id})
        assert resp_cancel.status_code == 200
        data = resp_cancel.get_json()
        assert data["ok"] is True
        assert data["stopped"] is True
        assert cancellation_store.is_cancelled(active_id, owner) is True
    finally:
        cancellation_store.release(active_id, owner)

    # 200 via backwards-compatible /api/chat/stop
    stop_id = f"test-stop-{uuid.uuid4()}"
    cancellation_store.register(stop_id, owner, conversation_id="conv-2")
    try:
        resp_stop = client.post("/api/chat/stop", headers=headers, json={"generation_id": stop_id})
        assert resp_stop.status_code == 200
        data = resp_stop.get_json()
        assert data["ok"] is True
        assert data["stopped"] is True
    finally:
        cancellation_store.release(stop_id, owner)


def test_chat_stream_error_emits_error_event_and_done(client, db, monkeypatch):
    user, headers = _auth_client(client, db, "test-stream-error@example.com")
    monkeypatch.setattr(chat_routes, "_extract_and_save_memory", lambda *args: None)
    monkeypatch.setattr(chat_routes, "rag_search", lambda *args, **kwargs: [])

    def _failing_stream(*args, **kwargs):
        raise RuntimeError("Provider failed mid-call")

    monkeypatch.setattr(chat_routes, "generate_reply_stream", _failing_stream)

    response = client.post(
        "/api/chat/stream",
        headers=headers,
        json={"message": "hello", "research_mode": "off"},
        buffered=False,
    )

    assert response.status_code == 200
    raw_data = response.get_data(as_text=True)
    # UI receives error event and [DONE] so it never hangs
    assert '"event": "error"' in raw_data
    assert "data: [DONE]\n\n" in raw_data
