import os
from flask import Flask, jsonify, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config, FRONTEND_DIR
from app.extensions import db, jwt, cors
from app.utils.logger import setup_logger

limiter = Limiter(key_func=get_remote_address, default_limits=["120 per minute"])


def create_app(config_class=Config):
    # Serve the frontend (index.html/style.css/script.js) directly from
    # Flask as static files. This makes the app same-origin by default,
    # so the browser never even sends a cross-origin request for /api/*
    # and CORS problems disappear for the common case of just running
    # `python run.py` and opening http://127.0.0.1:5000/.
    app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["LOG_DIR"], exist_ok=True)
    os.makedirs(app.config["VECTOR_STORE_DIR"], exist_ok=True)

    # --- Extensions ---
    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    limiter.init_app(app)
    setup_logger(app)

    # --- Blueprints ---
    from app.routes.auth_routes import auth_bp
    from app.routes.chat_routes import chat_bp
    from app.routes.upload_routes import upload_bp
    from app.routes.feedback_routes import feedback_bp
    from app.routes.history_routes import history_bp
    from app.routes.profile_routes import profile_bp

    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(chat_bp, url_prefix="/api")
    app.register_blueprint(upload_bp, url_prefix="/api")
    app.register_blueprint(feedback_bp, url_prefix="/api")
    app.register_blueprint(history_bp, url_prefix="/api")
    app.register_blueprint(profile_bp, url_prefix="/api")

    # --- Tighter limits on auth endpoints (brute-force protection) ---
    limiter.limit("10 per minute")(auth_bp)

    # --- Error handlers ---
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

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "Isolde backend"})

    @app.route("/", methods=["GET"])
    def serve_frontend():
        return send_from_directory(FRONTEND_DIR, "index.html")

    with app.app_context():
        db.create_all()

    return app
