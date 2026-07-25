import random
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token
from app.extensions import db
from app.models import User
from app.utils.validators import is_valid_email, is_valid_password, sanitize_text
from app.utils.logger import log_event

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    name = sanitize_text(data.get("name", ""))
    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")

    if not name or not is_valid_email(email):
        return jsonify({"error": "Valid name and email are required."}), 400

    ok, reason = is_valid_password(password)
    if not ok:
        return jsonify({"error": reason}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists."}), 409

    user = User(name=name, email=email)
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    log_event(current_app, "REGISTER", f"new user {email}", user.id)

    return jsonify({
        "message": "Registration successful.",
        "user": user.to_dict()
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        log_event(current_app, "LOGIN_FAILED", f"attempt for {email}")
        return jsonify({"error": "Invalid email or password."}), 401

    token = create_access_token(identity=str(user.id))

    log_event(current_app, "LOGIN_SUCCESS", email, user.id)

    return jsonify({
        "access_token": token,
        "user": user.to_dict()
    })


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({
            "message": "If that account exists, an OTP has been sent."
        })

    otp = f"{random.randint(100000,999999)}"

    user.reset_otp = otp
    user.reset_otp_expires = datetime.now(timezone.utc) + timedelta(minutes=10)

    db.session.commit()

    log_event(current_app, "PASSWORD_RESET_REQUEST", email, user.id)

    return jsonify({
        "message": "If that account exists, an OTP has been sent.",
        "dev_otp": otp
    })


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    otp = data.get("otp", "")
    new_password = data.get("new_password", "")

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

    db.session.commit()

    log_event(current_app, "PASSWORD_RESET_SUCCESS", email, user.id)

    return jsonify({
        "message": "Password has been reset. You can now log in."
    })