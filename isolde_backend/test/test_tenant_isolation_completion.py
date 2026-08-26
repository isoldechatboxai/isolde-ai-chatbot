import threading

from flask_jwt_extended import create_access_token

from app.models.user import User
from app.models.workspace_model import Agent, Workspace
from app.routes import chat_routes
from app.services import rag_service


def _create_user(db, email):
    user = User(name=email.split("@")[0], email=email, status="Active")
    user.set_password("StrongPass123!")
    db.session.add(user)
    db.session.commit()
    return user


def _auth_header(user_id):
    return {"Authorization": f"Bearer {create_access_token(identity=user_id)}"}


def test_agent_endpoints_enforce_workspace_ownership(client, db):
    owner = _create_user(db, "owner@example.com")
    attacker = _create_user(db, "attacker@example.com")
    workspace = Workspace(user_id=owner.id, name="Private")
    db.session.add(workspace)
    db.session.flush()
    agent = Agent(workspace_id=workspace.id, name="Private agent", system_prompt="secret")
    db.session.add(agent)
    db.session.commit()

    headers = _auth_header(attacker.id)
    assert client.get(f"/api/workspace/{workspace.id}/agents", headers=headers).status_code == 404
    assert client.put(f"/api/agent/{agent.id}", headers=headers, json={"name": "stolen"}).status_code == 404
    assert client.delete(f"/api/agent/{agent.id}", headers=headers).status_code == 404
    assert client.post(f"/api/agent/{agent.id}/activate", headers=headers).status_code == 404

    visible = client.get("/api/agent/list", headers=headers).get_json()["agents"]
    assert visible == []


def test_stop_generation_requires_exact_owner(client, db):
    owner = _create_user(db, "stream-owner@example.com")
    attacker = _create_user(db, "stream-attacker@example.com")
    stop_event = threading.Event()
    generation_id = "private-generation"
    chat_routes._register_generation(generation_id, stop_event, owner.id, "private-conversation")
    try:
        response = client.post(
            "/api/chat/stop",
            headers=_auth_header(attacker.id),
            json={"generation_id": generation_id},
        )
        assert response.status_code == 200
        assert response.get_json()["stopped"] is False
        assert stop_event.is_set() is False

        response = client.post(
            "/api/chat/stop",
            headers=_auth_header(owner.id),
            json={"generation_id": generation_id},
        )
        assert response.get_json()["stopped"] is True
        assert stop_event.is_set() is True
    finally:
        chat_routes._unregister_generation(generation_id)


def test_authenticated_rag_search_excludes_unowned_and_other_tenant(monkeypatch):
    monkeypatch.setattr(rag_service, "embed_text", lambda _text: [1.0, 0.0])
    monkeypatch.setattr(
        rag_service,
        "_load_index",
        lambda: [
            {"text": "legacy", "filename": "legacy.txt", "vector": [1.0, 0.0], "user_id": None},
            {"text": "mine", "filename": "mine.txt", "vector": [1.0, 0.0], "user_id": "user-a"},
            {"text": "theirs", "filename": "theirs.txt", "vector": [1.0, 0.0], "user_id": "user-b"},
        ],
    )

    results = rag_service.search("question", user_id="user-a")
    assert [result["filename"] for result in results] == ["mine.txt"]
