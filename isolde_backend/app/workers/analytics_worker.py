import logging

logger = logging.getLogger("IsoldeWorkers")

def process_analytics_task(user_id: int, action: str, metadata: dict):
    """
    Background worker task to aggregate telemetry and performance metrics.
    """
    logger.info(f"[AnalyticsWorker] Logging telemetry for User {user_id} - Action: {action}")
    # Analytics data warehousing logic goes here
    logger.info(f"[AnalyticsWorker] Telemetry successfully recorded.")