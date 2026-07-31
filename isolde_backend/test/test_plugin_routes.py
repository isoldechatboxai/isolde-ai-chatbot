import pytest
from app import create_app
from app.extensions import db
from app.plugin_manager import plugin_manager, IPlugin
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


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
        yield app.test_client()
        db.session.remove()
        db.drop_all()
    for name in [p["name"] for p in plugin_manager.list_plugins()]:
        plugin_manager.unregister_plugin(name)


def test_list_registered_plugins_empty(client):
    res = client.get("/api/plugins/registry")
    assert res.status_code == 200
    assert isinstance(res.get_json()["plugins"], list)


def test_execute_registered_plugin(client):
    plugin_manager.register_plugin(DummyPlugin())
    res = client.post("/api/plugins/registry/dummy-plugin/execute", json={"args": [], "kwargs": {}})
    assert res.status_code == 200
    assert res.get_json()["result"] == "executed"


def test_execute_unknown_plugin(client):
    res = client.post("/api/plugins/registry/does-not-exist/execute", json={})
    assert res.status_code == 404


def test_unregister_plugin(client):
    plugin_manager.register_plugin(DummyPlugin())
    res = client.delete("/api/plugins/registry/dummy-plugin")
    assert res.status_code == 200

    res = client.delete("/api/plugins/registry/dummy-plugin")
    assert res.status_code == 404