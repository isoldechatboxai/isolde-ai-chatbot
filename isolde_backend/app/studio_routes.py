from flask import Blueprint, request, jsonify
import os

studio_bp = Blueprint('studio_bp', __name__)

@studio_bp.route('/api/studio/generate-image', methods=['POST'])
def generate_image():
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        aspect_ratio = data.get('aspect_ratio', '1:1')
        
        if not prompt:
            return jsonify({'status': 'error', 'message': 'Prompt is required'}), 400

        # Pollinations AI / Free Public Endpoint or Custom AI Integration
        # Safe reliable image generation URL generation for quick deployment
        encoded_prompt = prompt.replace(" ", "%20")
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"

        return jsonify({
            'status': 'success',
            'image_url': image_url,
            'prompt': prompt,
            'aspect_ratio': aspect_ratio
        }), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@studio_bp.route('/api/studio/generate-video', methods=['POST'])
def generate_video():
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        
        if not prompt:
            return jsonify({'status': 'error', 'message': 'Video prompt is required'}), 400

        # Mock cinematic video generation response for pipeline stability
        return jsonify({
            'status': 'success',
            'message': 'Video generation task queued successfully.',
            'prompt': prompt,
            'estimated_time': '30 seconds'
        }), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500