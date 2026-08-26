# app/routes/health_routes.py

from flask import Blueprint, jsonify
from app.services.health_service import health_service

health_bp = Blueprint('health_bp', __name__, url_prefix='/api/health')

@health_bp.route('/', methods=['GET'])
def health_check():
    """
    API endpoint to check application health status, 
    database connectivity, and storage availability.
    """
    try:
        status_data = health_service.check_system_health()
        status_code = 200 if status_data.get("status") == "healthy" else 503
        
        return jsonify({
            "success": status_code == 200,
            "data": status_data
        }), status_code

    except Exception:
        return jsonify({
            "success": False,
            "error": "Health check failed."
        }), 500
