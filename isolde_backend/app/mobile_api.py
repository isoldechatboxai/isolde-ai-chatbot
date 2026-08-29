import logging
from typing import Any, Dict

logger = logging.getLogger("isolde.mobile")
logger.setLevel(logging.INFO)


class MobileAPIManager:
    """Manages mobile-specific device registration, token sync, push notifications, and optimized payload responses."""

    @staticmethod
    def register_device(user_id: str, device_token: str, platform: str) -> Dict[str, Any]:
        """Registers or updates a mobile device token for push notifications (FCM/APNs)."""
        raise NotImplementedError("Push notification registration is not configured.")

    @staticmethod
    def format_mobile_payload(data: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap a response for mobile clients without claiming transport compression."""
        return {
            "optimized": False,
            "payload": data,
            "compression": "none"
        }


# Global mobile API instance
mobile_api_manager = MobileAPIManager()
