"""
Pytest fixtures for the Isolde backend test suite.

Provides `app`, `client`, and `db` fixtures using the REAL application
factory and a temporary SQLite database.

IMPORTANT:
- No production code is modified.
- No authentication is bypassed.
- No routes are mocked.
- No JWT requirements are disabled.
- The real create_app() factory is used.

If this file already exists with other fixtures, MERGE these fixtures
into the existing file rather than replacing it.
"""
import pytest

from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="function")
def app(tmp_path):
    """
    Create the real Flask application configured for testing.

    Uses the actual create_app() factory with a TestingConfig that:
    - Points to a temporary SQLite database (isolated per test)
    - Enables TESTING mode
    - Disables production-only behavior
    - Disables rate limiting to prevent spurious 429 responses in tests

    No routes, middleware, JWT logic, or authentication is bypassed.
    The application context is pushed for the test duration so that
    db.session operations work directly in test functions.
    """
    from config import Config

    class TestingConfig(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'test_isolde.db'}"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        IS_PRODUCTION = False
        RATELIMIT_ENABLED = False
        # Direct runtime directories to temp path to avoid polluting project
        UPLOAD_FOLDER = str(tmp_path / "uploads")
        LOG_DIR = str(tmp_path / "logs")
        VECTOR_STORE_DIR = str(tmp_path / "vectors")

    application = create_app(TestingConfig)

    # create_app() already calls db.create_all() when IS_PRODUCTION is False,
    # but we call it again for safety (idempotent).
    with application.app_context():
        _db.create_all()

    # Push application context so tests can use db.session directly
    # without wrapping every operation in `with app.app_context():`.
    ctx = application.app_context()
    ctx.push()

    yield application

    # Teardown: pop context, clean up database.
    ctx.pop()

    with application.app_context():
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    """
    Provide a Flask test client for the application.

    The test client uses the real WSGI app. Requests go through the full
    middleware stack, route handlers, and JWT decorators. Nothing is mocked.
    """
    return app.test_client()


@pytest.fixture(scope="function")
def db(app):
    """
    Provide access to the SQLAlchemy database instance within an active
    application context.

    Rolls back the session after each test to prevent state leakage.
    """
    with app.app_context():
        yield _db
        _db.session.rollback()