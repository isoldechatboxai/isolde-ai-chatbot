# app/routes/voice_routes.py
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.voice_model import VoiceProfile, AudioSettings, VoiceSession, Meeting, Transcript
from app.models.workspace_model import Workspace, Agent

voice_bp = Blueprint("voice_bp", __name__)

# --- VOICE PROFILES & SETTINGS ---
@voice_bp.route("/voice/profile", methods=["GET"])
@jwt_required()
def get_voice_profile():
    try:
        # Defaulting to 1 for generic implementation, replace with get_jwt_identity()
        user_id = str(get_jwt_identity())
        profile = VoiceProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            profile = VoiceProfile(user_id=user_id)
            db.session.add(profile)
            db.session.commit()
        return jsonify({"profile": profile.to_dict()}), 200
    except Exception:
        current_app.logger.exception("Voice profile lookup failed.")
        return jsonify({"error": "Voice profile is unavailable."}), 500

@voice_bp.route("/voice/profile", methods=["PUT"])
@jwt_required()
def update_voice_profile():
    try:
        user_id = str(get_jwt_identity())
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
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Voice profile update failed.")
        return jsonify({"error": "Voice profile could not be updated."}), 500

# --- REAL-TIME VOICE SESSIONS ---
@voice_bp.route("/voice/session/start", methods=["POST"])
@jwt_required()
def start_voice_session():
    try:
        user_id = str(get_jwt_identity())
        data = request.get_json() or {}
        workspace_id = data.get("workspace_id")
        agent_id = data.get("agent_id")
        if workspace_id and not Workspace.query.filter_by(id=workspace_id, user_id=user_id).first():
            return jsonify({"error": "Workspace not found"}), 404
        if agent_id and not Agent.query.join(Workspace).filter(
            Agent.id == agent_id, Workspace.user_id == user_id
        ).first():
            return jsonify({"error": "Agent not found"}), 404
        
        session = VoiceSession(
            user_id=user_id,
            workspace_id=workspace_id,
            agent_id=agent_id
        )
        db.session.add(session)
        db.session.commit()
        return jsonify({"message": "Voice session started", "session": session.to_dict()}), 201
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Voice session creation failed.")
        return jsonify({"error": "Voice session could not be started."}), 500

@voice_bp.route("/voice/session/<int:session_id>/end", methods=["POST"])
@jwt_required()
def end_voice_session(session_id):
    try:
        session = VoiceSession.query.filter_by(id=session_id, user_id=str(get_jwt_identity())).first()
        if not session:
            return jsonify({"error": "Session not found"}), 404
        
        session.status = "Ended"
        session.end_time = datetime.now(timezone.utc)
        
        # Here we would trigger the Voice -> Memory extraction service asynchronously
        # e.g., extract_memory_from_session.delay(session_id)

        db.session.commit()
        return jsonify({"message": "Voice session ended", "session": session.to_dict()}), 200
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Voice session completion failed.")
        return jsonify({"error": "Voice session could not be ended."}), 500

# --- MEETING ASSISTANT ---
@voice_bp.route("/voice/meetings", methods=["GET"])
@jwt_required()
def list_meetings():
    try:
        meetings = Meeting.query.filter_by(user_id=str(get_jwt_identity())).order_by(Meeting.start_time.desc()).all()
        return jsonify({"meetings": [m.to_dict() for m in meetings]}), 200
    except Exception:
        current_app.logger.exception("Meeting listing failed.")
        return jsonify({"error": "Meetings are unavailable."}), 500

@voice_bp.route("/voice/meetings/start", methods=["POST"])
@jwt_required()
def start_meeting():
    try:
        data = request.get_json() or {}
        user_id = str(get_jwt_identity())
        workspace_id = data.get("workspace_id")
        if workspace_id and not Workspace.query.filter_by(id=workspace_id, user_id=user_id).first():
            return jsonify({"error": "Workspace not found"}), 404
        meeting = Meeting(
            user_id=user_id,
            workspace_id=workspace_id,
            title=data.get("title", "New AI Meeting")
        )
        db.session.add(meeting)
        db.session.commit()
        return jsonify({"message": "Meeting recording started", "meeting": meeting.to_dict()}), 201
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Meeting creation failed.")
        return jsonify({"error": "Meeting could not be started."}), 500

# --- TRANSCRIPTS & HISTORY ---
@voice_bp.route("/voice/session/<int:session_id>/transcripts", methods=["GET"])
@jwt_required()
def get_session_transcripts(session_id):
    try:
        owned_session = VoiceSession.query.filter_by(
            id=session_id, user_id=str(get_jwt_identity())
        ).first()
        if not owned_session:
            return jsonify({"error": "Session not found"}), 404
        transcripts = Transcript.query.filter_by(session_id=session_id).order_by(Transcript.timestamp.asc()).all()
        return jsonify({"transcripts": [t.to_dict() for t in transcripts]}), 200
    except Exception:
        current_app.logger.exception("Transcript listing failed.")
        return jsonify({"error": "Transcripts are unavailable."}), 500

