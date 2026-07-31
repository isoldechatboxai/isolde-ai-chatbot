from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.ai_studio_model import CustomModel, PlaygroundRun

ai_studio_bp = Blueprint("ai_studio_bp", __name__)


@ai_studio_bp.route("/ai-studio/models", methods=["GET"])
@jwt_required(optional=True)
def list_custom_models():
    try:
        user_id = str(get_jwt_identity() or "1")
        models = CustomModel.query.filter_by(user_id=user_id).order_by(CustomModel.created_at.desc()).all()
        return jsonify({"models": [m.to_dict() for m in models]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ai_studio_bp.route("/ai-studio/models", methods=["POST"])
@jwt_required(optional=True)
def create_custom_model():
    try:
        user_id = str(get_jwt_identity() or "1")
        data = request.get_json() or {}
        model_name = data.get("model_name", "Untitled Model")
        base_model = data.get("base_model", "gemini-flash")
        dataset_uri = data.get("dataset_uri", "")

        model_uid = f"model-{user_id[:6]}-{model_name.lower().replace(' ', '-')}-{CustomModel.query.count() + 1}"
        model = CustomModel(
            model_uid=model_uid,
            user_id=user_id,
            name=model_name,
            base_model=base_model,
            dataset_uri=dataset_uri,
            status="training"
        )
        db.session.add(model)
        db.session.commit()
        return jsonify({
            "status": "success",
            "message": "Model fine-tuning job successfully queued.",
            "model": model.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@ai_studio_bp.route("/ai-studio/playground/test", methods=["POST"])
@jwt_required(optional=True)
def test_playground_prompt():
    try:
        user_id = str(get_jwt_identity() or "1")
        data = request.get_json() or {}
        model_id = data.get("model_id", "default")
        prompt = data.get("prompt", "")
        parameters = data.get("parameters", {})

        output = f"Simulated AI Studio response using parameters {parameters}."
        tokens_used = max(len(prompt.split()) * 2, 1)

        run = PlaygroundRun(
            model_uid=model_id,
            user_id=user_id,
            prompt=prompt,
            output=output,
            parameters=str(parameters),
            tokens_used=tokens_used
        )
        db.session.add(run)
        db.session.commit()

        return jsonify({
            "status": "success",
            "model_id": model_id,
            "prompt": prompt,
            "output": output,
            "tokens_used": tokens_used
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@ai_studio_bp.route("/ai-studio/playground/history", methods=["GET"])
@jwt_required(optional=True)
def playground_history():
    try:
        user_id = str(get_jwt_identity() or "1")
        runs = PlaygroundRun.query.filter_by(user_id=user_id).order_by(PlaygroundRun.created_at.desc()).limit(50).all()
        return jsonify({"runs": [r.to_dict() for r in runs]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500