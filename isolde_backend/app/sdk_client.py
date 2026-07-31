import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("isolde.sdk")
logger.setLevel(logging.INFO)


class IsoldeClient:
    """Official Developer SDK client for interacting with the Isolde AI Platform programmatically."""

    def __init__(self, api_key: str, base_url: str = "http://localhost:5000/api") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate_chat(self, prompt: str, model_version: Optional[str] = None) -> Dict[str, Any]:
        """Sends a chat completion request via the Isolde AI SDK."""
        endpoint = f"{self.base_url}/chat"
        payload = {"prompt": prompt}
        if model_version:
            payload["model"] = model_version

        logger.info(f"SDK Chat Request sent to {endpoint}")
        # In production, integrate actual requests (e.g., requests.post) here.
        return {
            "status": "success",
            "provider": "isolde-sdk",
            "received_prompt": prompt,
            "response": "This is a simulated SDK response from Isolde AI backend."
        }

    def execute_plugin(self, plugin_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Triggers a registered plugin via the SDK."""
        endpoint = f"{self.base_url}/plugins/{plugin_name}/execute"
        logger.info(f"SDK Plugin Execution Request for: {plugin_name}")
        return {
            "status": "success",
            "plugin": plugin_name,
            "result": data
        }