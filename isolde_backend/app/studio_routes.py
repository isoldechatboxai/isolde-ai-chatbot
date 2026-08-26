from flask import Blueprint, jsonify, current_app
from flask_jwt_extended import jwt_required

studio_bp = Blueprint('studio_bp', __name__)

@studio_bp.route('/api/studio/generate-image', methods=['POST'])
@jwt_required()
def generate_image():
    provider = current_app.config.get("IMAGE_PROVIDER", "")
    return jsonify({
        'status': 'error',
        'capability': 'NOT_CONFIGURED' if not provider else 'NOT_SUPPORTED',
        'message': 'Image generation is not configured.' if not provider else 'The configured image provider is not supported.'
    }), 503 if not provider else 501

@studio_bp.route('/api/studio/generate-video', methods=['POST'])
@jwt_required()
def generate_video():
    provider = current_app.config.get("VIDEO_PROVIDER", "")
    return jsonify({
        'status': 'error',
        'capability': 'NOT_CONFIGURED' if not provider else 'NOT_SUPPORTED',
        'message': 'Video generation is not configured.' if not provider else 'The configured video provider is not supported.'
    }), 503 if not provider else 501


@studio_bp.route('/api/studio/capabilities', methods=['GET'])
@jwt_required()
def studio_capabilities():
    return jsonify({
        "image": "NOT_CONFIGURED" if not current_app.config.get("IMAGE_PROVIDER") else "NOT_SUPPORTED",
        "video": "NOT_CONFIGURED" if not current_app.config.get("VIDEO_PROVIDER") else "NOT_SUPPORTED",
    }), 200
