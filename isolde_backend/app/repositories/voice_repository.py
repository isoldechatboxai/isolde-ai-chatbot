from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.voice import VoiceLog  # Assuming model exists

class VoiceRepository:
    """
    Repository dedicated solely to Voice Interaction logs and transcription data.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, log_id: str) -> Optional[VoiceLog]:
        return self.db.query(VoiceLog).filter(VoiceLog.id == log_id).first()

    def get_user_logs(self, user_id: int) -> List[VoiceLog]:
        return self.db.query(VoiceLog).filter(VoiceLog.user_id == user_id).all()

    def create(self, data: dict) -> VoiceLog:
        log = VoiceLog(**data)
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def delete(self, log_id: str) -> bool:
        log = self.get_by_id(log_id)
        if log:
            self.db.delete(log)
            self.db.commit()
            return True
        return False