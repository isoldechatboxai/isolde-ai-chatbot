# app/routes/saas_cloud_routes.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models.saas_cloud_model import Tenant, Subscription, Invoice, APIKey

saas_cloud_bp = Blueprint("saas_cloud_bp", __name__)


# --- SUBSCRIPTION & BILLING APIS ---

@saas_cloud_bp.route("/saas/subscription", methods=["GET"])
@jwt_required()
def get_subscription():
    return jsonify({"error": "Tenant membership is not configured for this account."}), 501


@saas_cloud_bp.route("/saas/invoices", methods=["GET"])
@jwt_required()
def get_invoices():
    return jsonify({"error": "Tenant billing integration is not configured."}), 501


# --- PUBLIC API KEY PLATFORM ---

@saas_cloud_bp.route("/saas/apikeys", methods=["GET"])
@jwt_required()
def get_api_keys():
    try:
        user_id = str(get_jwt_identity())
        keys = APIKey.query.filter_by(user_id=user_id).all()
        # Safe by construction: APIKey.to_dict() never includes key_secret
        # or key_hash. No change to URL, method, or auth is required here.
        return jsonify({"api_keys": [k.to_dict() for k in keys]}), 200
    except Exception:
        current_app.logger.exception("SaaS API key listing failed.")
        return jsonify({"error": "API keys are unavailable."}), 500


@saas_cloud_bp.route("/saas/apikeys", methods=["POST"])
@jwt_required()
def create_api_key():
    try:
        user_id = str(get_jwt_identity())
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
            key_secret=None,
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
    except Exception:
        db.session.rollback()
        current_app.logger.exception("SaaS API key creation failed.")
        return jsonify({"error": "API key could not be created."}), 500


# --- CLOUD MONITORING & HEALTH APIS ---

@saas_cloud_bp.route("/saas/monitoring/health", methods=["GET"])
@jwt_required()
def cloud_health():
    from app.services.health_service import health_service
    status = health_service.check_system_health()
    return jsonify(status), 200 if status.get("status") == "healthy" else 503
