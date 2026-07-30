# app/services/ai_pipeline_service.py

from flask import current_app
from app.services.context_engine import context_engine
from app.services.prompt_builder import prompt_builder
from app.services.ai_orchestrator import ai_orchestrator

def process_ai_request(user_id: str, query: str, workspace_id: str = None, **kwargs) -> dict:
    """
    End-to-end AI execution pipeline:
    1. Assemble context (Memory, RAG, History) via Context Engine.
    2. Build optimized prompt via Prompt Builder.
    3. Execute request with fallback & multi-provider routing via AI Orchestrator.
    """
    try:
        # 1. Context Assembly
        context_data = context_engine.assemble_context(
            user_id=user_id, 
            query=query, 
            workspace_id=workspace_id
        )
        
        # 2. Prompt Building
        final_prompt = prompt_builder.build_prompt(
            user_query=query,
            context_fragments=context_data.get("context_fragments"),
            chat_history=context_data.get("chat_history")
        )
        
        # 3. Orchestration & Execution (with automatic fallback & health tracking)
        result = ai_orchestrator.generate_response(
            assembled_prompt=final_prompt,
            user_id=user_id,
            **kwargs
        )
        
        return result

    except Exception as e:
        if current_app:
            current_app.logger.error(f"[AIPipeline] Error processing request for user {user_id}: {str(e)}")
        
        return {
            "success": False,
            "provider": None,
            "result": None,
            "latency": 0.0,
            "error": str(e)
        }