from secrets import token_urlsafe

import pytest

from app import create_app
from app.extensions import db
from app.models.user import User
from config import Config


@pytest.fixture
def demo_app(tmp_path):
    demo_password = token_urlsafe(24)

    class DemoConfig(Config):
        TESTING = True
        ENVIRONMENT = "demo"
        IS_PRODUCTION = False
        IS_DEMO_STAGING = True
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'isolde-demo.db'}"
        SQLALCHEMY_ENGINE_OPTIONS = {}
        RATELIMIT_ENABLED = False
        UPLOAD_FOLDER = str(tmp_path / "uploads")
        LOG_DIR = str(tmp_path / "logs")
        VECTOR_STORE_DIR = str(tmp_path / "vectors")
        STORAGE_BACKEND = "s3"
        S3_BUCKET = "isolde-demo-private"
        CORS_ORIGINS = ["https://admin.demo.example"]
        DEMO_ADMIN_BOOTSTRAP_ENABLED = True
        DEMO_ADMIN_EMAIL = "demo-admin@example.test"
        DEMO_ADMIN_PASSWORD = demo_password
        DEMO_DATABASE_MARKER = "isolde-demo"
        DEMO_STORAGE_MARKER = "demo"

    application = create_app(DemoConfig)
    application.demo_test_password = demo_password
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


def test_demo_bootstrap_is_disabled_by_default(app):
    result = app.test_cli_runner().invoke(args=["provision-demo-admin"])
    assert result.exit_code != 0
    assert "disabled" in result.output.lower()


def test_demo_bootstrap_is_idempotent_and_uses_normal_admin_flow(demo_app):
    runner = demo_app.test_cli_runner()
    first = runner.invoke(args=["provision-demo-admin"])
    second = runner.invoke(args=["provision-demo-admin"])
    assert first.exit_code == second.exit_code == 0
    assert demo_app.demo_test_password not in first.output + second.output
    with demo_app.app_context():
        assert User.query.filter_by(email="demo-admin@example.test").count() == 1
    client = demo_app.test_client()
    login = client.post("/api/admin/login", json={
        "email": "demo-admin@example.test", "password": demo_app.demo_test_password,
    })
    assert login.status_code == 200
    token = login.get_json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/admin/v1/capabilities", headers=headers).status_code == 200
    assert client.get("/api/admin/v1/session", headers=headers).status_code == 200
    assert client.delete("/api/admin/v1/session", headers=headers).status_code == 200
    assert client.get("/api/admin/v1/session", headers=headers).status_code == 401


def test_production_rejects_demo_bootstrap_setting():
    class UnsafeProductionConfig(Config):
        IS_PRODUCTION = True
        DEMO_ADMIN_BOOTSTRAP_ENABLED = True

    with pytest.raises(RuntimeError, match="must never be enabled in production"):
        UnsafeProductionConfig.validate()
