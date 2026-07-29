# app/repositories/ai_repository.py
from app.models.enterprise_models import TokenCostLog, ScoredMemory, AuditLog
from app.extensions import db

class AIRepository:
    @staticmethod
    def log_token_usage(data: dict) -> TokenCostLog:
        log = TokenCostLog(**data)
        db.session.add(log)
        db.session.commit()
        return log

    @staticmethod
    def get_top_memories(user_id: int, limit: int = 5):
        return ScoredMemory.query.filter_by(user_id=user_id)\
            .order_by(ScoredMemory.final_score.desc())\
            .limit(limit).all()

    @staticmethod
    def record_audit(user_id: int, action: str, ip: str, status: str, details: str):
        log = AuditLog(user_id=user_id, action=action, ip_address=ip, status=status, details=details)
        db.session.add(log)
        db.session.commit()