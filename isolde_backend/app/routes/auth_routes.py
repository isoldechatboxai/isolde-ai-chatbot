import os
from datetime import datetime, timezone

from flask import Blueprint, current_app, g, jsonify, make_response, redirect, request, send_from_directory
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError, OperationalError

from app.extensions import db
from app.models import User
from app.models.auth_model import AuthSession, AuthToken, OAuthAccount, RevokedToken, token_digest, utcnow
from app.services.oauth_service import (
    OAuthProviderError, PROVIDERS, begin_authorization, complete_authorization,
    provider_is_configured,
)
from app.utils.logger import log_event
from app.utils.validators import is_valid_email, is_valid_password, sanitize_text
from app.workers.email_worker import start_email_worker

auth_bp = Blueprint("auth", __name__)


def _deliver_auth_email(recipient, subject, path, token):
    if not all((
        current_app.config.get("MAIL_SERVER"),
        current_app.config.get("MAIL_USERNAME"),
        current_app.config.get("MAIL_PASSWORD"),
        current_app.config.get("MAIL_DEFAULT_SENDER"),
    )):
        current_app.logger.warning("Authentication email delivery is not configured.")
        return False
    link = f"{current_app.config['PUBLIC_APP_URL']}{path}?token={token}"
    return start_email_worker(
        current_app._get_current_object(), subject, recipient,
        f"Open this single-use link: {link}",
        f'<p>Open this single-use link:</p><p><a href="{link}">{link}</a></p>',
    )


def _user_with_normalized_email(email):
    """Return the user whose stored email normalizes to ``email``."""
    return User.query.filter(
        db.func.lower(db.func.trim(User.email)) == email
    ).first()


def _issue_user_token(user, purpose, lifetime_minutes):
    AuthToken.query.filter_by(user_id=user.id, purpose=purpose, used_at=None).update(
        {"used_at": utcnow()}, synchronize_session=False
    )
    raw, record = AuthToken.issue(user.id, purpose, lifetime_minutes)
    db.session.add(record)
    return raw


def _testing_token(response, name, raw):
    if current_app.config.get("TESTING") and current_app.config.get("EXPOSE_TEST_AUTH_TOKENS", True):
        response[name] = raw


def _create_login(user):
    lifetime = current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
    auth_session = AuthSession.create(
        user.id, lifetime, request.headers.get("User-Agent"), request.remote_addr
    )
    db.session.add(auth_session)
    db.session.commit()
    token = create_access_token(identity=user.id, additional_claims={"sid": auth_session.id})
    return token, auth_session


def _consume_token(raw, purpose):
    if not raw:
        return None
    now = utcnow()
    digest = token_digest(raw)
    record = AuthToken.query.filter_by(token_hash=digest, purpose=purpose).first()
    if not record or record.used_at is not None or record.expires_at <= now:
        return None
    # The conditional update makes consumption single-use even when two
    # workers receive the same reset/verification/OAuth exchange token.
    consumed = AuthToken.query.filter(
        AuthToken.id == record.id,
        AuthToken.used_at.is_(None),
        AuthToken.expires_at > now,
    ).update({"used_at": now}, synchronize_session=False)
    if consumed != 1:
        return None
    record.used_at = now
    return record


def _oauth_result(identity, link_user_id):
    existing = OAuthAccount.query.filter_by(
        provider=identity.provider, provider_subject=identity.subject
    ).first()
    if link_user_id:
        user = db.session.get(User, str(link_user_id))
        # Authorization can be revoked while the user is at the provider.  A
        # disabled account must not be able to gain a new sign-in method from
        # an authorization flow that was initiated earlier.
        if not user or not user.is_active:
            return jsonify({"error": "Linking session is no longer valid."}), 401
        if existing and existing.user_id != user.id:
            return jsonify({"error": "This provider account is already linked to another user."}), 409
        same_provider = OAuthAccount.query.filter_by(user_id=user.id, provider=identity.provider).first()
        if same_provider and (not existing or same_provider.id != existing.id):
            return jsonify({"error": "A different account from this provider is already linked."}), 409
        if not existing:
            db.session.add(OAuthAccount(
                user_id=user.id, provider=identity.provider,
                provider_subject=identity.subject, provider_email=identity.email,
            ))
        db.session.commit()
        return jsonify({"message": f"{identity.provider.title()} account linked."}), 200

    if existing:
        user = db.session.get(User, existing.user_id)
        if not user or not user.is_active:
            return jsonify({"error": "Authentication failed."}), 401
        existing.last_login_at = utcnow()
        db.session.commit()
        return jsonify({"message": "Authentication verified.", "user": user.to_dict()}), 200

    # Email equality is not proof of ownership. Existing accounts must sign in
    # first and explicitly link, preventing OAuth-based account takeover.
    if identity.email and User.query.filter_by(email=identity.email).first():
        return jsonify({
            "error": "An account with this email already exists. Sign in with the existing method, then link this provider."
        }), 409
    if not identity.email or not identity.email_verified:
        return jsonify({"error": "The provider did not supply a verified email address."}), 422
    user = User(name=identity.name or identity.email.split("@")[0], email=identity.email, is_verified=True)
    db.session.add(user)
    db.session.flush()
    db.session.add(OAuthAccount(
        user_id=user.id, provider=identity.provider,
        provider_subject=identity.subject, provider_email=identity.email,
    ))
    db.session.commit()
    return jsonify({"message": "Account created.", "user": user.to_dict()}), 201


@auth_bp.route("/register", methods=["GET"])
def serve_register_page():
    return send_from_directory(os.path.abspath(os.path.join(current_app.root_path, "../frontend")), "register.html")


@auth_bp.route("/login", methods=["GET"])
def serve_login_page():
    return send_from_directory(os.path.abspath(os.path.join(current_app.root_path, "../frontend")), "login.html")


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON payload."}), 400
    name = sanitize_text(str(data.get("name", ""))).strip()
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")
    if not name or len(name) > 120 or not is_valid_email(email):
        return jsonify({"error": "Valid name and email are required."}), 400
    ok, reason = is_valid_password(password)
    if not ok:
        return jsonify({"error": reason}), 400
    try:
        if _user_with_normalized_email(email):
            return jsonify({"error": "An account with this email already exists."}), 409
    except OperationalError:
        db.session.rollback()
        current_app.logger.warning(
            "Registration failed. request_id=%s category=DATABASE_UNAVAILABLE",
            getattr(g, "request_id", "N/A"),
        )
        return jsonify({"error": "Registration is temporarily unavailable. Please try again later."}), 503
    # A production account that must verify its email cannot be usable unless
    # the verification message can actually be delivered.  Refuse before any
    # database mutation instead of returning a successful registration for an
    # account that has no path to sign in.
    if current_app.config.get("REQUIRE_EMAIL_VERIFICATION") and not all((
        current_app.config.get("MAIL_SERVER"),
        current_app.config.get("MAIL_USERNAME"),
        current_app.config.get("MAIL_PASSWORD"),
        current_app.config.get("MAIL_DEFAULT_SENDER"),
    )) and not current_app.config.get("TESTING"):
        current_app.logger.error("Registration is unavailable: verification email delivery is not configured.")
        return jsonify({"error": "Registration is temporarily unavailable. Please try again later."}), 503
    user = User(name=name, email=email, is_verified=False)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.flush()
        raw = _issue_user_token(user, "verify_email", current_app.config["EMAIL_VERIFICATION_TOKEN_MINUTES"])
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        try:
            if _user_with_normalized_email(email):
                return jsonify({"error": "An account with this email already exists."}), 409
        except OperationalError:
            current_app.logger.warning(
                "Registration failed. request_id=%s category=DATABASE_UNAVAILABLE",
                getattr(g, "request_id", "N/A"),
            )
            return jsonify({"error": "Registration is temporarily unavailable. Please try again later."}), 503
        current_app.logger.error(
            "Registration failed. request_id=%s category=DATABASE_CONSTRAINT_ERROR",
            getattr(g, "request_id", "N/A"),
        )
        return jsonify({"error": "Registration is temporarily unavailable. Please try again later."}), 503
    except OperationalError:
        db.session.rollback()
        # The request did not commit. Do not expose database details or claim
        # successful registration when the database is unavailable.
        current_app.logger.warning(
            "Registration failed. request_id=%s category=DATABASE_UNAVAILABLE",
            getattr(g, "request_id", "N/A"),
        )
        return jsonify({"error": "Registration is temporarily unavailable. Please try again later."}), 503
    except Exception:
        db.session.rollback()
        current_app.logger.error(
            "Registration failed. request_id=%s category=INTERNAL_ERROR",
            getattr(g, "request_id", "N/A"),
        )
        return jsonify({"error": "An internal server error occurred."}), 500
    log_event(current_app, "REGISTER", "new user", user.id)
    delivered = _deliver_auth_email(user.email, "Verify your Isolde email", "/api/verify-email", raw)
    if current_app.config.get("REQUIRE_EMAIL_VERIFICATION") and not delivered and not current_app.config.get("TESTING"):
        return jsonify({
            "error": "Registration was saved, but verification email delivery failed. Request a new verification email.",
            "verification_required": True,
        }), 503
    response = {"message": "Registration successful. Verify your email before signing in.", "user": user.to_dict()}
    _testing_token(response, "verification_token", raw)
    return jsonify(response), 201


@auth_bp.route("/verify-email", methods=["GET", "POST"])
def verify_email():
    data = (request.get_json(silent=True) or {}) if request.method == "POST" else {}
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON payload."}), 400
    raw_token = request.args.get("token") if request.method == "GET" else data.get("token")
    record = _consume_token(str(raw_token or ""), "verify_email")
    if not record:
        return jsonify({"error": "Verification token is invalid or expired."}), 400
    user = db.session.get(User, record.user_id)
    if not user:
        return jsonify({"error": "Verification token is invalid or expired."}), 400
    user.is_verified = True
    db.session.commit()
    if request.method == "GET":
        return redirect("/login.html?verified=1")
    return jsonify({"message": "Email verified successfully."}), 200


@auth_bp.route("/resend-verification", methods=["POST"])
def resend_verification():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON payload."}), 400
    email = str(data.get("email") or "").strip().lower()
    delivery_configured = all(current_app.config.get(key) for key in (
        "MAIL_SERVER", "MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_DEFAULT_SENDER",
    ))
    if not delivery_configured and not current_app.config.get("TESTING"):
        return jsonify({"error": "Verification email delivery is not configured."}), 503
    user = User.query.filter_by(email=email).first() if is_valid_email(email) else None
    delivered = True
    if user and not user.is_verified:
        raw = _issue_user_token(user, "verify_email", current_app.config["EMAIL_VERIFICATION_TOKEN_MINUTES"])
        db.session.commit()
        delivered = _deliver_auth_email(user.email, "Verify your Isolde email", "/api/verify-email", raw)
    if not delivered:
        current_app.logger.warning("Verification email delivery failed category=EMAIL_DELIVERY_FAILED")
    return jsonify({
        "message": "If that account requires verification and delivery succeeds, a new link will be sent."
    }), 200


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON payload."}), 400
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")
    if len(password) > 128:
        return jsonify({"error": "Invalid email or password."}), 401
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password) or not user.is_active:
        log_event(current_app, "LOGIN_FAILED", "invalid credentials")
        return jsonify({"error": "Invalid email or password."}), 401
    if current_app.config.get("REQUIRE_EMAIL_VERIFICATION") and not user.is_verified:
        return jsonify({"error": "Email verification is required.", "verification_required": True}), 403
    token, auth_session = _create_login(user)
    log_event(current_app, "LOGIN_SUCCESS", "password", user.id)
    return jsonify({
        "message": "Login successful.", "access_token": token,
        "session_id": auth_session.id, "user": user.to_dict()
    }), 200


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    claims = get_jwt()
    sid = claims.get("sid")
    if sid:
        auth_session = db.session.get(AuthSession, sid)
        if auth_session and auth_session.user_id == str(get_jwt_identity()):
            auth_session.revoked_at = utcnow()
    db.session.merge(RevokedToken(
        jti=claims["jti"], user_id=str(get_jwt_identity()),
        expires_at=datetime.fromtimestamp(claims["exp"], timezone.utc).replace(tzinfo=None),
    ))
    db.session.commit()
    return jsonify({"message": "Logged out successfully."}), 200


@auth_bp.route("/logout-all", methods=["POST"])
@jwt_required()
def logout_all():
    AuthSession.query.filter_by(user_id=str(get_jwt_identity()), revoked_at=None).update(
        {"revoked_at": utcnow()}, synchronize_session=False
    )
    db.session.commit()
    return jsonify({"message": "All sessions have been revoked."}), 200


@auth_bp.route("/sessions", methods=["GET"])
@jwt_required()
def list_sessions():
    sessions = AuthSession.query.filter_by(user_id=str(get_jwt_identity())).order_by(AuthSession.created_at.desc()).all()
    return jsonify({"sessions": [{
        "id": item.id, "created_at": item.created_at.isoformat(),
        "last_seen_at": item.last_seen_at.isoformat(), "active": item.is_valid,
    } for item in sessions]}), 200


@auth_bp.route("/sessions/<session_id>", methods=["DELETE"])
@jwt_required()
def revoke_session(session_id):
    auth_session = AuthSession.query.filter_by(id=session_id, user_id=str(get_jwt_identity())).first()
    if not auth_session:
        return jsonify({"error": "Session not found."}), 404
    auth_session.revoked_at = utcnow()
    db.session.commit()
    return jsonify({"message": "Session revoked."}), 200


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON payload."}), 400
    email = str(data.get("email") or "").strip().lower()
    email_delivery_configured = all((
        current_app.config.get("MAIL_SERVER"),
        current_app.config.get("MAIL_USERNAME"),
        current_app.config.get("MAIL_PASSWORD"),
        current_app.config.get("MAIL_DEFAULT_SENDER"),
    ))
    # This reveals only a service-wide capability, never whether an account
    # exists. Do not claim a reset email was issued when delivery is absent.
    if not email_delivery_configured and not current_app.config.get("TESTING"):
        return jsonify({"error": "Password reset email delivery is not configured."}), 503
    user = User.query.filter_by(email=email).first() if is_valid_email(email) else None
    raw = None
    if user and user.password_hash:
        raw = _issue_user_token(user, "password_reset", current_app.config["PASSWORD_RESET_TOKEN_MINUTES"])
        db.session.commit()
        log_event(current_app, "PASSWORD_RESET_REQUEST", "requested", user.id)
        _deliver_auth_email(user.email, "Reset your Isolde password", "/login.html", raw)
    response = {"message": "If that account exists and delivery succeeds, password-reset instructions will be sent."}
    if raw:
        _testing_token(response, "reset_token", raw)
    return jsonify(response), 200


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON payload."}), 400
    new_password = str(data.get("new_password") or "")
    confirm_password = data.get("confirm_password")
    if not isinstance(confirm_password, str) or new_password != confirm_password:
        return jsonify({"error": "New password and confirmation do not match."}), 400
    ok, reason = is_valid_password(new_password)
    if not ok:
        return jsonify({"error": reason}), 400
    record = _consume_token(str(data.get("token") or ""), "password_reset")
    if not record:
        return jsonify({"error": "Reset token is invalid or expired."}), 400
    user = db.session.get(User, record.user_id)
    if not user:
        return jsonify({"error": "Reset token is invalid or expired."}), 400
    user.set_password(new_password)
    user.is_verified = True
    AuthSession.query.filter_by(user_id=user.id, revoked_at=None).update(
        {"revoked_at": utcnow()}, synchronize_session=False
    )
    db.session.commit()
    log_event(current_app, "PASSWORD_RESET_SUCCESS", "completed", user.id)
    return jsonify({"message": "Password has been reset. Sign in again."}), 200


@auth_bp.route("/oauth/<provider>/start", methods=["GET"])
def oauth_start(provider):
    if provider not in PROVIDERS:
        return jsonify({"error": "Unsupported OAuth provider."}), 404
    try:
        return redirect(begin_authorization(provider))
    except RuntimeError:
        return jsonify({"error": "OAuth provider is not configured."}), 503
    except ValueError:
        return jsonify({"error": "OAuth authorization could not be started."}), 400


@auth_bp.route("/oauth/providers", methods=["GET"])
def oauth_providers():
    return jsonify({"providers": {
        provider: provider_is_configured(provider) for provider in PROVIDERS
    }}), 200


@auth_bp.route("/oauth/<provider>/link", methods=["GET"])
@jwt_required()
def oauth_link_start(provider):
    if provider not in PROVIDERS:
        return jsonify({"error": "Unsupported OAuth provider."}), 404
    try:
        return redirect(begin_authorization(provider, get_jwt_identity()))
    except RuntimeError:
        return jsonify({"error": "OAuth provider is not configured."}), 503
    except ValueError:
        return jsonify({"error": "OAuth authorization could not be started."}), 400


@auth_bp.route("/oauth/<provider>/callback", methods=["GET", "POST"])
def oauth_callback(provider):
    if provider not in PROVIDERS:
        return jsonify({"error": "Unsupported OAuth provider."}), 404
    if request.values.get("error"):
        return jsonify({"error": "OAuth authorization was denied or failed."}), 400
    try:
        identity, link_user_id = complete_authorization(
            provider, request.values.get("code"), request.values.get("state")
        )
        result = _oauth_result(identity, link_user_id)
        response, status = result
        if status >= 400:
            return response, status
        if link_user_id:
            return redirect("/?oauth_linked=1")
        payload = response.get_json() or {}
        user = db.session.get(User, str((payload.get("user") or {}).get("id")))
        if not user:
            return jsonify({"error": "OAuth login could not be completed."}), 500
        raw, exchange = AuthToken.issue(user.id, "oauth_exchange", 5)
        db.session.add(exchange)
        db.session.commit()
        browser_response = make_response(redirect("/login.html?oauth=complete"))
        browser_response.set_cookie(
            "oauth_exchange", raw, max_age=300, httponly=True,
            secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
            samesite="Lax", path="/api/oauth/session",
        )
        return browser_response
    except OAuthProviderError:
        db.session.rollback()
        current_app.logger.warning("OAuth callback failed provider=%s category=UPSTREAM_UNAVAILABLE", provider)
        return jsonify({"error": "OAuth provider is temporarily unavailable."}), 502
    except RuntimeError:
        db.session.rollback()
        current_app.logger.warning("OAuth callback failed provider=%s category=NOT_CONFIGURED", provider)
        return jsonify({"error": "OAuth provider is not configured."}), 503
    except IntegrityError:
        db.session.rollback()
        current_app.logger.warning("OAuth callback failed provider=%s category=ACCOUNT_CONFLICT", provider)
        return jsonify({"error": "OAuth account could not be linked safely."}), 409
    except Exception:
        db.session.rollback()
        current_app.logger.warning("OAuth callback failed provider=%s category=VALIDATION_FAILED", provider)
        return jsonify({"error": "OAuth response could not be verified."}), 400


@auth_bp.route("/oauth/session", methods=["POST"])
def oauth_session_exchange():
    record = _consume_token(request.cookies.get("oauth_exchange"), "oauth_exchange")
    if not record:
        response = jsonify({"error": "OAuth login session is invalid or expired."})
        response.delete_cookie("oauth_exchange", path="/api/oauth/session")
        return response, 401
    user = db.session.get(User, record.user_id)
    if not user or not user.is_active:
        db.session.rollback()
        return jsonify({"error": "Authentication failed."}), 401
    token, _ = _create_login(user)
    response = jsonify({"message": "Login successful.", "access_token": token, "user": user.to_dict()})
    response.delete_cookie("oauth_exchange", path="/api/oauth/session")
    return response, 200


@auth_bp.route("/oauth/accounts", methods=["GET"])
@jwt_required()
def oauth_accounts():
    accounts = OAuthAccount.query.filter_by(user_id=str(get_jwt_identity())).all()
    return jsonify({"accounts": [account.to_dict() for account in accounts]}), 200


@auth_bp.route("/oauth/accounts/<provider>", methods=["DELETE"])
@jwt_required()
def oauth_unlink(provider):
    user = db.session.get(User, str(get_jwt_identity()))
    account = OAuthAccount.query.filter_by(user_id=user.id, provider=provider).first()
    if not account:
        return jsonify({"error": "Linked provider not found."}), 404
    other_accounts = OAuthAccount.query.filter_by(user_id=user.id).count()
    if not user.password_hash and other_accounts <= 1:
        return jsonify({"error": "Add another authentication method before unlinking this provider."}), 409
    db.session.delete(account)
    db.session.commit()
    return jsonify({"message": f"{provider.title()} account unlinked."}), 200
