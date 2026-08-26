import json
import time
from sqlalchemy import inspect, text

from app import create_app
from app.extensions import db as extension_db
from app.models.rag_model import RAGChunk, RAGDocument
from app.services import rag_service
from app.services.cancellation_service import CancellationStore
from config import Config


def test_database_rag_is_tenant_scoped_and_transactional(app, db, monkeypatch):
    monkeypatch.setattr(rag_service, "embed_text", lambda text: [1.0, 0.0] if "other" not in text else [0.0, 1.0])
    with app.app_context():
        assert rag_service.index_document("doc-a", "a.txt", "private owner text", "user-a") == 1
        assert rag_service.index_document("doc-b", "b.txt", "other tenant text", "user-b") == 1
        assert RAGDocument.query.count() == 2
        assert RAGChunk.query.count() == 2
        results = rag_service.search("owner question", user_id="user-a")
        assert [result["filename"] for result in results] == ["a.txt"]
        assert rag_service.delete_document("doc-b", "user-a") is False
        assert rag_service.delete_document("doc-a", "user-a") is True
        assert RAGChunk.query.filter_by(user_id="user-a").count() == 0


def test_legacy_rag_import_preserves_owner_and_skips_ownerless(app, db, tmp_path):
    path = tmp_path / "index.json"
    path.write_text(json.dumps([
        {"id": "c1", "file_id": "d1", "filename": "owned.txt", "user_id": "user-a", "text": "owned", "vector": [1, 0]},
        {"id": "c2", "file_id": "d2", "filename": "legacy.txt", "user_id": None, "text": "legacy", "vector": [1, 0]},
    ]), encoding="utf-8")
    with app.app_context():
        result = rag_service.import_legacy_json(str(path))
        assert result == {"documents": 1, "chunks": 1, "ownerless_skipped": 1}
        assert RAGDocument.query.one().user_id == "user-a"


class _FakeRedis:
    def __init__(self):
        self.values = {}

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def get(self, key):
        return self.values.get(key)

    def eval(self, script, _keys, key, owner, *args):
        raw = self.values.get(key)
        if raw is None:
            return 0
        value = json.loads(raw)
        if value["owner"] != owner:
            return -1
        if "value.cancelled = true" in script:
            value["cancelled"] = True
            self.values[key] = json.dumps(value)
            return 1
        del self.values[key]
        return 1


def test_shared_cancellation_cross_worker_owner_semantics(app, monkeypatch):
    redis = _FakeRedis()
    worker_a = CancellationStore()
    worker_b = CancellationStore()
    monkeypatch.setattr(worker_a, "_redis", lambda: redis)
    monkeypatch.setattr(worker_b, "_redis", lambda: redis)
    with app.app_context():
        worker_a.register("generation", "user:owner", "conversation")
        assert worker_b.cancel("generation", "user:attacker") == -1
        assert worker_a.is_cancelled("generation", "user:owner") is False
        assert worker_b.cancel("generation", "user:owner") == 1
        assert worker_a.is_cancelled("generation", "user:owner") is True
        assert worker_a.unregister("generation", "user:attacker") == -1
        assert worker_a.unregister("generation", "user:owner") == 1
        assert redis.values == {}


def test_local_cancellation_state_expires(app):
    store = CancellationStore()
    app.config["CANCELLATION_TTL_SECONDS"] = 1
    with app.app_context():
        store.register("short", "user:owner")
        store._memory["short"]["expires"] = time.monotonic() - 1
        assert store.cancel("short", "user:owner") == 0
        assert store._memory == {}


def test_empty_database_bootstrap_creates_current_schema(tmp_path):
    class BootstrapConfig(Config):
        TESTING = True
        IS_PRODUCTION = True
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'bootstrap.db'}"
        RATELIMIT_ENABLED = False
        CANCELLATION_REDIS_URL = ""
        UPLOAD_FOLDER = str(tmp_path / "uploads")
        VECTOR_STORE_DIR = str(tmp_path / "vectors")
        LOG_DIR = str(tmp_path / "logs")

    bootstrap_app = create_app(BootstrapConfig)
    result = bootstrap_app.test_cli_runner().invoke(args=["db-bootstrap"])
    assert result.exit_code == 0, result.output
    with bootstrap_app.app_context():
        tables = set(inspect(extension_db.engine).get_table_names())
        assert {"users", "rag_documents", "rag_chunks", "alembic_version"} <= tables
        assert extension_db.session.execute(text("SELECT version_num FROM alembic_version")).scalar() == "20260826_000002"


def test_bootstrap_refuses_nonempty_unversioned_database(tmp_path):
    class BootstrapConfig(Config):
        TESTING = True
        IS_PRODUCTION = True
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'nonempty.db'}"
        RATELIMIT_ENABLED = False
        CANCELLATION_REDIS_URL = ""
        UPLOAD_FOLDER = str(tmp_path / "uploads")
        VECTOR_STORE_DIR = str(tmp_path / "vectors")
        LOG_DIR = str(tmp_path / "logs")

    bootstrap_app = create_app(BootstrapConfig)
    with bootstrap_app.app_context():
        extension_db.session.execute(text("CREATE TABLE legacy_data (id INTEGER PRIMARY KEY)"))
        extension_db.session.commit()
    result = bootstrap_app.test_cli_runner().invoke(args=["db-bootstrap"])
    assert result.exit_code != 0
    assert "Refusing to bootstrap" in result.output


def test_security_sensitive_routes_have_targeted_rate_limits(app):
    sensitive = {
        "auth.login", "auth.register", "auth.verify_email", "auth.forgot_password",
        "auth.reset_password", "auth.oauth_start", "auth.oauth_callback",
        "chat.chat", "chat.stream_chat", "upload.upload_file", "rag.upload_rag_file",
        "ai_studio_bp.test_playground_prompt", "admin.admin_login",
        "unified_engine_bp.handle_unified_chat", "memory_bp.save_memory",
        "studio_bp.generate_image", "studio_bp.generate_video",
    }
    for endpoint in sensitive:
        assert getattr(app.view_functions[endpoint], "__security_rate_limited__", False), endpoint
    assert not getattr(app.view_functions["auth.list_sessions"], "__security_rate_limited__", False)


def test_existing_database_migrates_from_auth_head_to_rag_head(app):
    with app.app_context():
        RAGChunk.__table__.drop(extension_db.engine, checkfirst=True)
        RAGDocument.__table__.drop(extension_db.engine, checkfirst=True)
    runner = app.test_cli_runner()
    stamped = runner.invoke(args=["db", "stamp", "20260826_000001"])
    assert stamped.exit_code == 0, stamped.output
    upgraded = runner.invoke(args=["db", "upgrade"])
    assert upgraded.exit_code == 0, upgraded.output
    with app.app_context():
        assert {"rag_documents", "rag_chunks"} <= set(inspect(extension_db.engine).get_table_names())
        assert extension_db.session.execute(text("SELECT version_num FROM alembic_version")).scalar() == "20260826_000002"
