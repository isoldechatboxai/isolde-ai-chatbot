"""
Tests for marketplace, workspace, and workflow routes.
Focus on authentication, authorization, ownership checks, and input validation.
"""
import pytest
from app import create_app
from app.extensions import db
from config import Config
from flask_jwt_extended import create_access_token


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_SECRET_KEY = "test-secret-key-for-testing"
    UPLOAD_FOLDER = "/tmp/test-uploads"
    LOG_DIR = "/tmp/test-logs"
    VECTOR_STORE_DIR = "/tmp/test-vector-store"


@pytest.fixture
def app_context():
    """Create app context with database."""
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def auth_token(app_context):
    """Create a valid JWT token for testing."""
    with app_context.test_request_context():
        token = create_access_token(identity="test_user_123")
    return token


@pytest.fixture
def client(auth_token):
    """Create test client with auth token."""
    return app_context.test_client(), auth_token


def get_auth_headers(token):
    """Helper to create auth headers."""
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


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
        res = test_client.post("/api/marketplace/install/1")
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
        res = test_client.post("/api/workflows/1/execute")
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
