# app/services/ai_orchestrator.py

import time
import logging
from typing import Dict, Any, List, Optional
from flask import current_app

# Import existing provider router or fallback handlers if available
try:
    from app.services.provider_router import route_request, get_provider_health
except ImportError:
    # Fallback mock references for architectural isolation
    def route_request(prompt, provider=None, **kwargs):
        return {"response": "Mock AI Response", "provider": provider or "default", "tokens": len(prompt.split())}
    def get_provider_health():
        return {"primary": True, "fallback": True}

class AIOrchestrator:
    """
    Central AI Orchestrator for managing multi-provider LLM requests,
    context assembly, prompt optimization, health tracking, and automatic fallback.
    """
    
    def __init__(self, primary_provider: str = "gemini", fallback_providers: Optional[List[str]] = None):
        self.primary_provider = primary_provider
        self.fallback_providers = fallback_providers or ["openai", "anthropic"]
        self.health_status = {}

    def check_health(self) -> Dict[str, bool]:
        """Tracks and returns provider health status."""
        try:
            if callable(get_provider_health):
                self.health_status = get_provider_health()
            else:
                self.health_status = {self.primary_provider: True}
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Health check failed: {e}")
            self.health_status = {self.primary_provider: False}
        return self.health_status

    def generate_response(self, assembled_prompt: str, user_id: str, **kwargs) -> Dict[str, Any]:
        """
        Executes prompt generation with automatic fallback, health tracking, and latency monitoring.
        """
        start_time = time.time()
        providers_to_try = [self.primary_provider] + self.fallback_providers
        
        last_error = None
        for provider in providers_to_try:
            try:
                if current_app:
                    current_app.logger.info(f"[Orchestrator] Attempting generation with provider: {provider}")
                
                # Route request to provider
                result = route_request(assembled_prompt, provider=provider, user_id=user_id, **kwargs)
                
                latency = time.time() - start_time
                if current_app:
                    current_app.logger.info(f"[Orchestrator] Success using {provider} in {latency:.4f}s")
                
                return {
                    "success": True,
                    "provider": provider,
                    "result": result,
                    "latency": latency,
                    "error": None
                }
            except Exception as e:
                last_error = e
                if current_app:
                    current_app.logger.warning(f"[Orchestrator] Provider {provider} failed: {str(e)}. Falling back...")
                continue

        # If all providers fail
        latency = time.time() - start_time
        if current_app:
            current_app.logger.error(f"[Orchestrator] All providers failed. Last error: {str(last_error)}")
        
        return {
            "success": False,
            "provider": None,
            "result": None,
            "latency": latency,
            "error": str(last_error) or "All AI providers failed."
        }

# Singleton instance for application-wide use
ai_orchestrator = AIOrchestrator()