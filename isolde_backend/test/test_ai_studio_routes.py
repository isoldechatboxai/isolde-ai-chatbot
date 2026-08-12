import pytest
from app import create_app
from app.extensions import db
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    # Override engine options for SQLite in-memory compatibility
    # Must exclude pool_size/max_overflow entirely for SQLite StaticPool
    SQLALCHEMY_ENGINE_OPTIONS = {}


@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_create_custom_model(client):
    res = client.post("/api/ai-studio/models", json={
        "model_name": "My Model",
        "base_model": "gemini-flash",
        "dataset_uri": "s3://bucket/data.csv"
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["model"]["name"] == "My Model"
    assert data["model"]["status"] == "training"


def test_list_custom_models(client):
    client.post("/api/ai-studio/models", json={"model_name": "M1", "base_model": "gemini-flash"})
    res = client.get("/api/ai-studio/models")
    assert res.status_code == 200
    assert len(res.get_json()["models"]) == 1


def test_playground_prompt(client):
    res = client.post("/api/ai-studio/playground/test", json={
        "model_id": "model-1",
        "prompt": "Hello world",
        "parameters": {"temperature": 0.5}
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["model_id"] == "model-1"
    assert data["tokens_used"] > 0


def test_playground_history(client):
    client.post("/api/ai-studio/playground/test", json={"model_id": "m1", "prompt": "hi"})
    res = client.get("/api/ai-studio/playground/history")
    assert res.status_code == 200
    assert len(res.get_json()["runs"]) == 1