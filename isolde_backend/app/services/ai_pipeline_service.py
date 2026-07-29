# app/services/ai_pipeline_service.py
import re
from app.repositories.ai_repository import AIRepository

class AIPipelineService:
    @staticmethod
    def sanitize_and_validate_prompt(prompt: str) -> str:
        # Module 10: Prompt Guardrails & Sanitizer
        dangerous_patterns = [r"<script>", r"ignore previous instructions", r"system override"]
        for pattern in dangerous_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                raise ValueError("Security Violation: Malicious prompt pattern detected.")
        return prompt.strip()

    @staticmethod
    def route_model(task_type: str, context_size: int) -> str:
        # Module 2: Dynamic AI Model Router
        if task_type == "coding" or context_size > 32000:
            return "claude-3-5-sonnet"
        elif task_type == "reasoning":
            return "gpt-4o"
        return "gpt-4o-mini"

    @staticmethod
    def calculate_memory_scores(memories: list) -> list:
        # Module 8: Memory Scoring Engine
        scored = []
        for mem in memories:
            final = (mem.get('importance', 0.5) * 0.3) + \
                    (mem.get('confidence', 0.8) * 0.2) + \
                    (mem.get('recency', 1.0) * 0.3) + \
                    (mem.get('usage', 0.1) * 0.2)
            mem['final_score'] = final
            scored.append(mem)
        return sorted(scored, key=lambda x: x['final_score'], reverse=True)