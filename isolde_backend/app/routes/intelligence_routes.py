# app/routes/intelligence_routes.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.intelligence_model import AIInsight, Recommendation, LearningProfile

intelligence_bp = Blueprint("intelligence_bp", __name__)

# --- GLOBAL SEARCH API ---
@intelligence_bp.route("/intelligence/search", methods=["GET"])
@jwt_required(optional=True)
def global_search():
    query = request.args.get("q", "").lower()
    # Cross-module mock search aggregation
    results = [
        {"type": "Document", "title": f"Project spec matching '{query}'", "snippet": "Enterprise cloud architecture guidelines..."},
        {"type": "Task", "title": f"Review pending audit for '{query}'", "status": "Open"},
        {"type": "Memory", "title": f"Cached preference on '{query}'", "snippet": "User prefers concise Python responses."}
    ] if query else []
    return jsonify({"query": query, "results": results}), 200

# --- AI INSIGHTS APIS ---
@intelligence_bp.route("/intelligence/insights", methods=["GET"])
@jwt_required(optional=True)
def get_insights():
    try:
        insights = AIInsight.query.all()
        if not insights:
            # Seed default executive insights if empty
            default_insight = AIInsight(user_id=1, category="Knowledge Gap", title="Cloud Security Documentation Missing", description="Detected 14 queries regarding OAuth2 protocols without corresponding internal docs.")
            db.session.add(default_insight)
            db.session.commit()
            insights = [default_insight]
        return jsonify({"insights": [i.to_dict() for i in insights]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- RECOMMENDATIONS APIS ---
@intelligence_bp.route("/intelligence/recommendations", methods=["GET"])
@jwt_required(optional=True)
def get_recommendations():
    try:
        recs = Recommendation.query.filter_by(is_completed=False).all()
        if not recs:
            default_rec = Recommendation(user_id=1, rec_type="Task", content="Schedule Q3 Architecture Review with DevOps Team", priority="High")
            db.session.add(default_rec)
            db.session.commit()
            recs = [default_rec]
        return jsonify({"recommendations": [r.to_dict() for r in recs]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- LEARNING PROFILE APIS ---
@intelligence_bp.route("/intelligence/profile", methods=["GET"])
@jwt_required(optional=True)
def get_learning_profile():
    try:
        user_id = get_jwt_identity() or 1
        profile = LearningProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            profile = LearningProfile(user_id=user_id, favorite_agent="Enterprise Orchestrator", preferred_workspace="Production Core")
            db.session.add(profile)
            db.session.commit()
        return jsonify({"learning_profile": profile.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500