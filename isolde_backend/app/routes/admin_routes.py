"""
Admin Panel Routes — Production-Grade.
Manages: Users, Conversations, Messages, Settings, Broadcasts, Feedback.
All endpoints (except admin login) require a valid JWT with role in
("Admin", "Super Admin").
"""

import secrets
import string
import os
import json
from functools import wraps

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity, create_access_token

from app.extensions import db
from sqlalchemy import text
from app.models.user import User, Setting, Broadcast
from app.models.conversation import Conversation, Message
from app.models.feedback import Feedback
from app.models.auth_model import AuthSession, utcnow
from app.models.billing_model import CreditBalance, CreditLedger, Invoice, PaymentEvent, Subscription
from app.models.collaboration_model import Organization, OrganizationMember, OrganizationPolicy
from app.models.collaboration_model import OrganizationProject, OrganizationRole
from app.models.enterprise_models import AuditLog
from app.models.rag_model import RAGChunk, RAGDocument
from app.models.uploaded_file import UploadedFile
from app.models.workspace_model import Project, Workspace
from app.models.workflow_model import Workflow, WorkflowExecution
from app.services.admin_configuration_service import public_configuration, update_configuration
from app.services.organization_policy_service import SUPPORTED_PROVIDERS
from app.utils.logger import log_event
from app.utils.validators import is_valid_email

admin_bp = Blueprint("admin", __name__)

ADMIN_ROLES = ("Admin", "Super Admin")
SECRET_SETTING_SUFFIXES = ("_api_key", "_secret", "_token", "_password", "_private_key", "_credential")
PROVIDER_SETTING_KEYS = {
    "ai_provider", "provider_fallbacks", "provider_priority",
    *(f"{name}_api_key" for name in SUPPORTED_PROVIDERS),
    *(f"{name}_model" for name in SUPPORTED_PROVIDERS),
}


def _is_secret_setting(key):
    return str(key).strip().lower().endswith(SECRET_SETTING_SUFFIXES)


def admin_required(fn):
    """Require an active authenticated administrator."""
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


def _audit(admin_user, action, details=None, status="success"):
    safe_details = json.dumps(details or {}, sort_keys=True)[:4000]
    db.session.add(AuditLog(
        actor_user_id=str(admin_user.id), action=action[:100], status=status[:20],
        ip_address=(request.remote_addr or "")[:50], details=safe_details,
    ))


def _pagination_args():
    """Bound and validate list pagination for versioned admin resources."""
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 50))
    except (TypeError, ValueError):
        return None
    if page < 1 or page_size < 1 or page_size > 200:
        return None
    return page, page_size


def _page(query, serializer):
    values = _pagination_args()
    if not values:
        return None
    page, page_size = values
    total = query.order_by(None).count()
    items = query.limit(page_size).offset((page - 1) * page_size).all()
    return {
        "items": [serializer(item) for item in items],
        "pagination": {
            "page": page, "page_size": page_size, "total": total,
            "has_next": page * page_size < total,
        },
    }


def _admin_session_payload(session):
    return {
        "id": session.id,
        "created_at": session.created_at.isoformat(),
        "last_seen_at": session.last_seen_at.isoformat(),
        "expires_at": session.expires_at.isoformat(),
        "revoked_at": session.revoked_at.isoformat() if session.revoked_at else None,
        "active": session.is_valid,
    }


@admin_bp.route("/product/config", methods=["GET"], strict_slashes=False)
def product_configuration():
    return jsonify({"status": "success", **public_configuration()}), 200


@admin_bp.route("/admin/configuration", methods=["GET", "PATCH"], strict_slashes=False)
@admin_bp.route("/admin/v1/configuration", methods=["GET", "PATCH"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_configuration(admin_user):
    if request.method == "GET":
        return jsonify({
            "status": "success", "configuration": public_configuration(),
            "runtime": {
                "environment": current_app.config.get("ENVIRONMENT", "development"),
                "storage_backend": current_app.config.get("STORAGE_BACKEND", "local"),
                "rag_backend": current_app.config.get("RAG_STORAGE_BACKEND", "database"),
                "rate_limit_backend": "Redis" if current_app.config.get("RATELIMIT_STORAGE_URI", "").startswith("redis") else "NOT_CONFIGURED",
                "media_configuration": {"image": "NOT_CONFIGURED", "video": "NOT_CONFIGURED"},
                "training": "NOT_SUPPORTED",
            },
        }), 200
    try:
        changed = update_configuration(request.get_json(silent=True))
        _audit(admin_user, "ADMIN_CONFIGURATION_UPDATE", {"keys": changed})
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 400
    return jsonify({"status": "success", "configuration": public_configuration()}), 200


@admin_bp.route("/admin/providers/configuration", methods=["GET", "PATCH"], strict_slashes=False)
@admin_bp.route("/admin/v1/providers/configuration", methods=["GET", "PATCH"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_provider_configuration(admin_user):
    from app.services.provider_router import ProviderManager, DEFAULT_MODELS, MODEL_SETTING_KEYS
    manager = ProviderManager()
    if request.method == "GET":
        return jsonify({"status": "success", "configuration": {
            "active_provider": manager.resolve_active_provider(),
            "models": {name: manager.get_model_for_provider(name) for name in sorted(SUPPORTED_PROVIDERS)},
            "defaults": DEFAULT_MODELS,
            "runtime_policy": {"timeout_seconds": 60, "max_retries": 3, "streaming": True, "usage": "provider_authoritative_or_unavailable"},
        }}), 200
    data = request.get_json(silent=True) or {}
    provider = str(data.get("active_provider") or "").strip().lower()
    models = data.get("models", {})
    if provider and provider not in SUPPORTED_PROVIDERS:
        return jsonify({"status": "error", "message": "Unsupported provider."}), 400
    if not isinstance(models, dict):
        return jsonify({"status": "error", "message": "models must be an object."}), 400
    for name, model in models.items():
        if name not in SUPPORTED_PROVIDERS or not isinstance(model, str) or not model.strip() or len(model.strip()) > 120:
            return jsonify({"status": "error", "message": "Invalid provider model configuration."}), 400
    changed = []
    if provider:
        try:
            manager.get_api_key_for_provider(provider)
        except RuntimeError:
            return jsonify({"status": "error", "capability": "NOT_CONFIGURED", "message": "Provider credentials are not configured."}), 422
        row = Setting.query.filter_by(key="ai_provider").first() or Setting(key="ai_provider")
        row.value = provider
        db.session.add(row)
        changed.append("ai_provider")
    for name, model in models.items():
        key = MODEL_SETTING_KEYS[name]
        row = Setting.query.filter_by(key=key).first() or Setting(key=key)
        row.value = model.strip()
        db.session.add(row)
        changed.append(key)
    if not changed:
        return jsonify({"status": "error", "message": "No provider configuration supplied."}), 400
    _audit(admin_user, "ADMIN_PROVIDER_CONFIGURATION", {"keys": changed})
    db.session.commit()
    return jsonify({"status": "success", "changed": changed}), 200


@admin_bp.route("/admin/audit", methods=["GET"], strict_slashes=False)
@admin_bp.route("/admin/v1/audit", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_audit(admin_user):
    query = AuditLog.query.order_by(AuditLog.created_at.desc())
    result = _page(query, lambda entry: entry.to_dict())
    if not result:
        return jsonify({"status": "error", "message": "Invalid pagination."}), 400
    return jsonify({"status": "success", "audit": result["items"], "pagination": result["pagination"]}), 200


@admin_bp.route("/admin/v1/capabilities", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_capabilities(admin_user):
    return jsonify({"status": "success", "api_version": "v1", "capabilities": {
        "users": True, "organizations": True, "provider_configuration": True,
        "feature_flags": True, "branding_text": True, "branding_asset_upload": "NOT_CONFIGURED",
        "billing": True, "billing_ledger": True, "payment_events": True,
        "rag_storage_status": True, "rag_admin_inspection": True,
        "workflow_administration": True, "admin_session": True, "audit": True,
        "image": "NOT_CONFIGURED", "video": "NOT_CONFIGURED", "training": "NOT_SUPPORTED",
        "deployment_execution": "NOT_SUPPORTED",
    }}), 200


@admin_bp.route("/admin/v1/release", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_release_metadata(admin_user):
    try:
        migration = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:
        db.session.rollback()
        migration = "UNAVAILABLE"
    return jsonify({"status": "success", "release": {
        "application": "ISOLDE", "api_version": "v1",
        "application_version": current_app.config.get("APP_VERSION") or os.getenv("APP_VERSION") or "UNSPECIFIED",
        "migration_version": migration,
        "deployment_updates": "NOT_SUPPORTED",
    }}), 200


@admin_bp.route("/admin/v1/projects", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_projects(admin_user):
    query = Project.query.join(Workspace).order_by(Project.created_at.desc())
    shares = OrganizationProject.query.all()
    shares_by_project = {}
    for share in shares:
        shares_by_project.setdefault(share.project_id, []).append({
            "organization_id": share.org_id, "access_level": share.access_level,
        })
    result = _page(query, lambda project: {
        "id": project.id, "name": project.name, "workspace_id": project.workspace_id,
        "owner_id": project.workspace.user_id, "status": project.status,
        "organization_shares": shares_by_project.get(project.id, []),
    })
    if not result:
        return jsonify({"status": "error", "message": "Invalid pagination."}), 400
    return jsonify({"status": "success", "projects": result["items"], "pagination": result["pagination"]}), 200


@admin_bp.route("/admin/v1/rag/documents", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_rag_documents(admin_user):
    query = RAGDocument.query.order_by(RAGDocument.created_at.desc())
    user_id = str(request.args.get("user_id") or "").strip()
    if user_id:
        if len(user_id) != 36:
            return jsonify({"status": "error", "message": "Invalid user filter."}), 400
        query = query.filter_by(user_id=user_id)
    result = _page(query, lambda item: {
        "id": item.id, "user_id": item.user_id, "filename": item.filename,
        "chunk_count": item.chunk_count, "created_at": item.created_at.isoformat(),
    })
    if not result:
        return jsonify({"status": "error", "message": "Invalid pagination."}), 400
    return jsonify({"status": "success", "documents": result["items"], "pagination": result["pagination"]}), 200


@admin_bp.route("/admin/v1/rag/documents/<document_id>", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_rag_document(admin_user, document_id):
    document = db.session.get(RAGDocument, document_id)
    if not document:
        return jsonify({"status": "error", "message": "Document not found."}), 404
    chunks = RAGChunk.query.filter_by(document_id=document.id).all()
    providers = sorted({item.embedding_provider for item in chunks if item.embedding_provider})
    models = sorted({item.embedding_model for item in chunks if item.embedding_model})
    dimensions = sorted({item.embedding_dimension for item in chunks})
    return jsonify({"status": "success", "document": {
        "id": document.id, "user_id": document.user_id, "filename": document.filename,
        "chunk_count": document.chunk_count, "stored_chunks": len(chunks),
        "embedding_providers": providers, "embedding_models": models,
        "embedding_dimensions": dimensions,
        "created_at": document.created_at.isoformat(),
    }}), 200


@admin_bp.route("/admin/v1/workflows", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_workflows(admin_user):
    query = Workflow.query.order_by(Workflow.created_at.desc())
    workspace_id = request.args.get("workspace_id")
    if workspace_id is not None:
        try:
            workspace_id = int(workspace_id)
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "Invalid workspace filter."}), 400
        query = query.filter_by(workspace_id=workspace_id)
    result = _page(query, lambda item: {
        **item.to_dict(),
        "execution_count": WorkflowExecution.query.filter_by(workflow_id=item.id).count(),
        "execution_capability": "NOT_SUPPORTED",
    })
    if not result:
        return jsonify({"status": "error", "message": "Invalid pagination."}), 400
    return jsonify({"status": "success", "workflows": result["items"], "pagination": result["pagination"]}), 200


@admin_bp.route("/admin/v1/workflows/<int:workflow_id>", methods=["GET", "PATCH", "DELETE"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_workflow(admin_user, workflow_id):
    workflow = db.session.get(Workflow, workflow_id)
    if not workflow:
        return jsonify({"status": "error", "message": "Workflow not found."}), 404
    if request.method == "GET":
        executions = WorkflowExecution.query.filter_by(workflow_id=workflow.id).order_by(WorkflowExecution.started_at.desc()).limit(50).all()
        return jsonify({"status": "success", "workflow": {
            **workflow.to_dict(), "execution_capability": "NOT_SUPPORTED",
            "executions": [{
                "id": item.id, "status": item.status, "started_at": item.started_at.isoformat(),
                "completed_at": item.completed_at.isoformat() if item.completed_at else None,
                "execution_time_ms": item.execution_time_ms,
            } for item in executions],
        }}), 200
    if request.method == "PATCH":
        data = request.get_json(silent=True) or {}
        if set(data) - {"is_active"} or not isinstance(data.get("is_active"), bool):
            return jsonify({"status": "error", "message": "Only is_active may be updated."}), 400
        workflow.is_active = data["is_active"]
        _audit(admin_user, "ADMIN_WORKFLOW_STATUS", {"workflow_id": workflow.id, "is_active": workflow.is_active})
        db.session.commit()
        return jsonify({"status": "success", "workflow": workflow.to_dict()}), 200
    _audit(admin_user, "ADMIN_WORKFLOW_DELETE", {"workflow_id": workflow.id})
    db.session.delete(workflow)
    db.session.commit()
    return jsonify({"status": "success", "deleted": True}), 200


@admin_bp.route("/admin/v1/organizations/<int:org_id>", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_organization_detail(admin_user, org_id):
    organization = db.session.get(Organization, org_id)
    if not organization:
        return jsonify({"status": "error", "message": "Organization not found."}), 404
    members = OrganizationMember.query.filter_by(org_id=org_id).all()
    roles = {role.id: role for role in OrganizationRole.query.filter_by(org_id=org_id).all()}
    projects = OrganizationProject.query.filter_by(org_id=org_id).all()
    return jsonify({"status": "success", "organization": {
        **organization.to_dict(),
        "members": [{
            "id": member.id, "user_id": member.user_id, "status": member.status,
            "role": roles[member.role_id].name if member.role_id in roles else None,
        } for member in members],
        "projects": [{"project_id": item.project_id, "access_level": item.access_level} for item in projects],
        "policy": (OrganizationPolicy.query.filter_by(org_id=org_id).first() or OrganizationPolicy(org_id=org_id)).to_dict(),
    }}), 200


@admin_bp.route("/admin/v1/users/<user_id>/sessions", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_user_sessions(admin_user, user_id):
    if not db.session.get(User, user_id):
        return jsonify({"status": "error", "message": "User not found."}), 404
    sessions = AuthSession.query.filter_by(user_id=user_id).order_by(AuthSession.created_at.desc()).all()
    return jsonify({"status": "success", "sessions": [_admin_session_payload(item) for item in sessions]}), 200


@admin_bp.route("/admin/v1/session", methods=["GET", "DELETE"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_current_session(admin_user):
    """Expose and revoke only the admin's current session, never its JWT."""
    session_id = str(get_jwt().get("sid") or "")
    session = db.session.get(AuthSession, session_id) if session_id else None
    if not session or session.user_id != str(admin_user.id):
        return jsonify({"status": "error", "message": "Active session not found."}), 401
    if request.method == "GET":
        return jsonify({"status": "success", "session": _admin_session_payload(session)}), 200
    if session.revoked_at is None:
        session.revoked_at = utcnow()
        _audit(admin_user, "ADMIN_CURRENT_SESSION_REVOKED", {"session_id": session.id})
        db.session.commit()
    return jsonify({"status": "success", "revoked": True}), 200


@admin_bp.route("/admin/v1/users/<user_id>/sessions/revoke-all", methods=["POST"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_revoke_user_sessions(admin_user, user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found."}), 404
    if user.id == admin_user.id:
        return jsonify({"status": "error", "message": "Use the normal logout-all flow for your own sessions."}), 409
    now = utcnow()
    count = AuthSession.query.filter_by(user_id=user_id, revoked_at=None).update({"revoked_at": now})
    _audit(admin_user, "ADMIN_USER_SESSIONS_REVOKED", {"target_user_id": user_id, "count": count})
    db.session.commit()
    return jsonify({"status": "success", "revoked_sessions": count}), 200


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
@admin_bp.route("/admin/v1/dashboard", methods=["GET"], strict_slashes=False)
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
@admin_bp.route("/admin/v1/organizations", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_tenants(admin_user):
    query = Organization.query.order_by(Organization.created_at.desc())
    result = _page(query, lambda org: {
        **org.to_dict(),
        "member_count": OrganizationMember.query.filter_by(org_id=org.id).count(),
        "policy": (OrganizationPolicy.query.filter_by(org_id=org.id).first() or OrganizationPolicy(org_id=org.id)).to_dict(),
    })
    if not result:
        return jsonify({"status": "error", "message": "Invalid pagination."}), 400
    return jsonify({"status": "success", "tenants": result["items"], "pagination": result["pagination"]}), 200


@admin_bp.route("/admin/billing-summary", methods=["GET"], strict_slashes=False)
@admin_bp.route("/admin/v1/billing/summary", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_billing_summary(admin_user):
    return jsonify({"status": "success", "billing": {
        "subscriptions": Subscription.query.count(),
        "invoices": Invoice.query.count(),
        "recorded_credits": db.session.query(db.func.coalesce(db.func.sum(CreditBalance.credits), 0)).scalar(),
        "provider": "Not configured" if not current_app.config.get("PAYMENT_PROVIDER") else current_app.config["PAYMENT_PROVIDER"],
    }}), 200


@admin_bp.route("/admin/billing/subscriptions", methods=["GET"], strict_slashes=False)
@admin_bp.route("/admin/v1/billing/subscriptions", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_subscriptions(admin_user):
    query = Subscription.query.order_by(Subscription.updated_at.desc())
    user_id = str(request.args.get("user_id") or "").strip()
    if user_id:
        if len(user_id) > 100:
            return jsonify({"status": "error", "message": "Invalid user filter."}), 400
        query = query.filter_by(user_id=user_id)
    result = _page(query, lambda item: item.to_dict())
    if not result:
        return jsonify({"status": "error", "message": "Invalid pagination."}), 400
    return jsonify({"status": "success", "subscriptions": result["items"], "pagination": result["pagination"]}), 200


@admin_bp.route("/admin/v1/billing/ledger", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_credit_ledger(admin_user):
    query = CreditLedger.query.order_by(CreditLedger.created_at.desc())
    user_id = str(request.args.get("user_id") or "").strip()
    if user_id:
        if len(user_id) > 100:
            return jsonify({"status": "error", "message": "Invalid user filter."}), 400
        query = query.filter_by(user_id=user_id)
    result = _page(query, lambda item: {
        "id": item.id, "user_id": item.user_id, "credits_delta": item.credits_delta,
        "source": item.source, "provider_tokens": item.provider_tokens,
        "created_at": item.created_at.isoformat(),
    })
    if not result:
        return jsonify({"status": "error", "message": "Invalid pagination."}), 400
    return jsonify({"status": "success", "ledger": result["items"], "pagination": result["pagination"]}), 200


@admin_bp.route("/admin/v1/billing/events", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_payment_events(admin_user):
    query = PaymentEvent.query.order_by(PaymentEvent.processed_at.desc())
    provider = str(request.args.get("provider") or "").strip().lower()
    if provider:
        if len(provider) > 32 or not provider.replace("_", "").isalnum():
            return jsonify({"status": "error", "message": "Invalid provider filter."}), 400
        query = query.filter_by(provider=provider)
    result = _page(query, lambda item: {
        "id": item.id, "provider": item.provider, "event_type": item.event_type,
        "processed_at": item.processed_at.isoformat(),
    })
    if not result:
        return jsonify({"status": "error", "message": "Invalid pagination."}), 400
    return jsonify({"status": "success", "events": result["items"], "pagination": result["pagination"]}), 200


@admin_bp.route("/admin/v1/billing/invoices", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_invoices(admin_user):
    query = Invoice.query.order_by(Invoice.created_at.desc())
    user_id = str(request.args.get("user_id") or "").strip()
    if user_id:
        if len(user_id) > 100:
            return jsonify({"status": "error", "message": "Invalid user filter."}), 400
        query = query.filter_by(user_id=user_id)
    result = _page(query, lambda item: item.to_dict())
    if not result:
        return jsonify({"status": "error", "message": "Invalid pagination."}), 400
    return jsonify({"status": "success", "invoices": result["items"], "pagination": result["pagination"]}), 200


@admin_bp.route("/admin/v1/billing/invoices/<int:invoice_id>/refund", methods=["POST"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_refund_invoice(admin_user, invoice_id):
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        return jsonify({"status": "error", "message": "Invoice not found."}), 404
    if invoice.status == "refunded":
        return jsonify({"status": "success", "invoice": invoice.to_dict(), "idempotent": True}), 200
    if invoice.status != "paid" or not invoice.provider_payment_id:
        return jsonify({"status": "error", "message": "Invoice is not refundable."}), 409
    try:
        from app.services.payment_service import PaymentNotConfigured, get_payment_provider
        result = get_payment_provider().refund_payment(invoice.provider_payment_id, f"admin-invoice-refund-{invoice.id}")
    except PaymentNotConfigured:
        return jsonify({"status": "error", "capability": "NOT_CONFIGURED", "message": "Payment provider is not configured."}), 503
    except Exception:
        current_app.logger.exception("Admin payment refund failed.")
        return jsonify({"status": "error", "message": "Payment refund failed."}), 502
    invoice.status = "refunded" if result.get("status") in {"succeeded", "pending"} else "refund_pending"
    _audit(admin_user, "ADMIN_INVOICE_REFUND", {"invoice_id": invoice.id, "user_id": invoice.user_id})
    db.session.commit()
    return jsonify({"status": "success", "invoice": invoice.to_dict()}), 200


@admin_bp.route("/admin/provider-status", methods=["GET"], strict_slashes=False)
@admin_bp.route("/admin/v1/providers/status", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_provider_status(admin_user):
    from app.services.provider_router import ProviderManager
    manager = ProviderManager()
    providers = {}
    for name in sorted(SUPPORTED_PROVIDERS):
        try:
            manager.get_api_key_for_provider(name)
            providers[name] = True
        except RuntimeError:
            providers[name] = False
    return jsonify({"status": "success", "providers": {
        name: "Configured" if configured else "Not configured"
        for name, configured in providers.items()
    }}), 200


@admin_bp.route("/admin/operations", methods=["GET"], strict_slashes=False)
@admin_bp.route("/admin/v1/operations", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_operations(admin_user):
    from app.services.health_service import health_service
    health = health_service.check_system_health()
    return jsonify({"status": "success", "operations": {
        "health": health,
        "storage_backend": current_app.config.get("STORAGE_BACKEND", "local"),
        "rag_backend": current_app.config.get("RAG_STORAGE_BACKEND", "database"),
        "rag_documents": RAGDocument.query.count(),
        "uploaded_files": UploadedFile.query.count(),
        "failed_rag_documents": RAGDocument.query.filter(RAGDocument.chunk_count == 0).count(),
        "rate_limit_storage": "Redis" if current_app.config.get("RATELIMIT_STORAGE_URI", "").startswith("redis") else "Not configured",
        "logs": "File logging enabled" if current_app.config.get("LOG_TO_FILE") else "Application logger",
    }}), 200


@admin_bp.route("/admin/tenants/<int:org_id>", methods=["PATCH"], strict_slashes=False)
@admin_bp.route("/admin/v1/organizations/<int:org_id>", methods=["PATCH"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_update_tenant(admin_user, org_id):
    organization = db.session.get(Organization, org_id)
    if not organization:
        return jsonify({"status": "error", "message": "Tenant not found."}), 404
    status = str((request.get_json(silent=True) or {}).get("status") or "")
    if status not in {"Active", "Suspended", "Archived"}:
        return jsonify({"status": "error", "message": "Invalid tenant status."}), 400
    organization.status = status
    _audit(admin_user, "ADMIN_TENANT_STATUS", {"tenant_id": org_id, "status": status})
    db.session.commit()
    log_event(current_app, "ADMIN_TENANT_STATUS", f"tenant={org_id} status={status}", admin_user.id)
    return jsonify({"status": "success", "tenant": organization.to_dict()}), 200


@admin_bp.route("/admin/tenants/<int:org_id>/policy", methods=["PATCH"], strict_slashes=False)
@admin_bp.route("/admin/v1/organizations/<int:org_id>/policy", methods=["PATCH"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_update_tenant_policy(admin_user, org_id):
    if not db.session.get(Organization, org_id):
        return jsonify({"status": "error", "message": "Tenant not found."}), 404
    policy = OrganizationPolicy.query.filter_by(org_id=org_id).first()
    if not policy:
        policy = OrganizationPolicy(org_id=org_id)
        db.session.add(policy)
    data = request.get_json(silent=True) or {}
    if "allowed_providers" in data:
        providers = data["allowed_providers"]
        if not isinstance(providers, list) or not providers:
            return jsonify({"status": "error", "message": "At least one allowed provider is required."}), 400
        normalized = sorted({str(item).strip().lower() for item in providers})
        if not set(normalized).issubset(SUPPORTED_PROVIDERS):
            return jsonify({"status": "error", "message": "Unsupported provider in policy."}), 400
        import json
        policy.allowed_providers = json.dumps(normalized)
    if "billing_enabled" in data:
        if not isinstance(data["billing_enabled"], bool):
            return jsonify({"status": "error", "message": "billing_enabled must be a boolean."}), 400
        policy.billing_enabled = data["billing_enabled"]
    _audit(admin_user, "ADMIN_TENANT_POLICY", {"tenant_id": org_id})
    db.session.commit()
    log_event(current_app, "ADMIN_TENANT_POLICY", f"tenant={org_id}", admin_user.id)
    return jsonify({"status": "success", "policy": policy.to_dict()}), 200


@admin_bp.route("/admin/billing/subscriptions/<user_id>/cancel", methods=["POST"], strict_slashes=False)
@admin_bp.route("/admin/v1/billing/subscriptions/<user_id>/cancel", methods=["POST"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_cancel_subscription(admin_user, user_id):
    subscription = Subscription.query.filter_by(user_id=user_id).first()
    if not subscription or not subscription.provider_subscription_id:
        return jsonify({"status": "error", "message": "Cancellable subscription not found."}), 404
    try:
        from app.services.payment_service import get_payment_provider
        result = get_payment_provider().cancel_subscription(subscription.provider_subscription_id)
    except Exception:
        current_app.logger.exception("Admin subscription cancellation failed.")
        return jsonify({"status": "error", "message": "Subscription cancellation failed or is not configured."}), 503
    subscription.status = str(result.get("status") or "cancellation_pending")
    _audit(admin_user, "ADMIN_SUBSCRIPTION_CANCEL", {"target_user_id": user_id})
    db.session.commit()
    return jsonify({"status": "success", "subscription": subscription.to_dict()}), 200


@admin_bp.route("/admin/operations/log-summary", methods=["GET"], strict_slashes=False)
@admin_bp.route("/admin/v1/operations/log-summary", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def admin_log_summary(admin_user):
    counts = {"error": 0, "warning": 0}
    if not current_app.config.get("LOG_TO_FILE"):
        return jsonify({"status": "success", "summary": counts, "source": "Not configured"}), 200
    log_dir = current_app.config.get("LOG_DIR", "")
    try:
        candidates = [os.path.join(log_dir, name) for name in os.listdir(log_dir) if name.endswith(".log")]
        if not candidates:
            return jsonify({"status": "success", "summary": counts, "source": "No log files"}), 200
        latest = max(candidates, key=os.path.getmtime)
        with open(latest, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()[-1000:]
        counts["error"] = sum("ERROR" in line.upper() for line in lines)
        counts["warning"] = sum("WARNING" in line.upper() for line in lines)
        return jsonify({"status": "success", "summary": counts, "source": "application log"}), 200
    except OSError:
        current_app.logger.exception("Admin log summary could not be read.")
        return jsonify({"status": "error", "message": "Log summary unavailable."}), 503


# ---------------------------------------------------------------------------
# 3. USER MANAGEMENT
# ---------------------------------------------------------------------------

@admin_bp.route("/admin/users", methods=["GET"], strict_slashes=False)
@admin_bp.route("/admin/v1/users", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def list_users(admin_user):
    query = User.query.order_by(User.created_at.desc())
    for name in ("role", "status"):
        value = str(request.args.get(name) or "").strip()
        if value:
            if len(value) > 32:
                return jsonify({"status": "error", "message": f"Invalid {name} filter."}), 400
            query = query.filter(getattr(User, name) == value)
    email = str(request.args.get("email") or "").strip().lower()
    if email:
        if len(email) > 180:
            return jsonify({"status": "error", "message": "Invalid email filter."}), 400
        query = query.filter(User.email.ilike(f"%{email}%"))
    result = _page(query, lambda user: user.to_dict())
    if not result:
        return jsonify({"status": "error", "message": "Invalid pagination."}), 400
    return jsonify({
        "status": "success",
        "users": result["items"], "pagination": result["pagination"],
    }), 200


@admin_bp.route("/admin/users", methods=["POST"], strict_slashes=False)
@admin_bp.route("/admin/v1/users", methods=["POST"], strict_slashes=False)
@jwt_required()
@admin_required
def create_user(admin_user):
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()
    email = str(data.get("email") or "").strip().lower()

    if not name or not is_valid_email(email):
        return jsonify({"status": "error", "message": "A name and valid email are required."}), 400

    existing = User.query.filter_by(email=email).first()
    if existing:
        return jsonify({"status": "error", "message": "A user with this email already exists."}), 400

    if not all(current_app.config.get(key) for key in (
        "MAIL_SERVER", "MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_DEFAULT_SENDER"
    )):
        return jsonify({
            "status": "error", "message": "User invitations require configured email delivery."
        }), 503

    temp_password = ''.join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(16)
    )

    try:
        user = User(name=name, email=email)
        user.set_password(temp_password)
        db.session.add(user)
        db.session.flush()
        from app.routes.auth_routes import _deliver_auth_email, _issue_user_token
        reset_token = _issue_user_token(
            user, "password_reset", current_app.config["PASSWORD_RESET_TOKEN_MINUTES"]
        )
        _audit(admin_user, "ADMIN_USER_UPDATE", {"target_user_id": user.id, "fields": sorted(data)})
        db.session.commit()
        _deliver_auth_email(user.email, "Set your Isolde password", "/login.html", reset_token)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin user create error: {e}")
        return jsonify({"status": "error", "message": "Failed to create user."}), 500

    return jsonify({
        "status": "success",
        "message": "User created. Password setup instructions were issued by email.",
        "user": user.to_dict(),
    }), 201


@admin_bp.route("/admin/users/<user_id>", methods=["GET"], strict_slashes=False)
@admin_bp.route("/admin/v1/users/<user_id>", methods=["GET"], strict_slashes=False)
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
@admin_bp.route("/admin/v1/users/<user_id>", methods=["PATCH"], strict_slashes=False)
@jwt_required()
@admin_required
def update_user(admin_user, user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found."}), 404
    data = request.get_json(silent=True) or {}

    if user.role in ADMIN_ROLES and admin_user.role != "Super Admin" and user.id != admin_user.id:
        return jsonify({"status": "error", "message": "Only Super Admin can modify administrator accounts."}), 403

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
            if data["status"] not in {"Active", "Suspended", "Disabled"}:
                return jsonify({"status": "error", "message": "Invalid account status."}), 400
            if user.id == admin_user.id and data["status"] != "Active":
                return jsonify({"status": "error", "message": "You cannot suspend your own account."}), 409
            user.status = data["status"]

        if "name" in data:
            user.name = data["name"]

        _audit(admin_user, "ADMIN_USER_UPDATE", {"target_user_id": user.id, "fields": sorted(data)})
        db.session.commit()
        log_event(current_app, "ADMIN_USER_UPDATE", f"target={user.id}", admin_user.id)

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin user update error: {e}")
        return jsonify({
            "status": "error",
            "message": "Failed to update user."
        }), 500

    return jsonify({"status": "success", "user": user.to_dict()}), 200


@admin_bp.route("/admin/users/<user_id>", methods=["DELETE"], strict_slashes=False)
@admin_bp.route("/admin/v1/users/<user_id>", methods=["DELETE"], strict_slashes=False)
@jwt_required()
@admin_required
def delete_user(admin_user, user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found."}), 404

    if user.id == admin_user.id:
        return jsonify({"status": "error", "message": "You cannot delete your own account."}), 400

    try:
        _audit(admin_user, "ADMIN_USER_DELETE", {"target_user_id": user.id})
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
@admin_bp.route("/admin/v1/conversations", methods=["GET"], strict_slashes=False)
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
@admin_bp.route("/admin/v1/conversations/<conversation_id>", methods=["GET"], strict_slashes=False)
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
@admin_bp.route("/admin/v1/conversations/<conversation_id>", methods=["DELETE"], strict_slashes=False)
@jwt_required()
@admin_required
def delete_conversation(admin_user, conversation_id):
    convo = db.session.get(Conversation, conversation_id)
    if not convo:
        return jsonify({"status": "error", "message": "Conversation not found."}), 404

    try:
        _audit(admin_user, "ADMIN_CONVERSATION_DELETE", {"conversation_id": conversation_id})
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
@admin_bp.route("/admin/v1/providers/settings", methods=["GET"], strict_slashes=False)
@jwt_required()
@admin_required
def list_settings(admin_user):
    settings = Setting.query.all()
    return jsonify({
        "status": "success",
        "settings": [{
            "key": setting.key,
            "value": "********" if _is_secret_setting(setting.key) else setting.value,
        } for setting in settings],
    }), 200


@admin_bp.route("/admin/settings", methods=["POST"], strict_slashes=False)
@admin_bp.route("/admin/v1/providers/settings", methods=["POST"], strict_slashes=False)
@jwt_required()
@admin_required
def save_setting(admin_user):
    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    value = data.get("value", "")

    if not key:
        return jsonify({"status": "error", "message": "Setting key is required."}), 400

    if key not in PROVIDER_SETTING_KEYS:
        return jsonify({
            "status": "error",
            "message": "Unsupported setting key. Use the versioned configuration APIs for product settings.",
        }), 400

    if _is_secret_setting(key):
        if not isinstance(value, str) or not value.strip() or value == "********":
            return jsonify({"status": "error", "message": "A new secret value is required."}), 400
        from app.services.security_service import SecurityService
        value = "enc:" + SecurityService().encrypt_data(value.strip())

    try:
        existing = Setting.query.filter_by(key=key).first()
        if existing:
            existing.value = value
        else:
            new_setting = Setting(key=key, value=value)
            db.session.add(new_setting)
        _audit(admin_user, "ADMIN_PROVIDER_SETTING", {"key": key, "secret": _is_secret_setting(key)})
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin setting save error: {e}")
        return jsonify({"status": "error", "message": "Failed to save setting."}), 500

    return jsonify({"status": "success", "message": f"Setting '{key}' saved."}), 200


@admin_bp.route("/admin/settings/<setting_key>", methods=["DELETE"], strict_slashes=False)
@admin_bp.route("/admin/v1/providers/settings/<setting_key>", methods=["DELETE"], strict_slashes=False)
@jwt_required()
@admin_required
def delete_setting(admin_user, setting_key):
    setting = Setting.query.filter_by(key=setting_key).first()
    if not setting:
        return jsonify({"status": "error", "message": "Setting not found."}), 404

    try:
        db.session.delete(setting)
        _audit(admin_user, "ADMIN_PROVIDER_SETTING_DELETE", {"key": setting_key})
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
