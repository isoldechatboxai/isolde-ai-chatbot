import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("isolde.marketplace")
logger.setLevel(logging.INFO)


class MarketplaceManager:
    """Manages community plugins, prompts, templates, and third-party AI assets listing and acquisition."""

    def __init__(self) -> None:
        self._listings: Dict[str, Dict[str, Any]] = {}

    def publish_asset(self, asset_id: str, author_id: str, metadata: Dict[str, Any]) -> bool:
        """Publishes a new plugin, prompt template, or model asset to the marketplace."""
        try:
            self._listings[asset_id] = {
                "author_id": author_id,
                "metadata": metadata,
                "downloads": 0,
                "rating": 5.0
            }
            logger.info(f"Asset '{asset_id}' successfully published by author '{author_id}'.")
            return True
        except Exception as e:
            logger.exception(f"Failed to publish asset '{asset_id}': {e}")
            return False

    def search_assets(self, query: str) -> List[Dict[str, Any]]:
        """Searches marketplace assets by keyword or category."""
        logger.info(f"Searching marketplace assets for query: '{query}'")
        results = []
        for asset_id, data in self._listings.items():
            if query.lower() in asset_id.lower() or query.lower() in str(data["metadata"]).lower():
                results.append({"asset_id": asset_id, **data})
        return results

    def acquire_asset(self, user_id: str, asset_id: str) -> Dict[str, Any]:
        """Handles user purchase or download of a marketplace asset."""
        if asset_id not in self._listings:
            raise ValueError(f"Marketplace asset '{asset_id}' does not exist.")
        
        self._listings[asset_id]["downloads"] += 1
        logger.info(f"User {user_id} acquired marketplace asset: {asset_id}")
        return {
            "status": "success",
            "user_id": user_id,
            "asset_id": asset_id,
            "message": "Asset successfully downloaded and linked to user account."
        }


# Global marketplace manager instance
marketplace_manager = MarketplaceManager()