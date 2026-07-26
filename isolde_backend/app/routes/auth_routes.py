import random
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, current_app
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


@auth_bp.route("/register", methods=["POST"])
def register():
    # FIX 3: silent=True prevents Flask from throwing an HTML error if JSON is missing or malformed
    data = request.get_json(silent=True)

    if data is None:
        return jsonify({"error": "Invalid JSON payload."}), 400

    # FIX 1: Safely cast inputs to str before calling string methods to prevent 500 errors
    name = sanitize_text(str(data.get("name", ""))).strip()
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password", ""))

    if not name or not is_valid_email(email):
        return jsonify({"error": "Valid name and email are required."}), 400

    ok, reason = is_valid_password(password)

    if not ok:
        return jsonify({"error": reason}), 400

    user = User(name=name, email=email)
    user.set_password(password)

    db.session.add(user)
    
    # FIX 4: Handle database race conditions and ensure rollbacks on errors
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

    # Integer identity instead of string
    token = create_access_token(identity=user.id)

    log_event(current_app, "LOGIN_SUCCESS", email, user.id)

    return jsonify({
        "message": "Login successful.",
        "access_token": token,
        "user": user.to_dict()
    }), 200


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

    # Show OTP only in development mode
    if current_app.config.get("DEBUG"):
        response["dev_otp"] = otp

    return jsonify(response), 200


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True)

    if data is None:
        return jsonify({"error": "Invalid JSON payload."}), 400

    email = str(data.get("email") or "").strip().lower()
    otp = str(data.get("otp", ""))  # FIX 2: Explicitly cast to string to prevent mismatched type comparisons
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