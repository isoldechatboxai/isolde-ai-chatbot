import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

# Configure module-level logger
logger = logging.getLogger("isolde.integrations")
logger.setLevel(logging.INFO)


class IThirdPartyIntegration(ABC):
    """Abstract Base Class for all third-party service integrations."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the third-party service provider."""
        pass

    @abstractmethod
    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Authenticates with the third-party provider."""
        pass

    @abstractmethod
    def send_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sends data or requests to the third-party service."""
        pass


class IntegrationManager:
    """Manages external third-party service connections and unified dispatching."""

    def __init__(self) -> None:
        self._integrations: Dict[str, IThirdPartyIntegration] = {}

    def register_integration(self, integration: IThirdPartyIntegration, credentials: Dict[str, Any]) -> bool:
        """Registers and authenticates a third-party integration."""
        try:
            provider = integration.provider_name
            if integration.authenticate(credentials):
                self._integrations[provider] = integration
                logger.info(f"Successfully integrated and authenticated with: {provider}")
                return True
            else:
                logger.error(f"Authentication failed for integration provider: {provider}")
                return False
        except Exception as e:
            logger.exception(f"Error registering integration {integration.provider_name}: {e}")
            return False

    def get_integration(self, provider_name: str) -> Optional[IThirdPartyIntegration]:
        """Retrieves an active integration by provider name."""
        return self._integrations.get(provider_name)

    def execute_call(self, provider_name: str, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a call through a registered third-party integration."""
        integration = self.get_integration(provider_name)
        if not integration:
            raise ValueError(f"Integration provider '{provider_name}' is not registered or active.")
        
        try:
            return integration.send_request(endpoint, payload)
        except Exception as e:
            logger.exception(f"Failed execution on provider '{provider_name}': {e}")
            raise


# Global singleton instance for integrations
integration_manager = IntegrationManager()