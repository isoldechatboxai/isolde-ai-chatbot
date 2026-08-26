# app/models/voice_model.py
from datetime import datetime
from app.extensions import db

class VoiceProfile(db.Model):
    __tablename__ = 'voice_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False, index=True)
    provider = db.Column(db.String(50), default='openai') # openai, google, elevenlabs
    voice_id = db.Column(db.String(50), default='alloy') # alloy, echo, fable, onyx, nova, shimmer
    speed = db.Column(db.Float, default=1.0)
    pitch = db.Column(db.Float, default=1.0)
    emotion_enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "provider": self.provider,
            "voice_id": self.voice_id,
            "speed": self.speed,
            "pitch": self.pitch,
            "emotion_enabled": self.emotion_enabled
        }

class AudioSettings(db.Model):
    __tablename__ = 'audio_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False, index=True)
    auto_detect_language = db.Column(db.Boolean, default=True)
    noise_reduction = db.Column(db.Boolean, default=True)
    continuous_listening = db.Column(db.Boolean, default=False)
    push_to_talk = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "auto_detect_language": self.auto_detect_language,
            "noise_reduction": self.noise_reduction,
            "continuous_listening": self.continuous_listening,
            "push_to_talk": self.push_to_talk
        }

class VoiceSession(db.Model):
    __tablename__ = 'voice_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False, index=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=True)
    status = db.Column(db.String(50), default='Active') # Active, Ended, Paused
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    summary = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "agent_id": self.agent_id,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "summary": self.summary
        }

class Meeting(db.Model):
    __tablename__ = 'meetings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False, index=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=True)
    title = db.Column(db.String(255), default='Untitled Meeting')
    status = db.Column(db.String(50), default='Recording') # Recording, Processing, Completed
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    summary = db.Column(db.Text, nullable=True)
    action_items = db.Column(db.Text, nullable=True)
    audio_file_path = db.Column(db.String(500), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "title": self.title,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "summary": self.summary,
            "action_items": self.action_items,
            "audio_file_path": self.audio_file_path
        }

class Speaker(db.Model):
    __tablename__ = 'speakers'
    
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meetings.id', ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(100), default='Speaker')
    voice_signature = db.Column(db.String(255), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "name": self.name
        }

class Transcript(db.Model):
    __tablename__ = 'transcripts'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('voice_sessions.id', ondelete="CASCADE"), nullable=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meetings.id', ondelete="CASCADE"), nullable=True)
    speaker_id = db.Column(db.Integer, db.ForeignKey('speakers.id', ondelete="SET NULL"), nullable=True)
    
    role = db.Column(db.String(50), nullable=False) # User, AI, External
    text = db.Column(db.Text, nullable=False)
    translated_text = db.Column(db.Text, nullable=True) # For Live Translation Module
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "meeting_id": self.meeting_id,
            "speaker_id": self.speaker_id,
            "role": self.role,
            "text": self.text,
            "translated_text": self.translated_text,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }
