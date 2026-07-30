# app/services/prompt_builder.py

from typing import List, Dict, Any, Optional

class PromptBuilder:
    """
    Builds optimized, structured prompts for LLMs by combining system instructions,
    context fragments (RAG, memory, workspace), and the user's primary query.
    """
    
    def __init__(self, default_system_prompt: Optional[str] = None):
        self.default_system_prompt = default_system_prompt or (
            "You are Isolde, an advanced, highly intelligent AI assistant and collaborative enterprise OS. "
            "Provide accurate, context-aware, well-structured, and actionable responses."
        )

    def build_prompt(
        self, 
        user_query: str, 
        context_fragments: Optional[List[str]] = None, 
        chat_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Assembles a clean, structured prompt string from multiple sources.
        """
        prompt_parts = []

        # 1. System Instruction
        sys_prompt = system_prompt or self.default_system_prompt
        prompt_parts.append(f"### SYSTEM INSTRUCTION:\n{sys_prompt}\n")

        # 2. Context Fragments (RAG, Uploaded files, Memory)
        if context_fragments:
            prompt_parts.append("### RELEVANT CONTEXT & KNOWLEDGE:")
            for idx, fragment in enumerate(context_fragments, 1):
                prompt_parts.append(f"[{idx}] {fragment}")
            prompt_parts.append("")

        # 3. Recent Chat History (Conversational Memory)
        if chat_history:
            prompt_parts.append("### CONVERSATION HISTORY:")
            for message in chat_history:
                role = message.get("role", "user").capitalize()
                content = message.get("content", "")
                prompt_parts.append(f"{role}: {content}")
            prompt_parts.append("")

        # 4. Current User Query
        prompt_parts.append(f"### CURRENT USER QUERY:\n{user_query}")

        return "\n".join(prompt_parts)

# Singleton instance for easy import
prompt_builder = PromptBuilder()