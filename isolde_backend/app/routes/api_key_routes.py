# app/routes/api_key_routes.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta

from app.services.api_key_service import (
    create_api_key, 
    list_user_keys, 
    revoke_api_key
)

api_key_bp = Blueprint("api_key_bp", __name__)

@api_key_bp.route("/keys/generate", methods=["POST"])
@jwt_required()
def generate_key():
    """
    Endpoint for developers to generate a new API key.
    Returns the PLAINTEXT key ONCE.
    """
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    
    name = data.get("name", "Default API Key")
    permissions = data.get("permissions", "read,write")
    
    # Optional expiration in days (e.g., expires in 365 days)
    expires_in_days = data.get("expires_in_days")
    expires_at = None
    if expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=int(expires_in_days))

    try:
        raw_key, key_metadata = create_api_key(
            user_id=user_id,
            name=name,
            permissions=permissions,
            expires_at=expires_at
        )
        
        return jsonify({
            "message": "API key generated successfully. Save this key now; it will never be shown again!",
            "api_key": raw_key,
            "metadata": key_metadata
        }), 201
    except Exception as e:
        return jsonify({"error": "Failed to generate API key.", "details": str(e)}), 500

@api_key_bp.route("/keys", methods=["GET"])
@jwt_required()
def get_user_keys():
    """Lists all API keys (metadata and analytics) belonging to the authenticated user."""
    user_id = get_jwt_identity()
    try:
        keys = list_user_keys(user_id)
        return jsonify({"keys": keys}), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch API keys.", "details": str(e)}), 500

@api_key_bp.route("/keys/<int:key_id>", methods=["DELETE"])
@jwt_required()
def delete_key(key_id):
    """Revokes an API key so it can no longer be used for authentication."""
    user_id = get_jwt_identity()
    try:
        success = revoke_api_key(key_id, user_id)
        if not success:
            return jsonify({"error": "API key not found or unauthorized."}), 404
            
        return jsonify({"message": f"API key ID {key_id} has been revoked successfully."}), 200
    except Exception as e:
        return jsonify({"error": "Failed to revoke API key.", "details": str(e)}), 500