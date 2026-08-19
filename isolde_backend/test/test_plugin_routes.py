import pytest

from app import create_app
from app.extensions import db
from app.plugin_manager import plugin_manager, IPlugin
from app.models.user import User
from config import Config
from flask_jwt_extended import create_access_token


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_SECRET_KEY = "test-secret-key-for-testing"
    # Override engine options for SQLite in-memory compatibility
    SQLALCHEMY_ENGINE_OPTIONS = {}


class DummyPlugin(IPlugin):
    @property
    def name(self):
        return "dummy-plugin"

    @property
    def version(self):
        return "1.0.0"

    def initialize(self, context):
        pass

    def execute(self, *args, **kwargs):
        return "executed"

    def shutdown(self):
        pass


@pytest.fixture
def client():
    app = create_app(TestConfig)

    with app.app_context():
        db.create_all()

        # Create a real Active user.
        #
        # The application authentication contract requires protected JWT routes
        # to resolve the JWT identity to an existing Active User row.
        plugin_user = User(
            name="Plugin Test User",
            email="plugin-test-user@example.com",
            status="Active",
        )
        plugin_user.set_password("ValidPassword123")

        db.session.add(plugin_user)
        db.session.commit()

        user_id = plugin_user.id

    # Create the JWT using the real database user ID.
    with app.test_request_context():
        token = create_access_token(identity=user_id)

    yield app.test_client(), token

    with app.app_context():
        db.session.remove()
        db.drop_all()

    for name in [p["name"] for p in plugin_manager.list_plugins()]:
        plugin_manager.unregister_plugin(name)


def get_auth_headers(token):
    """Helper to create auth headers for tests."""
    return {"Authorization": f"Bearer {token}"}


def test_list_registered_plugins_empty(client):
    test_client, token = client

    res = test_client.get("/api/plugins/registry")

    assert res.status_code == 200
    assert isinstance(res.get_json()["plugins"], list)


def test_execute_registered_plugin(client):
    test_client, token = client

    plugin_manager.register_plugin(DummyPlugin())

    res = test_client.post(
        "/api/plugins/registry/dummy-plugin/execute",
        json={"args": [], "kwargs": {}},
        headers=get_auth_headers(token),
    )

    assert res.status_code == 200
    assert res.get_json()["result"] == "executed"


def test_execute_unknown_plugin(client):
    test_client, token = client

    res = test_client.post(
        "/api/plugins/registry/does-not-exist/execute",
        json={},
        headers=get_auth_headers(token),
    )

    assert res.status_code == 404


def test_unregister_plugin(client):
    test_client, token = client

    plugin_manager.register_plugin(DummyPlugin())

    res = test_client.delete(
        "/api/plugins/registry/dummy-plugin",
        headers=get_auth_headers(token),
    )

    assert res.status_code == 200

    res = test_client.delete(
        "/api/plugins/registry/dummy-plugin",
        headers=get_auth_headers(token),
    )

    assert res.status_code == 404