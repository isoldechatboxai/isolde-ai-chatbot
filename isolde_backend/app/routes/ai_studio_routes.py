from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.ai_studio_model import CustomModel, PlaygroundRun
from app.models.billing_model import CreditBalance
from app.models.user import User
from app.services.credit_service import deduct_authoritative_usage
from app.services.provider_router import generate_reply_with_usage

ai_studio_bp = Blueprint("ai_studio_bp", __name__)


@ai_studio_bp.route("/ai-studio/models", methods=["GET"])
@jwt_required()
def list_custom_models():
    try:
        user_id = str(get_jwt_identity())
        models = CustomModel.query.filter_by(user_id=user_id).order_by(CustomModel.created_at.desc()).all()
        items = []
        for model in models:
            item = model.to_dict()
            item["status"] = "NOT_SUPPORTED"
            items.append(item)
        return jsonify({"models": items, "capability": "NOT_SUPPORTED"}), 200
    except Exception:
        current_app.logger.exception("AI Studio model listing failed.")
        return jsonify({"error": "AI Studio models are unavailable."}), 500


@ai_studio_bp.route("/ai-studio/models", methods=["POST"])
@jwt_required()
def create_custom_model():
    return jsonify({
        "status": "NOT_SUPPORTED",
        "error": "Fine-tuning is not configured. Configure a supported training provider before creating models."
    }), 501


@ai_studio_bp.route("/ai-studio/playground/test", methods=["POST"])
@jwt_required()
def test_playground_prompt():
    try:
        user_id = str(get_jwt_identity())
        data = request.get_json() or {}
        model_id = str(data.get("model_id") or "default")
        prompt = data.get("prompt", "")
        parameters = data.get("parameters", {})

        if not isinstance(prompt, str) or not prompt.strip():
            return jsonify({"error": "Prompt is required."}), 400
        if model_id != "default":
            return jsonify({
                "status": "NOT_SUPPORTED",
                "error": "Custom model execution is not supported. Use the configured default provider."
            }), 422
        if parameters not in ({}, None):
            return jsonify({
                "status": "NOT_SUPPORTED",
                "error": "Custom playground parameters are not supported by the current provider contract."
            }), 422
        balance = CreditBalance.query.filter_by(user_id=user_id).first()
        if balance and balance.credits <= 0:
            return jsonify({"error": "AI credits are exhausted."}), 402

        provider_result = generate_reply_with_usage(prompt.strip())
        output = provider_result.text

        run = PlaygroundRun(
            model_uid=model_id,
            user_id=user_id,
            prompt=prompt,
            output=output,
            parameters="{}",
            tokens_used=provider_result.tokens_used,
        )
        db.session.add(run)
        db.session.flush()
        if provider_result.tokens_used is not None:
            deduct_authoritative_usage(
                user_id, provider_result.tokens_used,
                f"ai-studio:{run.id}:{provider_result.provider}",
                current_app.config.get("CREDIT_TOKENS_PER_UNIT", 1000),
            )
            user = db.session.get(User, user_id)
            if user:
                user.tokens_used = (user.tokens_used or 0) + provider_result.tokens_used
        db.session.commit()

        return jsonify({
            "status": "success",
            "model_id": model_id,
            "prompt": prompt,
            "output": output,
            "provider": provider_result.provider,
            "tokens_used": provider_result.tokens_used,
            "usage": {
                "input_tokens": provider_result.input_tokens,
                "output_tokens": provider_result.output_tokens,
                "total_tokens": provider_result.tokens_used,
            } if provider_result.tokens_used is not None else "Usage unavailable"
        }), 200
    except RuntimeError:
        db.session.rollback()
        return jsonify({"error": "AI provider is unavailable or not configured."}), 503
    except Exception:
        db.session.rollback()
        current_app.logger.exception("AI Studio playground execution failed.")
        return jsonify({"error": "AI Studio execution failed."}), 500


@ai_studio_bp.route("/ai-studio/playground/history", methods=["GET"])
@jwt_required()
def playground_history():
    try:
        user_id = str(get_jwt_identity())
        runs = PlaygroundRun.query.filter_by(user_id=user_id).order_by(PlaygroundRun.created_at.desc()).limit(50).all()
        return jsonify({"runs": [r.to_dict() for r in runs]}), 200
    except Exception:
        current_app.logger.exception("AI Studio history lookup failed.")
        return jsonify({"error": "AI Studio history is unavailable."}), 500
