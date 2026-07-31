# app/__init__.py
import os
from flask import Flask, jsonify, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config, FRONTEND_DIR
from app.extensions import db, jwt, cors
from app.utils.logger import setup_logger

# 🌟 Phase 3: Import Middleware
from app.middleware.request_logger import setup_request_logger
from app.middleware.security_headers import setup_security_headers
from app.middleware.content_validator import setup_content_validator

limiter = Limiter(key_func=get_remote_address, default_limits=["120 per minute"])

def create_app(config_class=Config):
    app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["LOG_DIR"], exist_ok=True)
    os.makedirs(app.config["VECTOR_STORE_DIR"], exist_ok=True)

    # ---------------- Extensions ----------------
    db.init_app(app)
    jwt.init_app(app)

    # ---------------- JWT Debug ----------------
    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        print("❌ INVALID TOKEN:", reason)
        return jsonify({"error": reason}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(reason):
        print("❌ UNAUTHORIZED:", reason)
        return jsonify({"error": reason}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        print("❌ TOKEN EXPIRED")
        return jsonify({"error": "Token expired"}), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        print("❌ TOKEN REVOKED")
        return jsonify({"error": "Token revoked"}), 401

    @jwt.needs_fresh_token_loader
    def needs_fresh_callback(jwt_header, jwt_payload):
        print("❌ FRESH TOKEN REQUIRED")
        return jsonify({"error": "Fresh token required"}), 401

    @jwt.user_lookup_error_loader
    def user_lookup_error(jwt_header, jwt_payload):
        print("❌ USER LOOKUP ERROR")
        return jsonify({"error": "User lookup failed"}), 401

    # --- CORS ---
    cors.init_app(
        app,
        resources={
            r"/api/*": {
                "origins": ["http://localhost:5173", "http://127.0.0.1:5173"], 
                "allow_headers": ["Content-Type", "Authorization", "Accept"],
                "supports_credentials": True
            }
        },
    )

    limiter.init_app(app)
    setup_logger(app)
    
    # 🌟 Phase 3: Register Middleware
    setup_request_logger(app)
    setup_security_headers(app)
    setup_content_validator(app)

    # ---------------- Blueprints ----------------
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
    
    from app.models import chat_extended_models
    from app.routes.chat_extended_routes import chat_ext_bp
    
    from app.routes.billing_routes import billing_bp
    from app.routes.plugin_routes import plugin_bp
    from app.routes.ai_studio_routes import ai_studio_bp
    from app.routes.unified_chat_engine import unified_engine_bp

    # Rate limiting for auth
    limiter.limit("10 per minute")(auth_bp)

    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(chat_bp, url_prefix="/api")
    app.register_blueprint(upload_bp, url_prefix="/api")
    app.register_blueprint(feedback_bp, url_prefix="/api")
    app.register_blueprint(history_bp, url_prefix="/api")
    app.register_blueprint(profile_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/api")
    app.register_blueprint(memory_bp, url_prefix="/api")
    app.register_blueprint(workspace_bp, url_prefix="/api")
    app.register_blueprint(agent_bp, url_prefix="/api")
    app.register_blueprint(productivity_bp, url_prefix="/api")
    app.register_blueprint(voice_bp, url_prefix="/api")
    app.register_blueprint(workflow_bp, url_prefix="/api")
    app.register_blueprint(collaboration_bp, url_prefix="/api")
    app.register_blueprint(marketplace_bp, url_prefix="/api")
    app.register_blueprint(saas_cloud_bp, url_prefix="/api")
    app.register_blueprint(intelligence_bp, url_prefix="/api")
    app.register_blueprint(rag_bp)
    app.register_blueprint(api_key_bp, url_prefix="/api")
    app.register_blueprint(chat_ext_bp)

    app.register_blueprint(billing_bp, url_prefix="/api")
    app.register_blueprint(plugin_bp, url_prefix="/api")
    app.register_blueprint(ai_studio_bp, url_prefix="/api")
    app.register_blueprint(unified_engine_bp, url_prefix="/api")

    # ---------------- Error Handlers ----------------
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Endpoint not found."}), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "File too large."}), 413

    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify({"error": "Too many requests. Please slow down."}), 429

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error(f"Unhandled server error: {e}")
        return jsonify({"error": "Internal server error."}), 500

    # ---------------- Routes ----------------
    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "ok",
            "service": "Isolde backend",
            "platform_tier": "Phase 12 Ecosystem Expansion OS"
        })

    @app.route("/", methods=["GET"])
    def serve_frontend():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/login", methods=["GET"])
    @app.route("/login.html", methods=["GET"])
    def serve_login_page():
        return send_from_directory(FRONTEND_DIR, "login.html")

    @app.route("/register", methods=["GET"])
    @app.route("/register.html", methods=["GET"])
    def serve_register_page():
        return send_from_directory(FRONTEND_DIR, "register.html")

    # 🛠️ FINAL FIX: Handled Multi-worker Race Condition for DB Creation
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"⚠️ DB Creation bypassed (Multi-worker race condition handled): {e}")

    return app