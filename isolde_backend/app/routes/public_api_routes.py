"""Minimal versioned ISOLDE API contracts backed by existing services."""
from flask import Blueprint, current_app, g, jsonify, request

from app.routes.unified_chat_engine import unified_auth_required
from app.services.api_key_service import track_api_usage
from app.services.rag_service import search as rag_search
from app.services.research_service import ResearchUnavailable, build_result, research
from app.utils.validators import is_non_empty, sanitize_text


public_api_bp = Blueprint("public_api_bp", __name__)


def _error(code, message, status):
    return jsonify({
        "status": "error", "error": {"code": code, "message": message},
        "request_id": getattr(g, "request_id", None),
    }), status


def _track_request():
    key = getattr(g, "api_key", None)
    if key:
        track_api_usage(key.key_hash)


@public_api_bp.route("/v1/research", methods=["POST"], strict_slashes=False)
@unified_auth_required("read")
def versioned_research():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not is_non_empty(data.get("question")):
        return _error("VALIDATION_ERROR", "question is required.", 400)
    question = sanitize_text(data["question"])
    try:
        _plan, sources = research(question, requested=True)
        result = build_result(question, True, sources)
    except ResearchUnavailable:
        return _error("RESEARCH_PROVIDER_NOT_CONFIGURED", "Web research is not configured.", 503)
    except Exception:
        current_app.logger.error("Versioned research failed category=RESEARCH_UNAVAILABLE")
        return _error("RESEARCH_UNAVAILABLE", "Web research is temporarily unavailable.", 502)
    _track_request()
    return jsonify({"status": "success", "data": result, "request_id": getattr(g, "request_id", None)}), 200


@public_api_bp.route("/v1/rag/query", methods=["POST"], strict_slashes=False)
@unified_auth_required("read")
def versioned_rag_query():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not is_non_empty(data.get("query")):
        return _error("VALIDATION_ERROR", "query is required.", 400)
    try:
        top_k = int(data.get("top_k", 4))
    except (TypeError, ValueError):
        return _error("VALIDATION_ERROR", "top_k must be an integer from 1 to 10.", 400)
    if top_k < 1 or top_k > 10:
        return _error("VALIDATION_ERROR", "top_k must be an integer from 1 to 10.", 400)
    chunks = rag_search(sanitize_text(data["query"]), top_k=top_k, user_id=str(g.auth_user_id))
    _track_request()
    return jsonify({
        "status": "success", "data": {"chunks": chunks},
        "request_id": getattr(g, "request_id", None),
    }), 200
