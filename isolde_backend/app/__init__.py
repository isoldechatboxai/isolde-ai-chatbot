import os
import click
from flask import Flask, jsonify, send_from_directory, request, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import text, inspect
from werkzeug.middleware.proxy_fix import ProxyFix

try:
    from flask_jwt_extended.exceptions import UserLookupError
except ImportError:
    class UserLookupError(Exception):
        """
        Fallback only for uncommon Flask-JWT-Extended versions.
        The real exception type is preferred.
        """
        pass

from config import Config, FRONTEND_DIR
from app.extensions import db, jwt, cors, migrate
from app.utils.logger import setup_logger

# Middleware
from app.middleware.request_logger import setup_request_logger
from app.middleware.security_headers import setup_security_headers
from app.middleware.content_validator import setup_content_validator

# -------------------------------------------------------------------
# Global rate limiter
# -------------------------------------------------------------------
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120 per minute"],
)


def _readiness_error_category(error: Exception) -> str:
    """Classify dependency failures without retaining sensitive error text."""
    message = str(error).lower()
    if "timeout" in message or "timed out" in message:
        return "TIMEOUT"
    if any(token in message for token in ("access denied", "forbidden", "unauthorized", "permission denied")):
        return "ACCESS_DENIED"
    if any(token in message for token in ("credential", "authentication", "no credentials")):
        return "AUTHENTICATION_ERROR"
    if "bucket" in message and any(token in message for token in ("not found", "nosuchbucket", "does not exist")):
        return "BUCKET_NOT_FOUND"
    if "region" in message and any(token in message for token in ("mismatch", "redirect", "incorrect")):
        return "REGION_MISMATCH"
    if any(token in message for token in ("connect", "network", "connection refused", "name resolution")):
        return "NETWORK_ERROR"
    return "UNAVAILABLE"


def _log_readiness_failure(app, component: str, error: Exception) -> None:
    """Emit correlation-friendly readiness telemetry without endpoint details."""
    app.logger.error(
        "Readiness check failed. request_id=%s component=%s category=%s",
        getattr(g, "request_id", "N/A"),
        component,
        _readiness_error_category(error),
    )


def _user_lookup_error(message: str, jwt_header, jwt_payload):
    """
    Compatibility helper for Flask-JWT-Extended UserLookupError.
    Some Flask-JWT-Extended versions require:
        UserLookupError(message, jwt_header, jwt_data)
    Other/custom fallback versions may accept only:
        UserLookupError(message)
    This helper preserves account-status enforcement without causing
    constructor TypeError on supported versions.
    """
    try:
        return UserLookupError(message, jwt_header, jwt_payload)
    except TypeError:
        return UserLookupError(message)


def _apply_part1_targeted_rate_limits(app):
    """
    Part 1 targeted rate limiting.
    Applies narrow Flask-Limiter limits only to API-key related endpoints:
     - api_key blueprint endpoints: 5 per minute
     - SaaS API-key endpoints: 10 per minute
     This function:
       - reuses the existing global limiter
       - does not create a second limiter
       - does not apply global application limits
       - does not modify unrelated endpoints
       - preserves existing Flask-Limiter configuration
     """
    api_key_limit = app.config.get(
        "API_KEY_RATE_LIMIT",
        "5 per minute",
    )
    saas_api_key_limit = app.config.get(
        "SAAS_API_KEY_RATE_LIMIT",
        "10 per minute",
    )

    wrapped_endpoints = set()
    for endpoint, view_func in list(app.view_functions.items()):
        if endpoint == "static":
            continue
        if endpoint in wrapped_endpoints:
            continue
        if view_func is None:
            continue
        if getattr(view_func, "__part1_rate_limited__", False):
            wrapped_endpoints.add(endpoint)
            continue

        endpoint_l = endpoint.lower()
        view_name = getattr(view_func, "__name__", "").lower()
        module_name = getattr(view_func, "__module__", "") or ""
        is_api_key_endpoint = (
            endpoint_l.startswith(("api_key.", "api_keys.", "apikey."))
            or module_name.endswith("app.routes.api_key_routes")
        )
        is_saas_api_key_endpoint = (
            endpoint_l.startswith("saas_cloud.")
            or module_name.endswith("app.routes.saas_cloud_routes")
        ) and any(token in endpoint_l or token in view_name for token in ("api_key", "apikey", "keys"))

        limit_value = api_key_limit if is_api_key_endpoint else saas_api_key_limit if is_saas_api_key_endpoint else None
        if limit_value:
            limited_view = limiter.limit(limit_value)(view_func)
            limited_view.__part1_rate_limited__ = True
            app.view_functions[endpoint] = limited_view
            wrapped_endpoints.add(endpoint)


def _apply_security_sensitive_rate_limits(app):
    limits = {
        "auth.login": app.config["AUTH_RATE_LIMIT"],
        "auth.register": app.config["AUTH_RATE_LIMIT"],
        "auth.verify_email": app.config["AUTH_RATE_LIMIT"],
        "auth.forgot_password": app.config["AUTH_RATE_LIMIT"],
        "auth.reset_password": app.config["AUTH_RATE_LIMIT"],
        "auth.oauth_start": app.config["OAUTH_RATE_LIMIT"],
        "auth.oauth_callback": app.config["OAUTH_RATE_LIMIT"],
        "chat.chat": app.config["CHAT_RATE_LIMIT"],
        "chat.stream_chat": app.config["CHAT_RATE_LIMIT"],
        "upload.upload_file": app.config["UPLOAD_RATE_LIMIT"],
        "rag.upload_rag_file": app.config["UPLOAD_RATE_LIMIT"],
        "ai_studio_bp.test_playground_prompt": app.config["CHAT_RATE_LIMIT"],
        "admin.admin_login": app.config["AUTH_RATE_LIMIT"],
        "unified_engine_bp.handle_unified_chat": app.config["CHAT_RATE_LIMIT"],
        "memory_bp.save_memory": app.config["CHAT_RATE_LIMIT"],
        "studio_bp.generate_image": app.config["CHAT_RATE_LIMIT"],
        "studio_bp.generate_video": app.config["CHAT_RATE_LIMIT"],
        "billing_bp.create_checkout": app.config["BILLING_RATE_LIMIT"],
        "billing_bp.payment_webhook": app.config["BILLING_RATE_LIMIT"],
        "billing_bp.cancel_subscription": app.config["BILLING_RATE_LIMIT"],
        "billing_bp.refund_invoice": app.config["BILLING_RATE_LIMIT"],
        "admin.admin_cancel_subscription": app.config["BILLING_RATE_LIMIT"],
    }
    for endpoint, limit_value in limits.items():
        view = app.view_functions.get(endpoint)
        if view is not None and not getattr(view, "__security_rate_limited__", False):
            wrapped = limiter.limit(limit_value)(view)
            wrapped.__security_rate_limited__ = True
            app.view_functions[endpoint] = wrapped


def create_app(config_class=Config):
    """
    Application factory for the Isolde Flask backend.
    The application factory is responsible for:
     - loading configuration
     - initializing Flask extensions
     - registering middleware
     - registering API blueprints
     - exposing health/readiness endpoints
     - serving the frontend
    """
    # ----------------------------------------------------------------
    # Deferred imports — performed INSIDE the factory to avoid
    # circular imports between app, models, and routes.
    # At this point the app package is fully initialized, so models
    # and routes can safely import from app.extensions.
    # ----------------------------------------------------------------
    from app.models.user import User
    import app.models  # Ensure all models are registered with SQLAlchemy metadata

    app = Flask(
        __name__,
        static_folder=FRONTEND_DIR,
        static_url_path="",
    )

    # ----------------------------------------------------------------
    # Configuration
    # ----------------------------------------------------------------
    app.config.from_object(config_class)
    proxy_hops = int(app.config.get("TRUST_PROXY_HOPS", 0))
    if proxy_hops:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxy_hops, x_proto=proxy_hops, x_host=proxy_hops, x_port=proxy_hops)

    # ----------------------------------------------------------------
    # Runtime directories
    # ----------------------------------------------------------------
    os.makedirs(
        app.config["UPLOAD_FOLDER"],
        exist_ok=True,
    )
    os.makedirs(
        app.config["LOG_DIR"],
        exist_ok=True,
    )
    os.makedirs(
        app.config["VECTOR_STORE_DIR"],
        exist_ok=True,
    )

    # ----------------------------------------------------------------
    # Extensions
    # ----------------------------------------------------------------
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    # ----------------------------------------------------------------
    # JWT error handlers
    # ----------------------------------------------------------------
    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        app.logger.warning(
            "Invalid JWT token: %s",
            reason,
        )
        return jsonify({
            "error": "Invalid authentication token."
        }), 401

    @jwt.unauthorized_loader
    def missing_token_callback(reason):
        app.logger.warning(
            "Missing JWT token: %s",
            reason,
        )
        return jsonify({
            "error": "Authentication required."
        }), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({
            "error": "Token expired."
        }), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({
            "error": "Token revoked."
        }), 401

    @jwt.token_in_blocklist_loader
    def token_is_revoked(jwt_header, jwt_payload):
        from app.models.auth_model import AuthSession, RevokedToken

        if db.session.get(RevokedToken, jwt_payload.get("jti")) is not None:
            return True
        session_id = jwt_payload.get("sid")
        if not session_id:
            # Compatibility for tokens issued before database-backed sessions.
            return False
        auth_session = db.session.get(AuthSession, session_id)
        return not auth_session or not auth_session.is_valid

    @jwt.needs_fresh_token_loader
    def needs_fresh_callback(jwt_header, jwt_payload):
        return jsonify({
            "error": "Fresh token required."
        }), 401

    @jwt.user_lookup_error_loader
    def user_lookup_error(jwt_header, jwt_payload):
        return jsonify({
            "error": "User lookup failed."
        }), 401

    # ----------------------------------------------------------------
    # Account Status Enforcement
    # ----------------------------------------------------------------
    # This loader is called for every protected route to verify that
    # the user account is still active.
    #
    # If the user does not exist or is not Active, raise UserLookupError.
    # This causes existing JWT error handling to return 401.
    # ----------------------------------------------------------------
    @jwt.user_lookup_loader
    def user_lookup(jwt_header, jwt_payload):
        user_id = jwt_payload.get("sub")
        if not user_id:
            raise _user_lookup_error(
                "Missing user identity.",
                jwt_header,
                jwt_payload,
            )
        try:
            user = db.session.get(User, user_id)
        except Exception:
            raise _user_lookup_error(
                "User lookup failed.",
                jwt_header,
                jwt_payload,
            )
        if not user or user.status != "Active":
            raise _user_lookup_error(
                "User account is not active.",
                jwt_header,
                jwt_payload,
            )
        return user

    # ----------------------------------------------------------------
    # CORS
    # ----------------------------------------------------------------
    cors_origins = app.config.get(
        "CORS_ORIGINS",
        ["*"],
    )
    # Credentials must not be enabled with a wildcard origin.
    supports_credentials = cors_origins != ["*"]
    cors.init_app(
        app,
        resources={
            r"/api/*": {
                "origins": cors_origins,
                "allow_headers": [
                    "Content-Type",
                    "Authorization",
                    "Accept",
                    "X-Requested-With",
                ],
                "methods": [
                    "GET",
                    "POST",
                    "PUT",
                    "PATCH",
                    "DELETE",
                    "OPTIONS",
                ],
                "supports_credentials": supports_credentials,
            }
        },
    )

    # ----------------------------------------------------------------
    # Rate limiting
    # ----------------------------------------------------------------
    limiter.init_app(app)

    # ----------------------------------------------------------------
    # Logging
    # ----------------------------------------------------------------
    setup_logger(app)

    # ----------------------------------------------------------------
    # Middleware
    # ----------------------------------------------------------------
    setup_request_logger(app)
    setup_security_headers(app)
    setup_content_validator(app)

    # ----------------------------------------------------------------
    # Blueprints
    # ----------------------------------------------------------------
    from app.routes.auth_routes import auth_bp
    from app.routes.chat_routes import chat_bp
    from app.routes.upload_routes import upload_bp
    from app.routes.feedback_routes import feedback_bp
    from app.routes.history_routes import history_bp
    from app.routes.profile_routes import profile_bp
    from app.routes.admin_routes import admin_bp
    from app.routes.memory_routes import memory_bp
    from app.routes.workspace_routes import workspace_bp
    from app.routes.agent_routes import agent_bp
    from app.routes.productivity_routes import productivity_bp
    from app.routes.voice_routes import voice_bp
    from app.routes.workflow_routes import workflow_bp
    from app.routes.collaboration_routes import collaboration_bp
    from app.routes.marketplace_routes import marketplace_bp
    from app.routes.saas_cloud_routes import saas_cloud_bp
    from app.routes.intelligence_routes import intelligence_bp
    from app.routes.rag_routes import rag_bp
    from app.routes.api_key_routes import api_key_bp
    from app.routes.chat_extended_routes import chat_ext_bp
    from app.routes.billing_routes import billing_bp
    from app.routes.plugin_routes import plugin_bp
    from app.routes.ai_studio_routes import ai_studio_bp
    from app.routes.unified_chat_engine import unified_engine_bp
    from app.routes.settings_routes import settings_bp
    from app.routes.codex_routes import codex_bp  # Codex Project Engineering

    # Health and analytics
    from app.routes.health_routes import health_bp
    from app.routes.analytics_routes import analytics_bp

    # Studio
    from app.studio_routes import studio_bp

    # ----------------------------------------------------------------
    # Core API blueprints
    # ----------------------------------------------------------------
    app.register_blueprint(
        auth_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        chat_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        upload_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        feedback_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        history_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        profile_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        admin_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        memory_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        workspace_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        agent_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        productivity_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        voice_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        workflow_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        collaboration_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        marketplace_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        saas_cloud_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        intelligence_bp,
        url_prefix="/api",
    )

    # RAG routes define their own paths.
    app.register_blueprint(rag_bp)

    # ISOLDE Own API blueprint — registered ONCE (duplicate removed)
    app.register_blueprint(
        api_key_bp,
        url_prefix="/api",
    )

    # Extended chat routes define their own paths.
    app.register_blueprint(chat_ext_bp)

    app.register_blueprint(
        billing_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        plugin_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        ai_studio_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        unified_engine_bp,
        url_prefix="/api",
    )
    app.register_blueprint(
        settings_bp,
        url_prefix="/api",
    )
# Codex Project Engineering blueprint
    app.register_blueprint(
        codex_bp,
        url_prefix="/api",
    )

    # Health blueprint already defines /api/health.
    app.register_blueprint(health_bp)

    # Analytics blueprint already defines /api/analytics.
    app.register_blueprint(analytics_bp)

    # Studio blueprint defines its own routes.
    app.register_blueprint(studio_bp)

    # ----------------------------------------------------------------
    # Part 1 targeted API-key rate limiting
    # ----------------------------------------------------------------
    _apply_part1_targeted_rate_limits(app)
    _apply_security_sensitive_rate_limits(app)

    @app.cli.command("db-bootstrap")
    def db_bootstrap():
        """Initialize an entirely empty database and stamp it at migration head."""
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())
        if "alembic_version" in tables:
            raise click.ClickException("Database is already migration-managed; run 'flask db upgrade'.")
        if tables:
            raise click.ClickException("Refusing to bootstrap a non-empty unversioned database.")
        db.create_all()
        from flask_migrate import stamp
        stamp(revision="head")
        click.echo("Empty database initialized and stamped at migration head.")

    @app.cli.command("provision-demo-admin")
    def provision_demo_admin():
        """Explicitly provision one idempotent Super Admin for demo/staging only."""
        from app.models.enterprise_models import AuditLog
        from app.utils.validators import is_valid_email

        if not app.config.get("DEMO_ADMIN_BOOTSTRAP_ENABLED", False):
            raise click.ClickException("Demo admin bootstrap is disabled.")
        if app.config.get("IS_PRODUCTION") or not app.config.get("IS_DEMO_STAGING"):
            raise click.ClickException("Demo admin bootstrap is permitted only in demo or staging.")
        database_marker = str(app.config.get("DEMO_DATABASE_MARKER") or "").lower()
        storage_marker = str(app.config.get("DEMO_STORAGE_MARKER") or "").lower()
        database_url = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "").lower()
        storage_bucket = str(app.config.get("S3_BUCKET") or "").lower()
        cors_origins = app.config.get("CORS_ORIGINS") or []
        if (not database_marker or database_marker not in database_url or
                app.config.get("STORAGE_BACKEND") != "s3" or
                not storage_marker or storage_marker not in storage_bucket or
                "*" in cors_origins):
            raise click.ClickException("Demo bootstrap isolation requirements are not satisfied.")
        email = str(app.config.get("DEMO_ADMIN_EMAIL") or "").strip().lower()
        password = str(app.config.get("DEMO_ADMIN_PASSWORD") or "")
        if not is_valid_email(email) or len(password) < 16 or Config._is_placeholder_secret(password):
            raise click.ClickException("Demo admin credentials are missing or do not meet security requirements.")
        existing = User.query.filter_by(email=email).first()
        if existing:
            if existing.role != "Super Admin":
                raise click.ClickException("Configured demo admin email belongs to a non-Super-Admin account.")
            click.echo("Demo/staging Super Admin is already provisioned.")
            return
        user = User(name="Demo Staging Administrator", email=email, role="Super Admin", status="Active", is_verified=True)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        db.session.add(AuditLog(actor_user_id=str(user.id), action="DEMO_ADMIN_PROVISIONED", status="success", details="{}"))
        db.session.commit()
        click.echo("Demo/staging Super Admin provisioned.")

    @app.cli.command("rag-import-json")
    @click.argument("path", type=click.Path(exists=True, dir_okay=False, readable=True))
    def rag_import_json(path):
        """Import an owned legacy RAG index.json into database storage."""
        from app.services.rag_service import import_legacy_json
        result = import_legacy_json(path)
        click.echo(
            f"Imported {result['documents']} documents and {result['chunks']} chunks; "
            f"skipped {result['ownerless_skipped']} ownerless records."
        )

    # ----------------------------------------------------------------
    # Error handlers
    # ----------------------------------------------------------------
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "error": "Endpoint not found."
        }), 404

    @app.errorhandler(413)
    def too_large(error):
        return jsonify({
            "error": "File too large."
        }), 413

    @app.errorhandler(429)
    def rate_limited(error):
        return jsonify({
            "error": "Too many requests. Please slow down."
        }), 429

    @app.errorhandler(500)
    def server_error(error):
        app.logger.exception(
            "Unhandled server error: %s",
            error,
        )
        return jsonify({
            "error": "Internal server error."
        }), 500

    # ----------------------------------------------------------------
    # Part 1 secure API response headers
    # ----------------------------------------------------------------
    @app.after_request
    def part1_secure_api_response_headers(response):
        """
        Prevent API responses from being cached by browsers or proxies.
        This is additive and does not replace the existing security
        header middleware.
        """
        try:
            if request.path.startswith("/api/"):
                response.headers.setdefault("Cache-Control", "no-store")
                response.headers.setdefault("Pragma", "no-cache")
        except Exception:
            pass
        return response

    # ----------------------------------------------------------------
    # Liveness endpoint
    # ----------------------------------------------------------------
    @app.route(
        "/api/live",
        methods=["GET"],
    )
    def liveness():
        """
        Lightweight process-level liveness check.
        This endpoint intentionally does not require the database.
        """
        return jsonify({
            "status": "ok",
            "service": "Isolde backend",
        }), 200

    # ----------------------------------------------------------------
    # Readiness endpoint
    # ----------------------------------------------------------------
    @app.route(
        "/api/ready",
        methods=["GET"],
    )
    def readiness():
        """
        Readiness check.
        Verifies that the application can communicate with the
        configured database and that required runtime directories exist.
        """
        checks = {
            "database": False,
            "storage": False,
            "vector_store": False,
            "cancellation": False,
            "logs": not app.config.get("LOG_TO_FILE", False),
        }
        try:
            db.session.execute(text("SELECT 1"))
            checks["database"] = True
            from app.models.rag_model import RAGDocument
            db.session.query(RAGDocument.id).limit(1).all()
            checks["vector_store"] = True
        except Exception as error:
            _log_readiness_failure(app, "database", error)

        try:
            from app.services.storage_service import get_storage
            checks["storage"] = get_storage().check()
        except Exception as error:
            _log_readiness_failure(app, "storage", error)

        required_directories = {}
        if app.config.get("LOG_TO_FILE", False):
            required_directories["logs"] = app.config["LOG_DIR"]
        for check_name, directory in required_directories.items():
            try:
                checks[check_name] = os.path.isdir(directory)
            except OSError as error:
                _log_readiness_failure(app, check_name, error)

        try:
            cancellation_url = app.config.get("CANCELLATION_REDIS_URL", "")
            if cancellation_url:
                import redis
                redis.Redis.from_url(
                    cancellation_url,
                    socket_connect_timeout=app.config.get("REDIS_CONNECT_TIMEOUT_SECONDS", 2),
                    socket_timeout=app.config.get("REDIS_SOCKET_TIMEOUT_SECONDS", 2),
                ).ping()
                checks["cancellation"] = True
            else:
                checks["cancellation"] = not app.config.get("IS_PRODUCTION", False)
        except Exception as error:
            _log_readiness_failure(app, "cancellation", error)

        ready = all(checks.values())
        return jsonify({
            "status": "ready" if ready else "not_ready",
            "service": "Isolde backend",
            "checks": checks,
        }), 200 if ready else 503

    @app.route(
        "/api/v1/health",
        methods=["GET"],
    )
    def api_v1_health():
        """Compatibility alias for the health endpoint in the target API namespace."""
        try:
            from app.services.health_service import health_service
            status_data = health_service.check_system_health()
            status_code = 200 if status_data.get("status") == "healthy" else 503
            return jsonify({
                "success": status_code == 200,
                "data": status_data,
            }), status_code
        except Exception as error:
            app.logger.exception("Versioned health check failed: %s", error)
            return jsonify({
                "success": False,
                "error": "Health check failed.",
            }), 500

    @app.route(
        "/api/v1/ready",
        methods=["GET"],
    )
    def api_v1_ready():
        """Compatibility alias for the readiness endpoint in the target API namespace."""
        return readiness()

    # ----------------------------------------------------------------
    # Frontend routes
    # ----------------------------------------------------------------
    @app.route(
        "/",
        methods=["GET"],
    )
    def serve_frontend():
        return send_from_directory(
            FRONTEND_DIR,
            "index.html",
        )

    @app.route(
        "/login",
        methods=["GET"],
    )
    @app.route(
        "/login.html",
        methods=["GET"],
    )
    def serve_login_page():
        return send_from_directory(
            FRONTEND_DIR,
            "login.html",
        )

    @app.route(
        "/register",
        methods=["GET"],
    )
    @app.route(
        "/register.html",
        methods=["GET"],
    )
    def serve_register_page():
        return send_from_directory(
            FRONTEND_DIR,
            "register.html",
        )

    # ----------------------------------------------------------------
    # Development database initialization
    # ----------------------------------------------------------------
    #
    # IMPORTANT:
    # Production schema changes must use Flask-Migrate/Alembic.
    #
    # Until the migration foundation is installed, local development
    # continues to use db.create_all() so the existing project can run.
    #
    # This block is intentionally disabled in production.
    # ----------------------------------------------------------------
    # Never infer a PostgreSQL schema from ORM metadata.  Development SQLite
    # remains convenient, while every shared database (including staging)
    # is owned exclusively by Alembic migrations.
    if (not app.config.get("IS_PRODUCTION", False)
            and app.config.get("SQLALCHEMY_DATABASE_URI", "").startswith("sqlite:")):
        with app.app_context():
            db.create_all()

    return app
