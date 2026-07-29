# app/routes/voice_routes.py
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.voice_model import VoiceProfile, AudioSettings, VoiceSession, Meeting, Transcript

voice_bp = Blueprint("voice_bp", __name__)

# --- VOICE PROFILES & SETTINGS ---
@voice_bp.route("/voice/profile", methods=["GET"])
@jwt_required(optional=True)
def get_voice_profile():
    try:
        # Defaulting to 1 for generic implementation, replace with get_jwt_identity()
        user_id = get_jwt_identity() or 1 
        profile = VoiceProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            profile = VoiceProfile(user_id=user_id)
            db.session.add(profile)
            db.session.commit()
        return jsonify({"profile": profile.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@voice_bp.route("/voice/profile", methods=["PUT"])
@jwt_required(optional=True)
def update_voice_profile():
    try:
        user_id = get_jwt_identity() or 1 
        data = request.get_json() or {}
        profile = VoiceProfile.query.filter_by(user_id=user_id).first()
        
        if not profile:
            profile = VoiceProfile(user_id=user_id)
            db.session.add(profile)

        profile.provider = data.get("provider", profile.provider)
        profile.voice_id = data.get("voice_id", profile.voice_id)
        profile.speed = data.get("speed", profile.speed)
        profile.pitch = data.get("pitch", profile.pitch)
        profile.emotion_enabled = data.get("emotion_enabled", profile.emotion_enabled)

        db.session.commit()
        return jsonify({"message": "Voice profile updated", "profile": profile.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# --- REAL-TIME VOICE SESSIONS ---
@voice_bp.route("/voice/session/start", methods=["POST"])
@jwt_required(optional=True)
def start_voice_session():
    try:
        user_id = get_jwt_identity() or 1 
        data = request.get_json() or {}
        
        session = VoiceSession(
            user_id=user_id,
            workspace_id=data.get("workspace_id"),
            agent_id=data.get("agent_id")
        )
        db.session.add(session)
        db.session.commit()
        return jsonify({"message": "Voice session started", "session": session.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@voice_bp.route("/voice/session/<int:session_id>/end", methods=["POST"])
@jwt_required(optional=True)
def end_voice_session(session_id):
    try:
        session = VoiceSession.query.get(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404
        
        session.status = "Ended"
        session.end_time = datetime.utcnow()
        
        # Here we would trigger the Voice -> Memory extraction service asynchronously
        # e.g., extract_memory_from_session.delay(session_id)

        db.session.commit()
        return jsonify({"message": "Voice session ended", "session": session.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# --- MEETING ASSISTANT ---
@voice_bp.route("/voice/meetings", methods=["GET"])
@jwt_required(optional=True)
def list_meetings():
    try:
        meetings = Meeting.query.order_by(Meeting.start_time.desc()).all()
        return jsonify({"meetings": [m.to_dict() for m in meetings]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@voice_bp.route("/voice/meetings/start", methods=["POST"])
@jwt_required(optional=True)
def start_meeting():
    try:
        data = request.get_json() or {}
        meeting = Meeting(
            workspace_id=data.get("workspace_id"),
            title=data.get("title", "New AI Meeting")
        )
        db.session.add(meeting)
        db.session.commit()
        return jsonify({"message": "Meeting recording started", "meeting": meeting.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# --- TRANSCRIPTS & HISTORY ---
@voice_bp.route("/voice/session/<int:session_id>/transcripts", methods=["GET"])
@jwt_required(optional=True)
def get_session_transcripts(session_id):
    try:
        transcripts = Transcript.query.filter_by(session_id=session_id).order_by(Transcript.timestamp.asc()).all()
        return jsonify({"transcripts": [t.to_dict() for t in transcripts]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500