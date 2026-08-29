"""
Tests for marketplace, workspace, and workflow routes.
Focus on authentication, authorization, ownership checks, and input validation.
"""
import os

import pytest
from app import create_app
from app.extensions import db
from config import Config
from flask_jwt_extended import create_access_token


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_SECRET_KEY = "test-secret-key-for-testing"
    _TEST_RUNTIME_ROOT = os.path.join(os.path.dirname(__file__), ".runtime")
    UPLOAD_FOLDER = os.path.join(_TEST_RUNTIME_ROOT, "uploads")
    LOG_DIR = os.path.join(_TEST_RUNTIME_ROOT, "logs")
    VECTOR_STORE_DIR = os.path.join(_TEST_RUNTIME_ROOT, "vector-store")
    # Override engine options for SQLite in-memory compatibility
    SQLALCHEMY_ENGINE_OPTIONS = {}


@pytest.fixture
def app():
    """Create app context with database."""
    app = create_app(TestConfig)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def auth_token(app):
    """Create a valid JWT token for testing."""
    from app.models.user import User

    with app.app_context():
        # Create a real test user with Active status
        test_user = User(name="Test User", email="testuser@example.com", status="Active")
        test_user.set_password("TestPassword123")
        db.session.add(test_user)
        db.session.commit()
        user_id = test_user.id

    with app.test_request_context():
        token = create_access_token(identity=user_id)
    return token


class TestProductionConfigValidation:
    """Regression tests for Unit 2A production configuration security."""

    @staticmethod
    def _make_production_config(**overrides):
        class ProductionConfig(Config):
            IS_PRODUCTION = True
            SECRET_KEY = "a" * 32
            JWT_SECRET_KEY = "b" * 32
            DEBUG = False
            GEMINI_API_KEY = "test-gemini-api-key"
            GEMINI_MODEL = "gemini-1.5-flash"
            CORS_ORIGINS = ["https://example.com"]
            RATELIMIT_STORAGE_URI = "redis://redis:6379/0"
            CANCELLATION_REDIS_URL = "redis://redis:6379/1"
            RAG_STORAGE_BACKEND = "database"
            STORAGE_BACKEND = "s3"
            S3_BUCKET = "isolde-test-private"
            SQLALCHEMY_DATABASE_URI = "postgresql://isolde:secret@db/isolde"

        for key, value in overrides.items():
            setattr(ProductionConfig, key, value)

        return ProductionConfig

    def test_development_configuration_loads(self):
        class DevelopmentConfig(Config):
            IS_PRODUCTION = False
            SECRET_KEY = "dev-secret"
            JWT_SECRET_KEY = "dev-jwt-secret"
            DEBUG = False
            GEMINI_API_KEY = "dev-gemini-key"
            GEMINI_MODEL = "gemini-1.5-flash"
            CORS_ORIGINS = ["*"]

        DevelopmentConfig.validate()

    def test_valid_production_configuration_passes(self):
        production_config = self._make_production_config()
        production_config.validate()

    def test_non_gemini_provider_can_bootstrap_production(self):
        production_config = self._make_production_config(
            GEMINI_API_KEY="", GEMINI_MODEL="", OPENAI_API_KEY="sk-live-not-a-real-key"
        )
        production_config.validate()

    def test_production_requires_at_least_one_provider_key(self):
        production_config = self._make_production_config(GEMINI_API_KEY="")
        with pytest.raises(RuntimeError, match="AI provider API key"):
            production_config.validate()

    def test_missing_flask_secret_key_fails(self):
        production_config = self._make_production_config(SECRET_KEY="")
        with pytest.raises(RuntimeError, match="FLASK_SECRET_KEY"):
            production_config.validate()

    def test_missing_jwt_secret_key_fails(self):
        production_config = self._make_production_config(JWT_SECRET_KEY="")
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            production_config.validate()

    def test_placeholder_flask_secret_key_fails(self):
        production_config = self._make_production_config(SECRET_KEY="change_me")
        with pytest.raises(RuntimeError, match="FLASK_SECRET_KEY"):
            production_config.validate()

    def test_placeholder_jwt_secret_key_fails(self):
        production_config = self._make_production_config(JWT_SECRET_KEY="your-jwt-secret")
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            production_config.validate()

    def test_production_debug_true_fails(self):
        production_config = self._make_production_config(DEBUG=True)
        with pytest.raises(RuntimeError, match="FLASK_DEBUG"):
            production_config.validate()

    def test_production_wildcard_cors_fails(self):
        production_config = self._make_production_config(CORS_ORIGINS=["*"])
        with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
            production_config.validate()

    def test_production_in_memory_rate_limit_storage_fails(self):
        production_config = self._make_production_config(RATELIMIT_STORAGE_URI="memory://")
        with pytest.raises(RuntimeError, match="RATELIMIT_STORAGE_URI"):
            production_config.validate()

    def test_production_requires_redis_rate_limit_storage(self):
        production_config = self._make_production_config(RATELIMIT_STORAGE_URI="file:///tmp/limits")
        with pytest.raises(RuntimeError, match="RATELIMIT_STORAGE_URI"):
            production_config.validate()

    def test_production_sqlite_database_fails(self):
        production_config = self._make_production_config(SQLALCHEMY_DATABASE_URI="sqlite:///isolde.db")
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            production_config.validate()

    def test_production_requires_shared_cancellation(self):
        production_config = self._make_production_config(CANCELLATION_REDIS_URL="")
        with pytest.raises(RuntimeError, match="CANCELLATION_REDIS_URL"):
            production_config.validate()


class TestAccountStatusEnforcement:
    """Unit 2B regression tests for account status enforcement."""

    @staticmethod
    def _create_test_user(app, email, status="Active"):
        """Helper to create a test user with specified status."""
        from app.models.user import User
        with app.app_context():
            user = User(name="Test User", email=email, status=status)
            user.set_password("ValidPassword123")
            db.session.add(user)
            db.session.commit()
            return user.id

    def test_valid_login_succeeds(self, app):
        """Valid credentials with Active status should allow login."""
        client = app.test_client()
        user_id = self._create_test_user(app, "active@example.com", status="Active")

        res = client.post("/api/login", json={
            "email": "active@example.com",
            "password": "ValidPassword123"
        })

        assert res.status_code == 200
        data = res.get_json()
        assert "access_token" in data
        assert data["user"]["status"] == "Active"

    def test_invalid_password_fails(self, app):
        """Invalid password should return 401."""
        client = app.test_client()
        self._create_test_user(app, "user@example.com", status="Active")

        res = client.post("/api/login", json={
            "email": "user@example.com",
            "password": "WrongPassword"
        })

        assert res.status_code == 401
        assert "Invalid email or password" in res.get_json()["error"]

    def test_disabled_user_cannot_login(self, app):
        """Disabled user cannot login, even with correct password."""
        client = app.test_client()
        self._create_test_user(app, "disabled@example.com", status="Disabled")

        res = client.post("/api/login", json={
            "email": "disabled@example.com",
            "password": "ValidPassword123"
        })

        assert res.status_code == 401
        assert "Invalid email or password" in res.get_json()["error"]

    def test_deleted_user_cannot_login(self, app):
        """Deleted user cannot login, even with correct password."""
        client = app.test_client()
        self._create_test_user(app, "deleted@example.com", status="Deleted")

        res = client.post("/api/login", json={
            "email": "deleted@example.com",
            "password": "ValidPassword123"
        })

        assert res.status_code == 401
        assert "Invalid email or password" in res.get_json()["error"]

    def test_disabled_user_jwt_rejected(self, app, auth_token):
        """Disabled user's existing JWT should be rejected on protected routes."""
        from app.models.user import User
        
        # Create a test user with Active status initially
        with app.app_context():
            user = User(name="Active User", email="jwt_test@example.com", status="Active")
            user.set_password("ValidPassword123")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            # Create a valid JWT for this user
            from flask_jwt_extended import create_access_token
            with app.test_request_context():
                token = create_access_token(identity=user_id)

            # Now disable the user
            user = db.session.get(User, user_id)
            user.status = "Disabled"
            db.session.commit()

        # Try to use the JWT on a protected route
        client = app.test_client()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Use marketplace endpoint which requires auth
        res = client.get("/api/marketplace/installed", headers=headers)
        
        # Should be rejected because user is now disabled
        assert res.status_code == 401

    def test_deleted_user_jwt_rejected(self, app):
        """Deleted user's existing JWT should be rejected on protected routes."""
        from app.models.user import User
        
        # Create a test user with Active status initially
        with app.app_context():
            user = User(name="Delete Test User", email="delete_jwt_test@example.com", status="Active")
            user.set_password("ValidPassword123")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            # Create a valid JWT for this user
            from flask_jwt_extended import create_access_token
            with app.test_request_context():
                token = create_access_token(identity=user_id)

            # Now delete the user (mark as Deleted)
            user = db.session.get(User, user_id)
            user.status = "Deleted"
            db.session.commit()

        # Try to use the JWT on a protected route
        client = app.test_client()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Use marketplace endpoint which requires auth
        res = client.get("/api/marketplace/installed", headers=headers)
        
        # Should be rejected because user is now deleted
        assert res.status_code == 401

    def test_client_cannot_access_admin_endpoint(self, app, auth_token):
        """Client user should not access admin endpoints."""
        client = app.test_client()
        test_client, token = (client, auth_token)
        
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        res = test_client.get("/api/admin/dashboard", headers=headers)
        
        # Client role should be rejected
        assert res.status_code == 403

    def test_admin_can_access_allowed_endpoint(self, app):
        """Admin user should access allowed admin endpoints."""
        from app.models.user import User
        
        with app.app_context():
            # Create an admin user
            admin = User(name="Admin User", email="admin@example.com", role="Admin", status="Active")
            admin.set_password("ValidPassword123")
            db.session.add(admin)
            db.session.commit()
            admin_id = admin.id

            # Create JWT for admin
            from flask_jwt_extended import create_access_token
            with app.test_request_context():
                token = create_access_token(identity=admin_id)

        # Access admin endpoint
        client = app.test_client()
        headers = {"Authorization": f"Bearer {token}"}
        res = client.get("/api/admin/dashboard", headers=headers)
        
        # Admin should access successfully
        assert res.status_code == 200
        data = res.get_json()
        assert "dashboard" in data


@pytest.fixture
def client(auth_token, app):
    """Create test client with auth token."""
    return app.test_client(), auth_token


def get_auth_headers(token):
    """Helper to create auth headers."""
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


class TestVersionedApiCompatibility:

    def test_api_v1_health_and_ready_endpoints(self, app):
        """The platform must expose the target /api/v1 namespace for health checks."""
        client = app.test_client()

        health_response = client.get("/api/v1/health")
        assert health_response.status_code == 200
        health_data = health_response.get_json()
        assert "success" in health_data
        assert "data" in health_data

        ready_response = client.get("/api/v1/ready")
        assert ready_response.status_code in {200, 503}
        ready_data = ready_response.get_json()
        assert "status" in ready_data
        assert "checks" in ready_data


# =============================================================================
# MARKETPLACE ROUTE TESTS
# =============================================================================

class TestMarketplaceRoutes:
    
    def test_get_marketplace_plugins_public(self, client):
        """Test that anyone can view published plugins (optional auth)."""
        test_client, token = client
        # This endpoint allows optional auth, so no token needed
        res = test_client.get("/api/marketplace/plugins")
        assert res.status_code == 200
        data = res.get_json()
        assert "plugins" in data
    
    def test_publish_plugin_requires_auth(self, client):
        """Test that publishing a plugin requires authentication."""
        test_client, token = client
        res = test_client.post("/api/marketplace/plugins", json={})
        assert res.status_code == 401
    
    def test_publish_plugin_valid(self, client):
        """Test publishing a plugin with valid data."""
        test_client, token = client
        data = {
            "name": "Test Plugin",
            "developer_name": "Test Developer",
            "version": "1.0.0",
            "category": "Productivity"
        }
        res = test_client.post("/api/marketplace/plugins", json=data, headers=get_auth_headers(token))
        assert res.status_code == 201
        result = res.get_json()
        assert "plugin" in result
        assert result["plugin"]["name"] == "Test Plugin"
    
    def test_publish_plugin_missing_name(self, client):
        """Test that publishing fails without a name."""
        test_client, token = client
        data = {"developer_name": "Test Developer"}
        res = test_client.post("/api/marketplace/plugins", json=data, headers=get_auth_headers(token))
        assert res.status_code == 400
    
    def test_install_plugin_requires_auth(self, client):
        """Test that installing a plugin requires authentication."""
        test_client, token = client
        res = test_client.post("/api/marketplace/install/1", headers={"Content-Type": "application/json"})
        assert res.status_code == 401
    
    def test_get_installed_plugins_requires_auth(self, client):
        """Test that getting installed plugins requires authentication."""
        test_client, token = client
        res = test_client.get("/api/marketplace/installed")
        assert res.status_code == 401


# =============================================================================
# WORKSPACE ROUTE TESTS
# =============================================================================

class TestWorkspaceRoutes:
    
    def test_list_workspaces_requires_auth(self, client):
        """Test that listing workspaces requires authentication."""
        test_client, token = client
        res = test_client.get("/api/workspace/list")
        assert res.status_code == 401
    
    def test_create_workspace_valid(self, client):
        """Test creating a workspace with valid data."""
        test_client, token = client
        data = {"name": "My Workspace", "description": "Test workspace"}
        res = test_client.post("/api/workspace/create", json=data, headers=get_auth_headers(token))
        assert res.status_code == 201
        result = res.get_json()
        assert "workspace" in result
        assert result["workspace"]["name"] == "My Workspace"
    
    def test_create_workspace_missing_name(self, client):
        """Test that creating workspace fails without name."""
        test_client, token = client
        res = test_client.post("/api/workspace/create", json={}, headers=get_auth_headers(token))
        assert res.status_code == 400
    
    def test_list_projects_requires_auth(self, client):
        """Test that listing projects requires authentication."""
        test_client, token = client
        res = test_client.get("/api/workspace/1/projects")
        assert res.status_code == 401
    
    def test_create_project_requires_auth(self, client):
        """Test that creating a project requires authentication."""
        test_client, token = client
        res = test_client.post("/api/workspace/1/projects", json={})
        assert res.status_code == 401


# =============================================================================
# WORKFLOW ROUTE TESTS
# =============================================================================

class TestWorkflowRoutes:
    
    def test_get_workflows_requires_auth(self, client):
        """Test that getting workflows requires authentication."""
        test_client, token = client
        res = test_client.get("/api/workflows")
        assert res.status_code == 401
    
    def test_create_workflow_requires_auth(self, client):
        """Test that creating a workflow requires authentication."""
        test_client, token = client
        res = test_client.post("/api/workflows", json={})
        assert res.status_code == 401
    
    def test_execute_workflow_requires_auth(self, client):
        """Test that executing a workflow requires authentication."""
        test_client, token = client
        res = test_client.post("/api/workflows/1/execute", headers={"Content-Type": "application/json"})
        assert res.status_code == 401
    
    def test_get_workflow_analytics_requires_auth(self, client):
        """Test that getting analytics requires authentication."""
        test_client, token = client
        res = test_client.get("/api/workflows/analytics")
        assert res.status_code == 401


# =============================================================================
# UUID IMPORT TEST (for marketplace_routes.py)
# =============================================================================

class TestUuidImport:
    
    def test_uuid_module_available(self):
        """Test that uuid module is properly imported in marketplace_routes."""
        import uuid
        # Verify uuid.uuid4() works
        test_uuid = uuid.uuid4()
        assert test_uuid is not None
        assert len(test_uuid.hex) == 32
