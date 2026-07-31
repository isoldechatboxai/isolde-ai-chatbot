# app/repositories/analytics_repository.py

from typing import List, Dict, Any, Optional
from sqlalchemy import func
from app.extensions import db
from app.models.analytics_model import AnalyticsModel

class AnalyticsRepository:
    """
    Repository layer for managing CRUD operations and aggregation queries 
    for AI telemetry, token metrics, and operational costs.
    """

    def log_metric(
        self, 
        user_id: Optional[str] = None, 
        workspace_id: Optional[str] = None, 
        provider: Optional[str] = None, 
        model_name: Optional[str] = None, 
        prompt_tokens: int = 0, 
        completion_tokens: int = 0, 
        total_tokens: int = 0, 
        cost: float = 0.0, 
        latency: float = 0.0, 
        status: str = "success", 
        extra_metadata: Optional[str] = None
    ) -> AnalyticsModel:
        """Records a new telemetry metric entry into the database."""
        metric = AnalyticsModel(
            user_id=user_id,
            workspace_id=workspace_id,
            provider=provider,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            latency=latency,
            status=status,
            extra_metadata=extra_metadata
        )
        db.session.add(metric)
        db.session.commit()
        return metric

    def get_metrics_by_user(self, user_id: str, limit: int = 50) -> List[AnalyticsModel]:
        """Retrieves recent analytics metrics logs for a specific user."""
        return AnalyticsModel.query.filter_by(user_id=user_id).order_by(AnalyticsModel.timestamp.desc()).limit(limit).all()

    def get_usage_summary(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Aggregates total tokens consumed, total cost, and average latency."""
        query = db.session.query(
            func.sum(AnalyticsModel.total_tokens).label("total_tokens"),
            func.sum(AnalyticsModel.cost).label("total_cost"),
            func.avg(AnalyticsModel.latency).label("avg_latency"),
            func.count(AnalyticsModel.id).label("total_requests")
        )

        if user_id:
            query = query.filter_by(user_id=user_id)

        result = query.first()

        return {
            "total_tokens": result.total_tokens or 0,
            "total_cost": round(result.total_cost or 0.0, 6),
            "avg_latency": round(result.avg_latency or 0.0, 4),
            "total_requests": result.total_requests or 0
        }

# Singleton instance for application-wide use
analytics_repository = AnalyticsRepository()