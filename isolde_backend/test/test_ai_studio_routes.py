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
    # Must exclude pool_size/max_overflow entirely for SQLite StaticPool
    SQLALCHEMY_ENGINE_OPTIONS = {}


@pytest.fixture
def client(monkeypatch):
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        user = User(name="Studio User", email="studio@example.com", status="Active")
        user.set_password("StrongPass123!")
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=user.id)
        test_client = app.test_client()
        test_client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        monkeypatch.setattr(
            "app.routes.ai_studio_routes.generate_reply",
            lambda prompt, system_context="": f"Provider response: {prompt}",
        )
        yield test_client
        db.session.remove()
        db.drop_all()


def test_create_custom_model(client):
    res = client.post("/api/ai-studio/models", json={
        "model_name": "My Model",
        "base_model": "gemini-flash",
        "dataset_uri": "s3://bucket/data.csv"
    })
    assert res.status_code == 501
    assert res.get_json()["status"] == "unavailable"


def test_list_custom_models(client):
    res = client.get("/api/ai-studio/models")
    assert res.status_code == 200
    assert res.get_json()["models"] == []


def test_playground_prompt(client):
    res = client.post("/api/ai-studio/playground/test", json={
        "model_id": "model-1",
        "prompt": "Hello world",
        "parameters": {"temperature": 0.5}
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["model_id"] == "model-1"
    assert data["output"] == "Provider response: Hello world"
    assert data["tokens_used"] is None
    assert data["usage"] == "Usage unavailable"


def test_playground_history(client):
    client.post("/api/ai-studio/playground/test", json={"model_id": "m1", "prompt": "hi"})
    res = client.get("/api/ai-studio/playground/history")
    assert res.status_code == 200
    assert len(res.get_json()["runs"]) == 1
