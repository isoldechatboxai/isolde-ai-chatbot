import logging
import requests
from typing import Any, Dict, Optional

logger = logging.getLogger("isolde.sdk")
logger.setLevel(logging.INFO)


class IsoldeClient:
    """Official Developer SDK client for interacting with the Isolde AI Platform programmatically."""

    def __init__(self, api_key: str, base_url: str = "http://localhost:5000/api", timeout: int = 30) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate_chat(self, prompt: str, model_version: Optional[str] = None) -> Dict[str, Any]:
        """Sends a chat completion request via the Isolde AI SDK."""
        endpoint = f"{self.base_url}/chat"
        payload = {"message": prompt}
        if model_version:
            payload["model"] = model_version

        logger.info("SDK chat request sent to configured backend")
        response = requests.post(endpoint, headers=self._headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def execute_plugin(self, plugin_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Triggers a registered plugin via the SDK."""
        endpoint = f"{self.base_url}/plugins/registry/{plugin_name}/execute"
        logger.info("SDK plugin execution request sent")
        response = requests.post(endpoint, headers=self._headers, json=data, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
