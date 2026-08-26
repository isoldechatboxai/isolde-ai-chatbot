from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.ai_studio_model import CustomModel, PlaygroundRun
from app.services.provider_router import generate_reply

ai_studio_bp = Blueprint("ai_studio_bp", __name__)


@ai_studio_bp.route("/ai-studio/models", methods=["GET"])
@jwt_required()
def list_custom_models():
    try:
        user_id = str(get_jwt_identity())
        models = CustomModel.query.filter_by(user_id=user_id).order_by(CustomModel.created_at.desc()).all()
        return jsonify({"models": [m.to_dict() for m in models]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
        model_id = data.get("model_id", "default")
        prompt = data.get("prompt", "")
        parameters = data.get("parameters", {})

        if not isinstance(prompt, str) or not prompt.strip():
            return jsonify({"error": "Prompt is required."}), 400

        output = generate_reply(
            prompt.strip(),
            system_context=(
                f"AI Studio playground request for configured model {model_id}. "
                f"Requested parameters: {parameters}"
            ),
        )

        run = PlaygroundRun(
            model_uid=model_id,
            user_id=user_id,
            prompt=prompt,
            output=output,
            parameters=str(parameters),
            # Do not fabricate provider token counts when the provider router
            # does not return authoritative usage metadata.
            tokens_used=None
        )
        db.session.add(run)
        db.session.commit()

        return jsonify({
            "status": "success",
            "model_id": model_id,
            "prompt": prompt,
            "output": output,
            "tokens_used": None,
            "usage": "Usage unavailable"
        }), 200
    except RuntimeError:
        db.session.rollback()
        return jsonify({"error": "AI provider is unavailable or not configured."}), 503
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@ai_studio_bp.route("/ai-studio/playground/history", methods=["GET"])
@jwt_required()
def playground_history():
    try:
        user_id = str(get_jwt_identity())
        runs = PlaygroundRun.query.filter_by(user_id=user_id).order_by(PlaygroundRun.created_at.desc()).limit(50).all()
        return jsonify({"runs": [r.to_dict() for r in runs]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
