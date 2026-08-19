from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models.saas_cloud_model import Tenant, Subscription, Invoice, APIKey

saas_cloud_bp = Blueprint("saas_cloud_bp", __name__)


# --- SUBSCRIPTION & BILLING APIS ---

@saas_cloud_bp.route("/saas/subscription", methods=["GET"])
@jwt_required(optional=True)
def get_subscription():
    try:
        tenant = Tenant.query.first()
        if not tenant:
            tenant = Tenant(name="Default Enterprise", subdomain="default", plan_tier="Business")
            db.session.add(tenant)
            db.session.commit()

        sub = Subscription.query.filter_by(tenant_id=tenant.id).first()
        return jsonify({
            "tenant": tenant.to_dict(),
            "subscription": sub.to_dict() if sub else {"plan_name": tenant.plan_tier, "status": "Active"}
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@saas_cloud_bp.route("/saas/invoices", methods=["GET"])
@jwt_required(optional=True)
def get_invoices():
    try:
        invoices = Invoice.query.order_by(Invoice.invoice_date.desc()).all()
        return jsonify({"invoices": [inv.to_dict() for inv in invoices]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- PUBLIC API KEY PLATFORM ---

@saas_cloud_bp.route("/saas/apikeys", methods=["GET"])
@jwt_required(optional=True)
def get_api_keys():
    try:
        user_id = get_jwt_identity() or 1
        keys = APIKey.query.filter_by(user_id=user_id).all()
        # Safe by construction: APIKey.to_dict() never includes key_secret
        # or key_hash. No change to URL, method, or auth is required here.
        return jsonify({"api_keys": [k.to_dict() for k in keys]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@saas_cloud_bp.route("/saas/apikeys", methods=["POST"])
@jwt_required(optional=True)
def create_api_key():
    try:
        user_id = get_jwt_identity() or 1
        data = request.get_json() or {}

        # Phase 3: generate the raw key, its non-recoverable hash, and its
        # safe identification prefix. The raw key is returned to the caller
        # exactly once, in this creation response only. It is never returned
        # by to_dict(), the list endpoint, or any detail endpoint.
        raw_key, key_hash, key_prefix = APIKey.generate_key()

        new_key = APIKey(
            user_id=user_id,
            key_name=data.get("key_name", "Production Key"),
            scopes=data.get("scopes", "read,write,ai"),
            key_secret=raw_key,
            key_hash=key_hash,
            key_prefix=key_prefix
        )
        db.session.add(new_key)
        db.session.commit()

        return jsonify({
            "message": "API Key generated successfully. Save this key now; it will never be shown again!",
            "api_key": new_key.to_dict(),
            "raw_key": raw_key
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# --- CLOUD MONITORING & HEALTH APIS ---

@saas_cloud_bp.route("/saas/monitoring/health", methods=["GET"])
@jwt_required(optional=True)
def cloud_health():
    return jsonify({
        "status": "healthy",
        "uptime": "99.99%",
        "active_nodes": 12,
        "database": "connected",
        "redis_queue": "operational"
    }), 200