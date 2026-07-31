# app/routes/analytics_routes.py

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.analytics_service import analytics_service

analytics_bp = Blueprint('analytics_bp', __name__, url_prefix='/api/analytics')

@analytics_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard_metrics():
    """
    API endpoint to fetch aggregated usage metrics, token consumption, 
    costs, and recent activity logs for the authenticated user.
    """
    try:
        user_id = get_jwt_identity()
        analytics_data = analytics_service.get_dashboard_analytics(user_id=user_id)
        
        return jsonify({
            "success": True,
            "data": analytics_data
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500