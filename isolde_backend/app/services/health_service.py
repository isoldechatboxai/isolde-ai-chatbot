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

        # 2. Check Storage Directory Write Permissions
        try:
            upload_dir = "uploads"
            os.makedirs(upload_dir, exist_ok=True)
            test_file_path = os.path.join(upload_dir, "health_probe.tmp")
            with open(test_file_path, "w") as f:
                f.write("OK")
            if os.path.exists(test_file_path):
                os.remove(test_file_path)
                health_status["storage"] = "writable"
        except Exception as e:
            health_status["status"] = "degraded"
            if current_app:
                current_app.logger.error(f"[HealthService] Storage health check failed: {str(e)}")

        return health_status

# Singleton instance for application-wide use
health_service = HealthService()