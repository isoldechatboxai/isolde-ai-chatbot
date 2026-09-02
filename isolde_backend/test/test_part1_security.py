"""
Part 1 security regression tests.

These tests preserve the existing stabilization suite by not modifying
test_backend_stabilization.py.

They cover the new Part 1 core security foundation:
- explicit JWT configuration
- active account enforcement
- ownership helper behavior
- secure API response headers
- targeted API-key rate-limit wrapping
"""

import pytest

from flask import Flask, Blueprint, jsonify
from flask_jwt_extended import create_access_token, jwt_required
from sqlalchemy.pool import StaticPool

from app import create_app, _apply_part1_targeted_rate_limits, limiter
from app.extensions import db
from config import Config

from app.models.user import User
from app.models.conversation import Conversation
from app.security.authorization import active_user_required, get_owned_object


class TestConfig(Config):
    TESTING = True
    IS_PRODUCTION = False
    SECRET_KEY = "test-flask-secret-key"
    JWT_SECRET_KEY = "test-jwt-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "poolclass": StaticPool,
        "connect_args": {
            "check_same_thread": False,
        },
    }
    UPLOAD_FOLDER = "/tmp/test-uploads"
    LOG_DIR = "/tmp/test-logs"
    VECTOR_STORE_DIR = "/tmp/test-vector-store"
    CORS_ORIGINS = ["*"]


@pytest.fixture
def app_context(tmp_path):
    """Create app context with database."""
    # Keep filesystem artifacts isolated to pytest's writable temporary
    # directory.  The production runtime directories remain untouched.
    class SecurityTestConfig(TestConfig):
        UPLOAD_FOLDER = str(tmp_path / "uploads")
        LOG_DIR = str(tmp_path / "logs")
        VECTOR_STORE_DIR = str(tmp_path / "vectors")

    app = create_app(SecurityTestConfig)

    with app.app_context():
        db.create_all()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


def _auth_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _add_route(app, rule, endpoint, view_func, methods=("GET",)):
    """
    Add a test-only route if it does not already exist.
    """
    if endpoint not in app.view_functions:
        app.add_url_rule(
            rule,
            endpoint=endpoint,
            view_func=view_func,
            methods=list(methods),
        )


def _create_user(app_context, email, status="Active", role="Client"):
    with app_context.app_context():
        user = User(
            name="Part 1 Test User",
            email=email,
            status=status,
            role=role,
        )
        user.set_password("ValidPassword123")

        db.session.add(user)
        db.session.commit()

        return user.id


def _create_token(app_context, user_id):
    with app_context.app_context():
        return create_access_token(identity=user_id)


def _set_user_status(app_context, user_id, status):
    with app_context.app_context():
        user = db.session.get(User, user_id)
        user.status = status
        db.session.commit()


class TestPart1ConfigurationHardening:
    def test_jwt_algorithm_is_explicit(self):
        assert Config.JWT_ALGORITHM == "HS256"

    def test_jwt_decode_algorithms_are_explicit(self):
        assert Config.JWT_DECODE_ALGORITHMS == ["HS256"]

    def test_jwt_token_location_is_header_only(self):
        assert Config.JWT_TOKEN_LOCATION == ["headers"]

    def test_jwt_error_message_key_matches_existing_contract(self):
        assert Config.JWT_ERROR_MESSAGE_KEY == "error"

    def test_auth_and_api_key_rate_limits_are_configurable(self):
        assert Config.AUTH_RATE_LIMIT
        assert Config.API_KEY_RATE_LIMIT
        assert Config.SAAS_API_KEY_RATE_LIMIT


class TestPart1UserModelSecurity:
    def test_active_user_properties(self):
        user = User(
            name="Active User",
            email="active-properties@example.com",
            status="Active",
        )

        assert user.is_active is True
        assert user.is_disabled is False
        assert user.is_deleted is False

    def test_disabled_user_properties(self):
        user = User(
            name="Disabled User",
            email="disabled-properties@example.com",
            status="Disabled",
        )

        assert user.is_active is False
        assert user.is_disabled is True
        assert user.is_deleted is False

    def test_deleted_user_properties(self):
        user = User(
            name="Deleted User",
            email="deleted-properties@example.com",
            status="Deleted",
        )

        assert user.is_active is False
        assert user.is_disabled is False
        assert user.is_deleted is True

    def test_to_dict_does_not_expose_password_hash(self):
        user = User(
            name="Serialization User",
            email="serialization@example.com",
            status="Active",
        )
        user.set_password("ValidPassword123")

        payload = user.to_dict()

        assert "password_hash" not in payload
        assert "verification_token" not in payload
        assert "reset_otp" not in payload
        assert payload["email"] == "serialization@example.com"


class TestPart1OwnershipHelpers:
    def test_get_owned_object_enforces_owner(self, app_context):
        with app_context.app_context():
            user_one = User(
                name="Owner One",
                email="owner-one@example.com",
                status="Active",
            )
            user_one.set_password("ValidPassword123")

            user_two = User(
                name="Owner Two",
                email="owner-two@example.com",
                status="Active",
            )
            user_two.set_password("ValidPassword123")

            db.session.add_all([user_one, user_two])
            db.session.commit()

            conversation = Conversation(
                user_id=user_one.id,
                title="Owned Conversation",
            )

            db.session.add(conversation)
            db.session.commit()

            owned = get_owned_object(
                Conversation,
                conversation.id,
                user_one.id,
            )

            not_owned = get_owned_object(
                Conversation,
                conversation.id,
                user_two.id,
            )

            assert owned is not None
            assert owned.id == conversation.id
            assert not_owned is None


class TestPart1JwtAccountStatusEnforcement:
    def test_active_user_jwt_is_accepted(self, app_context):
        def protected_view():
            return jsonify({"ok": True}), 200

        _add_route(
            app_context,
            "/test/part1-protected",
            "part1_protected",
            jwt_required()(protected_view),
        )

        user_id = _create_user(
            app_context,
            "part1-active-jwt@example.com",
            status="Active",
        )

        token = _create_token(app_context, user_id)
        client = app_context.test_client()

        response = client.get(
            "/test/part1-protected",
            headers=_auth_headers(token),
        )

        assert response.status_code == 200
        assert response.get_json()["ok"] is True

    def test_disabled_user_jwt_is_rejected(self, app_context):
        def protected_view():
            return jsonify({"ok": True}), 200

        _add_route(
            app_context,
            "/test/part1-protected-disabled",
            "part1_protected_disabled",
            jwt_required()(protected_view),
        )

        user_id = _create_user(
            app_context,
            "part1-disabled-jwt@example.com",
            status="Active",
        )

        token = _create_token(app_context, user_id)

        _set_user_status(app_context, user_id, "Disabled")

        client = app_context.test_client()

        response = client.get(
            "/test/part1-protected-disabled",
            headers=_auth_headers(token),
        )

        assert response.status_code == 401

    def test_deleted_user_jwt_is_rejected(self, app_context):
        def protected_view():
            return jsonify({"ok": True}), 200

        _add_route(
            app_context,
            "/test/part1-protected-deleted",
            "part1_protected_deleted",
            jwt_required()(protected_view),
        )

        user_id = _create_user(
            app_context,
            "part1-deleted-jwt@example.com",
            status="Active",
        )

        token = _create_token(app_context, user_id)

        _set_user_status(app_context, user_id, "Deleted")

        client = app_context.test_client()

        response = client.get(
            "/test/part1-protected-deleted",
            headers=_auth_headers(token),
        )

        assert response.status_code == 401


class TestPart1ActiveUserRequiredDecorator:
    def test_missing_token_is_rejected(self, app_context):
        def view():
            return jsonify({"ok": True}), 200

        _add_route(
            app_context,
            "/test/part1-active-required-missing",
            "part1_active_required_missing",
            active_user_required(view),
        )

        client = app_context.test_client()

        response = client.get("/test/part1-active-required-missing")

        assert response.status_code == 401

    def test_active_user_is_accepted(self, app_context):
        def view():
            return jsonify({"ok": True}), 200

        _add_route(
            app_context,
            "/test/part1-active-required-active",
            "part1_active_required_active",
            active_user_required(view),
        )

        user_id = _create_user(
            app_context,
            "part1-active-required@example.com",
            status="Active",
        )

        token = _create_token(app_context, user_id)
        client = app_context.test_client()

        response = client.get(
            "/test/part1-active-required-active",
            headers=_auth_headers(token),
        )

        assert response.status_code == 200
        assert response.get_json()["ok"] is True

    def test_disabled_user_is_rejected(self, app_context):
        def view():
            return jsonify({"ok": True}), 200

        _add_route(
            app_context,
            "/test/part1-active-required-disabled",
            "part1_active_required_disabled",
            active_user_required(view),
        )

        user_id = _create_user(
            app_context,
            "part1-active-required-disabled@example.com",
            status="Active",
        )

        token = _create_token(app_context, user_id)

        _set_user_status(app_context, user_id, "Disabled")

        client = app_context.test_client()

        response = client.get(
            "/test/part1-active-required-disabled",
            headers=_auth_headers(token),
        )

        assert response.status_code == 401


class TestPart1SecureApiResponseHeaders:
    def test_api_responses_are_not_cached(self, app_context):
        client = app_context.test_client()

        response = client.get("/api/live")

        assert response.status_code == 200
        assert response.headers.get("Cache-Control") == "no-store"
        assert response.headers.get("Pragma") == "no-cache"


class TestPart1TargetedRateLimitWrapping:
    def test_targeted_rate_limits_wrap_only_api_key_endpoints(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["API_KEY_RATE_LIMIT"] = "5 per minute"
        app.config["SAAS_API_KEY_RATE_LIMIT"] = "10 per minute"

        limiter.init_app(app)

        api_key_bp = Blueprint("api_key", __name__)

        @api_key_bp.route("/items")
        def api_key_items():
            return jsonify({"ok": True}), 200

        saas_cloud_bp = Blueprint("saas_cloud", __name__)

        @saas_cloud_bp.route("/api-keys")
        def saas_api_keys():
            return jsonify({"ok": True}), 200

        other_bp = Blueprint("other", __name__)

        @other_bp.route("/items")
        def other_items():
            return jsonify({"ok": True}), 200

        app.register_blueprint(api_key_bp, url_prefix="/api")
        app.register_blueprint(saas_cloud_bp, url_prefix="/api/saas")
        app.register_blueprint(other_bp, url_prefix="/other")

        _apply_part1_targeted_rate_limits(app)

        assert app.view_functions["api_key.api_key_items"] is not api_key_items
        assert app.view_functions["saas_cloud.saas_api_keys"] is not saas_api_keys
        assert app.view_functions["other.other_items"] is other_items
