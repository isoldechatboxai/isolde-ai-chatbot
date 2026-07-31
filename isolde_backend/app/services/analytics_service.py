# app/services/analytics_service.py

from typing import Dict, Any, Optional, List
from flask import current_app
from app.repositories.analytics_repository import analytics_repository

class AnalyticsService:
    """
    Service layer for tracking system metrics, AI provider usage, 
    token consumption, cost, and generating analytics reports.
    """

    def track_request(
        self, 
        user_id: Optional[str] = None, 
        workspace_id: Optional[str] = None, 
        provider: Optional[str] = None, 
        model_name: Optional[str] = None, 
        prompt_tokens: int = 0, 
        completion_tokens: int = 0, 
        cost: float = 0.0, 
        latency: float = 0.0, 
        status: str = "success"
    ) -> None:
        """Tracks an individual AI request or operational transaction asynchronously or synchronously."""
        try:
            total_tokens = prompt_tokens + completion_tokens
            analytics_repository.log_metric(
                user_id=user_id,
                workspace_id=workspace_id,
                provider=provider,
                model_name=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost=cost,
                latency=latency,
                status=status
            )
            if current_app:
                current_app.logger.info(f"[AnalyticsService] Tracked request for user {user_id}: {total_tokens} tokens, ${cost} cost.")
        except Exception as e:
            if current_app:
                current_app.logger.error(f"[AnalyticsService] Error tracking request: {str(e)}")

    def get_dashboard_analytics(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Generates comprehensive usage metrics summary for analytics dashboards."""
        summary = analytics_repository.get_usage_summary(user_id=user_id)
        recent_logs = analytics_repository.get_metrics_by_user(user_id=user_id, limit=10) if user_id else []

        return {
            "summary": summary,
            "recent_activity": [log.to_dict() for log in recent_logs]
        }

# Singleton instance for application-wide use
analytics_service = AnalyticsService()