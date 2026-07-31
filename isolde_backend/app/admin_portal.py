import logging
from typing import Any, Dict, List

logger = logging.getLogger("isolde.admin")
logger.setLevel(logging.INFO)


class EnterpriseAdminPortal:
    """Manages enterprise-grade user roles, access control permissions, and system-wide audit logging."""

    def __init__(self) -> None:
        self._audit_logs: List[Dict[str, Any]] = []
        self._user_roles: Dict[str, str] = {}

    def assign_role(self, admin_user_id: str, target_user_id: str, role: str) -> Dict[str, Any]:
        """Assigns an enterprise role (e.g., Admin, Developer, Viewer) to a user."""
        self._user_roles[target_user_id] = role
        log_entry = {
            "action": "ASSIGN_ROLE",
            "performed_by": admin_user_id,
            "target_user": target_user_id,
            "role": role
        }
        self._audit_logs.append(log_entry)
        logger.info(f"Admin {admin_user_id} assigned role '{role}' to user {target_user_id}.")
        return {
            "status": "success",
            "target_user_id": target_user_id,
            "assigned_role": role
        }

    def get_audit_logs(self) -> List[Dict[str, Any]]:
        """Retrieves system audit logs for administrative compliance and security tracking."""
        logger.info("Retrieving enterprise audit logs.")
        return self._audit_logs


# Global enterprise admin portal instance
enterprise_admin_portal = EnterpriseAdminPortal()