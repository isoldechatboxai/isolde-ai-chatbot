"""
AI Orchestrator compatibility layer.

Part 1 rules preserved:
- do NOT create a second provider router
- do NOT create a second AI engine
- keep provider_router.py as the canonical AI provider layer
- delegate all real generation work to the existing provider_router.py
"""

import time
import logging

from typing import Dict, Any, List, Optional

from flask import current_app

from app.services.provider_router import get_provider_manager


class AIOrchestrator:
    """
    Compatibility orchestrator for managing multi-provider LLM requests.

    The actual provider selection, retry, fallback, circuit breaker,
    health-cache, and provider-call logic remains in provider_router.py.
    """

    def __init__(
        self,
        primary_provider: str = "gemini",
        fallback_providers: Optional[List[str]] = None,
    ):
        self.primary_provider = primary_provider
        self.fallback_providers = fallback_providers or ["groq", "openai", "claude"]
        self.health_status = {}

    def check_health(self) -> Dict[str, bool]:
        """
        Return provider health status from the existing provider manager.
        """
        try:
            manager = get_provider_manager()
            self.health_status = manager.get_provider_health()
        except Exception as e:
            try:
                if current_app:
                    current_app.logger.error(f"Health check failed: {e}")
            except Exception:
                logging.getLogger(__name__).error(f"Health check failed: {e}")

            self.health_status = {self.primary_provider: False}

        return self.health_status

    def generate_response(
        self,
        assembled_prompt: str,
        user_id: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Execute generation using the existing provider router.

        This preserves the orchestrator response contract while delegating
        all real provider work to provider_router.ProviderManager.
        """
        start_time = time.time()

        try:
            manager = get_provider_manager()

            history = kwargs.get("history")
            system_context = kwargs.get("system_context", "")
            timeout = kwargs.get("timeout")

            result = manager.generate(
                assembled_prompt,
                history=history,
                system_context=system_context,
                timeout=timeout,
            )

            latency = time.time() - start_time

            if result.success:
                return {
                    "success": True,
                    "provider": result.provider,
                    "result": {
                        "text": result.text,
                        "model": result.model,
                        "tokens_used": result.tokens_used,
                        "latency_ms": result.latency_ms,
                    },
                    "latency": latency,
                    "error": None,
                }

            return {
                "success": False,
                "provider": result.provider,
                "result": None,
                "latency": latency,
                "error": result.error or "AI generation failed.",
            }

        except Exception as e:
            latency = time.time() - start_time

            try:
                if current_app:
                    current_app.logger.error(
                        f"[Orchestrator] Generation failed: {str(e)}"
                    )
            except Exception:
                logging.getLogger(__name__).error(
                    f"[Orchestrator] Generation failed: {str(e)}"
                )

            return {
                "success": False,
                "provider": None,
                "result": None,
                "latency": latency,
                "error": str(e) or "All AI providers failed.",
            }


# Singleton instance for application-wide compatibility.
ai_orchestrator = AIOrchestrator() 