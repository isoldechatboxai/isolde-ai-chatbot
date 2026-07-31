# app/services/backup_service.py

import os
import shutil
from datetime import datetime
from typing import Dict, Any, Optional
from flask import current_app

class BackupService:
    """
    Manages automated database backups, file persistence safety copies,
    and disaster recovery routines for production environments.
    """

    def __init__(self, backup_dir: Optional[str] = None):
        self.backup_dir = backup_dir or "instance/backups"
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_sqlite_backup(self, db_path: str) -> Dict[str, Any]:
        """Creates a timestamped point-in-time backup copy of a SQLite database file."""
        if not os.path.exists(db_path):
            return {"success": False, "error": f"Source database file not found at {db_path}"}

        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"isolde_backup_{timestamp}.db"
            backup_filepath = os.path.join(self.backup_dir, backup_filename)

            shutil.copy2(db_path, backup_filepath)

            if current_app:
                current_app.logger.info(f"[BackupService] Successfully created database backup at {backup_filepath}")

            return {
                "success": True,
                "backup_path": backup_filepath,
                "timestamp": timestamp,
                "error": None
            }
        except Exception as e:
            if current_app:
                current_app.logger.error(f"[BackupService] Backup creation failed: {str(e)}")
            return {"success": False, "error": str(e)}

# Singleton instance for application-wide use
backup_service = BackupService()