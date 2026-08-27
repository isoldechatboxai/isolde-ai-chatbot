# app/routes/intelligence_routes.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.intelligence_model import AIInsight, Recommendation, LearningProfile

intelligence_bp = Blueprint("intelligence_bp", __name__)

# --- GLOBAL SEARCH API ---
@intelligence_bp.route("/intelligence/search", methods=["GET"])
@jwt_required()
def global_search():
    query = request.args.get("q", "").lower()
    return jsonify({"query": query, "results": [], "message": "Cross-module search is not configured."}), 200

# --- AI INSIGHTS APIS ---
@intelligence_bp.route("/intelligence/insights", methods=["GET"])
@jwt_required()
def get_insights():
    try:
        insights = AIInsight.query.filter_by(user_id=str(get_jwt_identity())).all()
        return jsonify({"insights": [i.to_dict() for i in insights]}), 200
    except Exception:
        current_app.logger.exception("Insight listing failed.")
        return jsonify({"error": "Insights are unavailable."}), 500

# --- RECOMMENDATIONS APIS ---
@intelligence_bp.route("/intelligence/recommendations", methods=["GET"])
@jwt_required()
def get_recommendations():
    try:
        recs = Recommendation.query.filter_by(user_id=str(get_jwt_identity()), is_completed=False).all()
        return jsonify({"recommendations": [r.to_dict() for r in recs]}), 200
    except Exception:
        current_app.logger.exception("Recommendation listing failed.")
        return jsonify({"error": "Recommendations are unavailable."}), 500

# --- LEARNING PROFILE APIS ---
@intelligence_bp.route("/intelligence/profile", methods=["GET"])
@jwt_required()
def get_learning_profile():
    try:
        user_id = str(get_jwt_identity())
        profile = LearningProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            profile = LearningProfile(user_id=user_id)
            db.session.add(profile)
            db.session.commit()
        return jsonify({"learning_profile": profile.to_dict()}), 200
    except Exception:
        current_app.logger.exception("Learning profile lookup failed.")
        return jsonify({"error": "Learning profile is unavailable."}), 500
