from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

studio_bp = Blueprint('studio_bp', __name__)

@studio_bp.route('/api/studio/generate-image', methods=['POST'])
@jwt_required()
def generate_image():
    return jsonify({
        'status': 'error',
        'message': 'Image generation is not configured.'
    }), 501

@studio_bp.route('/api/studio/generate-video', methods=['POST'])
@jwt_required()
def generate_video():
    return jsonify({
        'status': 'error',
        'message': 'Video generation is not configured.'
    }), 501
