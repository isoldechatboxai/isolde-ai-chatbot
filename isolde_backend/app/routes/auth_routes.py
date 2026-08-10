# app/routes/auth_routes.py
import random
import os
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import create_access_token
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import User
from app.utils.validators import (
    is_valid_email,
    is_valid_password,
    sanitize_text,
)
from app.utils.logger import log_event

auth_bp = Blueprint("auth", __name__)


# 🌟 NEW: Serve frontend HTML pages directly to avoid 404 / Endpoint errors
@auth_bp.route("/register", methods=["GET"])
def serve_register_page():
    frontend_dir = os.path.abspath(os.path.join(current_app.root_path, '../frontend'))
    return send_from_directory(frontend_dir, 'register.html')


@auth_bp.route("/login", methods=["GET"])
def serve_login_page():
    frontend_dir = os.path.abspath(os.path.join(current_app.root_path, '../frontend'))
    return send_from_directory(frontend_dir, 'login.html')


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)

    if data is None:
        return jsonify({"error": "Invalid JSON payload."}), 400

    name = sanitize_text(str(data.get("name", ""))).strip()
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")

    if not name or not is_valid_email(email):
        return jsonify({"error": "Valid name and email are required."}), 400

    ok, reason = is_valid_password(password)

    if not ok:
        return jsonify({"error": reason}), 400

    user = User(name=name, email=email)
    user.set_password(password)

    db.session.add(user)
    
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(
            {"error": "An account with this email already exists."}
        ), 409
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration DB Error: {str(e)}")
        return jsonify({"error": "An internal server error occurred."}), 500

    log_event(current_app, "REGISTER", f"new user {email}", user.id)

    return jsonify({
        "message": "Registration successful.",
        "user": user.to_dict()
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)

    if data is None:
        return jsonify({"error": "Invalid JSON payload."}), 400

    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password", ""))

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        log_event(current_app, "LOGIN_FAILED", f"attempt for {email}")
        return jsonify({"error": "Invalid email or password."}), 401

    token = create_access_token(identity=user.id)

    log_event(current_app, "LOGIN_SUCCESS", email, user.id)

    return jsonify({
        "message": "Login successful.",
        "access_token": token,
        "user": user.to_dict()
    }), 200


@auth_bp.route("/logout", methods=["POST"])
def logout():
    return jsonify({"message": "Logged out successfully."}), 200


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json(silent=True)

    if data is None:
        return jsonify({"error": "Invalid JSON payload."}), 400

    email = str(data.get("email") or "").strip().lower()

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({
            "message": "If that account exists, an OTP has been sent."
        }), 200

    otp = f"{random.randint(100000, 999999)}"

    user.reset_otp = otp
    user.reset_otp_expires = (
        datetime.now(timezone.utc) + timedelta(minutes=10)
    )

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Forgot Password DB Error: {str(e)}")
        return jsonify({"error": "An internal server error occurred."}), 500

    log_event(current_app, "PASSWORD_RESET_REQUEST", email, user.id)

    response = {
        "message": "If that account exists, an OTP has been sent."
    }

    if current_app.config.get("DEBUG"):
        response["dev_otp"] = otp

    return jsonify(response), 200


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True)

    if data is None:
        return jsonify({"error": "Invalid JSON payload."}), 400

    email = str(data.get("email") or "").strip().lower()
    otp = str(data.get("otp", ""))  
    new_password = str(data.get("new_password", ""))

    user = User.query.filter_by(email=email).first()

    if not user or user.reset_otp != otp:
        return jsonify({"error": "Invalid OTP."}), 400

    if (
        not user.reset_otp_expires
        or datetime.now(timezone.utc)
        > user.reset_otp_expires.replace(tzinfo=timezone.utc)
    ):
        return jsonify({"error": "OTP has expired."}), 400

    ok, reason = is_valid_password(new_password)

    if not ok:
        return jsonify({"error": reason}), 400

    user.set_password(new_password)
    user.reset_otp = None
    user.reset_otp_expires = None

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Reset Password DB Error: {str(e)}")
        return jsonify({"error": "An internal server error occurred."}), 500

    log_event(current_app, "PASSWORD_RESET_SUCCESS", email, user.id)

    return jsonify({
        "message": "Password has been reset. You can now log in."
    }), 200