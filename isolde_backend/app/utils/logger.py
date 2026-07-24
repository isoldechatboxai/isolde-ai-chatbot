import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logger(app):
    """Attach rotating file + console logging to the Flask app."""
    log_dir = app.config["LOG_DIR"]
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "isolde.log")
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )

    file_handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=5)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.INFO)

    return app.logger


def log_event(app, event_type: str, detail: str, user_id=None):
    """Standardized structured log line for auth/chat/feedback/etc events."""
    uid = f"user={user_id}" if user_id else "user=anonymous"
    app.logger.info(f"[{event_type}] {uid} | {detail}")
