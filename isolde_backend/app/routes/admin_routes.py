"""
Admin Panel Routes — Production-Grade.
Manages: Users, Conversations, Messages, Settings, Broadcasts, Feedback.
All endpoints (except admin login) require a valid JWT with role in
("Admin", "Super Admin").
"""

import secrets
import string
from functools import wraps

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token

from app.extensions import db
from app.models.user import User, Setting, Broadcast
from app.models.conversation import Conversation, Message
from app.models.feedback import Feedback
from app.models.auth_model import AuthSession
from app.models.billing_model import CreditBalance, Invoice, Subscription
from app.models.collaboration_model import Organization, OrganizationMember

admin_bp = Blueprint("admin", __name__)

ADMIN_ROLES = ("Admin", "Super Admin")


# ---------------------------------------------------------------------------
# Admin Role Guard Decorator
# ---------------------------------------------------------------------------

def admin_required(fn):
    """
    Decorator that enforces:
      1. Valid JWT token (via @jwt_required)
      2. The authenticated user has an administrative role
    Must be applied AFTER @jwt_required().
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"status": "error", "message": "User not found."}), 401
        if user.role not in ADMIN_ROLES:
            return jsonify({"status": "error", "message": "Admin access denied."}), 403
        return fn(user, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# 1. SECURE ADMIN LOGIN
# ---------------------------------------------------------------------------

@admin_bp.route("/admin/login", methods=["POST"], strict_slashes=False)
def admin_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"status": "error", "message": "Email and password are required."}), 400

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({"status": "error", "message": "Invalid email or password."}), 401

    if user.role not in ADMIN_ROLES:
        return jsonify({"status": "error", "message": "Access denied. Admin privileges required."}), 403

    if user.status != "Active":
        return jsonify({"status": "error", "message": "Account is not active."}), 403

    auth_session = AuthSession.create(
        user.id, current_app.config["JWT_ACCESS_TOKEN_EXPIRES"],
        request.headers.get("User-Agent"), request.remote_addr,
    )
    db.session.add(auth_session)
    db.session.commit()
    access_token = create_access_token(identity=user.id, additional_claims={"sid": auth_session.id})

    return jsonify({
        "status": "success",
        "message": "Admin login successful.",
        "access_token": access_token,
        "admin": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
        },
    }), 200


# ---------------------------------------------------------------------------
# 2. DASHBOARD / OVERVIEW STATS
# ---------------------------------------------------------------------------

@admin_bp.route("/admin/dashboard", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_dashboard(admin_user):
    total_users = User.query.count()
    total_conversations = Conversation.query.count()
    total_messages = Message.query.count()
    total_feedback = Feedback.query.count()
    active_users = User.query.filter_by(status="Active").count()

    return jsonify({
        "status": "success",
        "dashboard": {
            "total_users": total_users,
            "active_users": active_users,
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "total_feedback": total_feedback,
        },
    }), 200


@admin_bp.route("/admin/tenants", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_tenants(admin_user):
    organizations = Organization.query.order_by(Organization.created_at.desc()).all()
    return jsonify({"status": "success", "tenants": [{
        **org.to_dict(),
        "member_count": OrganizationMember.query.filter_by(org_id=org.id).count(),
    } for org in organizations]}), 200


@admin_bp.route("/admin/billing-summary", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_billing_summary(admin_user):
    return jsonify({"status": "success", "billing": {
        "subscriptions": Subscription.query.count(),
        "invoices": Invoice.query.count(),
        "recorded_credits": db.session.query(db.func.coalesce(db.func.sum(CreditBalance.credits), 0)).scalar(),
        "provider": "Not configured" if not current_app.config.get("PAYMENT_PROVIDER") else current_app.config["PAYMENT_PROVIDER"],
    }}), 200


@admin_bp.route("/admin/provider-status", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_provider_status(admin_user):
    providers = {
        "gemini": bool(current_app.config.get("GEMINI_API_KEY") and current_app.config.get("GEMINI_MODEL")),
        "openai": bool(current_app.config.get("OPENAI_API_KEY")),
        "claude": bool(current_app.config.get("ANTHROPIC_API_KEY")),
        "openrouter": bool(current_app.config.get("OPENROUTER_API_KEY")),
        "deepseek": bool(current_app.config.get("DEEPSEEK_API_KEY")),
        "mistral": bool(current_app.config.get("MISTRAL_API_KEY")),
    }
    return jsonify({"status": "success", "providers": {
        name: "Configured" if configured else "Not configured"
        for name, configured in providers.items()
    }}), 200


@admin_bp.route("/admin/operations", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_operations(admin_user):
    from app.services.health_service import health_service
    health = health_service.check_system_health()
    return jsonify({"status": "success", "operations": {
        "health": health,
        "storage_backend": current_app.config.get("STORAGE_BACKEND", "local"),
        "rag_backend": current_app.config.get("RAG_STORAGE_BACKEND", "database"),
        "rate_limit_storage": "Redis" if current_app.config.get("RATELIMIT_STORAGE_URI", "").startswith("redis") else "Not configured",
        "logs": "File logging enabled" if current_app.config.get("LOG_TO_FILE") else "Application logger",
    }}), 200


# ---------------------------------------------------------------------------
# 3. USER MANAGEMENT
# ---------------------------------------------------------------------------

@admin_bp.route("/admin/users", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def list_users(admin_user):
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({
        "status": "success",
        "users": [u.to_dict() for u in users],
    }), 200


@admin_bp.route("/admin/users", methods=["POST"], strict_slashes=False)
@jwt_required()
@admin_required
def create_user(admin_user):
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()

    if not name or not email:
        return jsonify({"status": "error", "message": "Name and email are required."}), 400

    existing = User.query.filter_by(email=email).first()
    if existing:
        return jsonify({"status": "error", "message": "A user with this email already exists."}), 400

    temp_password = ''.join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(16)
    )

    try:
        user = User(name=name, email=email)
        user.set_password(temp_password)
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin user create error: {e}")
        return jsonify({"status": "error", "message": "Failed to create user."}), 500

    return jsonify({
        "status": "success",
        "message": "User created.",
        "user": user.to_dict(),
        "temporary_password": temp_password,
    }), 201


@admin_bp.route("/admin/users/<user_id>", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def get_user_detail(admin_user, user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found."}), 404

    conversation_count = Conversation.query.filter_by(user_id=user_id).count()

    data = user.to_dict()
    data["conversation_count"] = conversation_count

    return jsonify({"status": "success", "user": data}), 200


@admin_bp.route("/admin/users/<user_id>", methods=["PATCH"], strict_slashes=False)
@jwt_required()
@admin_required
def update_user(admin_user, user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found."}), 404
    data = request.get_json(silent=True) or {}

    try:
        if "role" in data:
            if admin_user.role != "Super Admin":
                return jsonify({
                    "status": "error",
                    "message": "Only Super Admin can change user roles."
                }), 403

            if data["role"] not in ("Client", "Admin", "Super Admin"):
                return jsonify({
                    "status": "error",
                    "message": "Invalid role."
                }), 400

            user.role = data["role"]

        if "status" in data:
            user.status = data["status"]

        if "name" in data:
            user.name = data["name"]

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin user update error: {e}")
        return jsonify({
            "status": "error",
            "message": "Failed to update user."
        }), 500


@admin_bp.route("/admin/users/<user_id>", methods=["DELETE"], strict_slashes=False)
@jwt_required()
@admin_required
def delete_user(admin_user, user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found."}), 404

    if user.id == admin_user.id:
        return jsonify({"status": "error", "message": "You cannot delete your own account."}), 400

    try:
        db.session.delete(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin user delete error: {e}")
        return jsonify({"status": "error", "message": "Failed to delete user."}), 500

    return jsonify({"status": "success", "message": "User deleted."}), 200


# ---------------------------------------------------------------------------
# 4. CONVERSATION & MESSAGE MANAGEMENT
# ---------------------------------------------------------------------------

@admin_bp.route("/admin/conversations", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def list_conversations(admin_user):
    conversations = (
        Conversation.query
        .order_by(Conversation.created_at.desc())
        .all()
    )

    result = []
    for convo in conversations:
        item = convo.to_dict()
        item["message_count"] = len(convo.messages)
        item["user_email"] = None
        if convo.user:
            item["user_email"] = convo.user.email
        result.append(item)

    return jsonify({"status": "success", "conversations": result}), 200


@admin_bp.route("/admin/conversations/<conversation_id>", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def get_conversation_detail(admin_user, conversation_id):
    convo = db.session.get(Conversation, conversation_id)
    if not convo:
        return jsonify({"status": "error", "message": "Conversation not found."}), 404

    data = convo.to_dict(include_messages=True)
    data["user_email"] = convo.user.email if convo.user else None

    return jsonify({"status": "success", "conversation": data}), 200


@admin_bp.route("/admin/conversations/<conversation_id>", methods=["DELETE"], strict_slashes=False)
@jwt_required()
@admin_required
def delete_conversation(admin_user, conversation_id):
    convo = db.session.get(Conversation, conversation_id)
    if not convo:
        return jsonify({"status": "error", "message": "Conversation not found."}), 404

    try:
        db.session.delete(convo)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin conversation delete error: {e}")
        return jsonify({"status": "error", "message": "Failed to delete conversation."}), 500

    return jsonify({"status": "success", "message": "Conversation deleted."}), 200


# ---------------------------------------------------------------------------
# 5. SETTINGS MANAGEMENT
# ---------------------------------------------------------------------------

@admin_bp.route("/admin/settings", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def list_settings(admin_user):
    settings = Setting.query.all()
    return jsonify({
        "status": "success",
        "settings": [s.to_dict() for s in settings],
    }), 200


@admin_bp.route("/admin/settings", methods=["POST"], strict_slashes=False)
@jwt_required()
@admin_required
def save_setting(admin_user):
    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    value = data.get("value", "")

    if not key:
        return jsonify({"status": "error", "message": "Setting key is required."}), 400

    try:
        existing = Setting.query.filter_by(key=key).first()
        if existing:
            existing.value = value
        else:
            new_setting = Setting(key=key, value=value)
            db.session.add(new_setting)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin setting save error: {e}")
        return jsonify({"status": "error", "message": "Failed to save setting."}), 500

    return jsonify({"status": "success", "message": f"Setting '{key}' saved."}), 200


@admin_bp.route("/admin/settings/<setting_key>", methods=["DELETE"], strict_slashes=False)
@jwt_required()
@admin_required
def delete_setting(admin_user, setting_key):
    setting = Setting.query.filter_by(key=setting_key).first()
    if not setting:
        return jsonify({"status": "error", "message": "Setting not found."}), 404

    try:
        db.session.delete(setting)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin setting delete error: {e}")
        return jsonify({"status": "error", "message": "Failed to delete setting."}), 500

    return jsonify({"status": "success", "message": "Setting deleted."}), 200


@admin_bp.route("/admin/settings/test-key", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def test_api_key(admin_user):
    try:
        from app.services.provider_router import get_provider_manager
        
        # 1. Resolve the currently active AI provider
        manager = get_provider_manager()
        provider = manager.resolve_active_provider()
        
        # 2. Attempt to fetch the provider-specific API key
        try:
            manager.get_api_key_for_provider(provider)
            return jsonify({
                "status": "success",
                "key_configured": True,
                "provider": provider,
                "message": "API key is configured."
            }), 200
            
        except RuntimeError as e:
            # 3. Handle missing key gracefully (HTTP 200, key_configured: false)
            return jsonify({
                "status": "error",
                "key_configured": False,
                "provider": provider,
                "message": str(e)
            }), 200
            
    except Exception as e:
        # 4. Catch-all for unexpected DB/Import errors to prevent HTML 500 pages
        current_app.logger.error(f"API key test error: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "key_configured": False,
            "provider": "unknown",
            "message": "Failed to test API key due to an unexpected server error."
        }), 200


# ---------------------------------------------------------------------------
# 6. BROADCAST MANAGEMENT
# ---------------------------------------------------------------------------

@admin_bp.route("/admin/broadcasts", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def list_broadcasts(admin_user):
    broadcasts = Broadcast.query.order_by(Broadcast.timestamp.desc()).all()
    return jsonify({
        "status": "success",
        "broadcasts": [b.to_dict() for b in broadcasts],
    }), 200


@admin_bp.route("/admin/broadcasts", methods=["POST"], strict_slashes=False)
@jwt_required()
@admin_required
def create_broadcast(admin_user):
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    target = data.get("target", "All Users")

    if not message:
        return jsonify({"status": "error", "message": "Broadcast message is required."}), 400

    try:
        broadcast = Broadcast(message=message, target=target)
        db.session.add(broadcast)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin broadcast create error: {e}")
        return jsonify({"status": "error", "message": "Failed to send broadcast."}), 500

    return jsonify({
        "status": "success",
        "message": "Broadcast sent.",
        "broadcast": broadcast.to_dict(),
    }), 201


@admin_bp.route("/admin/broadcasts/<int:broadcast_id>", methods=["DELETE"], strict_slashes=False)
@jwt_required()
@admin_required
def delete_broadcast(admin_user, broadcast_id):
    broadcast = db.session.get(Broadcast, broadcast_id)
    if not broadcast:
        return jsonify({"status": "error", "message": "Broadcast not found."}), 404

    try:
        db.session.delete(broadcast)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin broadcast delete error: {e}")
        return jsonify({"status": "error", "message": "Failed to delete broadcast."}), 500

    return jsonify({"status": "success", "message": "Broadcast deleted."}), 200


# ---------------------------------------------------------------------------
# 7. FEEDBACK MANAGEMENT
# ---------------------------------------------------------------------------

@admin_bp.route("/admin/feedback", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def list_feedback(admin_user):
    feedback_items = Feedback.query.order_by(Feedback.created_at.desc()).all()
    return jsonify({
        "status": "success",
        "feedback": [f.to_dict() for f in feedback_items],
    }), 200


@admin_bp.route("/admin/feedback/<feedback_id>", methods=["DELETE"], strict_slashes=False)
@jwt_required()
@admin_required
def delete_feedback(admin_user, feedback_id):
    fb = db.session.get(Feedback, feedback_id)
    if not fb:
        return jsonify({"status": "error", "message": "Feedback not found."}), 404

    try:
        db.session.delete(fb)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin feedback delete error: {e}")
        return jsonify({"status": "error", "message": "Failed to delete feedback."}), 500

    return jsonify({"status": "success", "message": "Feedback deleted."}), 200
