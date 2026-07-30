from app.repositories.analytics_repository import AnalyticsRepository

class AnalyticsService:
    """
    Service to process and log system performance metrics, user actions, 
    and operational telemetry.
    """
    def __init__(self, analytics_repo: AnalyticsRepository):
        self.analytics_repo = analytics_repo

    def log_event(self, user_id: int, action: str, metadata: dict = None):
        log_data = {
            "user_id": user_id,
            "action": action,
            "meta_data": metadata or {}
        }
        return self.analytics_repo.create(log_data)

    def fetch_user_telemetry(self, user_id: int):
        return self.analytics_repo.get_user_logs(user_id)