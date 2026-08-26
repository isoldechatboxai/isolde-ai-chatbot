# app/services/health_service.py

import os
from typing import Dict, Any
from flask import current_app
from app.extensions import db

class HealthService:
    """
    Provides comprehensive health checks, infrastructure diagnostics,
    and liveness/readiness probes for containerized and cloud deployments.
    """

    def __init__(self):
        pass

    def check_system_health(self) -> Dict[str, Any]:
        """Performs liveness checks across database connectivity, storage, and runtime status."""
        health_status = {
            "status": "healthy",
            "database": "disconnected",
            "storage": "unavailable",
            "cancellation": "unavailable",
            "environment": os.environ.get("FLASK_ENV", "production")
        }

        # 1. Check Database Connectivity
        try:
            db.session.execute(db.text("SELECT 1"))
            health_status["database"] = "connected"
        except Exception as e:
            health_status["status"] = "degraded"
            if current_app:
                current_app.logger.error(f"[HealthService] Database health check failed: {str(e)}")

        # 2. Check the configured private storage backend.
        try:
            from app.services.storage_service import get_storage
            if get_storage().check():
                health_status["storage"] = "available"
        except Exception as e:
            health_status["status"] = "degraded"
            if current_app:
                current_app.logger.error(f"[HealthService] Storage health check failed: {str(e)}")

        try:
            cancellation_url = current_app.config.get("CANCELLATION_REDIS_URL", "")
            if cancellation_url:
                import redis
                redis.Redis.from_url(
                    cancellation_url,
                    socket_connect_timeout=current_app.config.get("REDIS_CONNECT_TIMEOUT_SECONDS", 2),
                    socket_timeout=current_app.config.get("REDIS_SOCKET_TIMEOUT_SECONDS", 2),
                ).ping()
                health_status["cancellation"] = "connected"
            elif not current_app.config.get("IS_PRODUCTION"):
                health_status["cancellation"] = "local-development"
            else:
                health_status["status"] = "degraded"
        except Exception as e:
            health_status["status"] = "degraded"
            current_app.logger.error("[HealthService] Cancellation storage check failed: %s", e)

        return health_status

# Singleton instance for application-wide use
health_service = HealthService()
