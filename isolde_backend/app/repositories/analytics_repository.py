from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.analytics import AnalyticsLog  # Assuming model exists

class AnalyticsRepository:
    """
    Repository dedicated solely to System Metrics and Analytics data logging.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, log_id: str) -> Optional[AnalyticsLog]:
        return self.db.query(AnalyticsLog).filter(AnalyticsLog.id == log_id).first()

    def get_user_logs(self, user_id: int) -> List[AnalyticsLog]:
        return self.db.query(AnalyticsLog).filter(AnalyticsLog.user_id == user_id).all()

    def create(self, data: dict) -> AnalyticsLog:
        log = AnalyticsLog(**data)
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log