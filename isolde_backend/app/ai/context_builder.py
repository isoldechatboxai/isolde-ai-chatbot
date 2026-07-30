class ContextBuilder:
    """
    Assembles conversational history, memory injections, and RAG context chunks 
    into a structured payload for LLM consumption.
    """
    @staticmethod
    def build_payload(system_prompt: str, memories: list, rag_chunks: list, history: list) -> list:
        payload = []
        
        # 1. Inject System Prompt
        if system_prompt:
            payload.append({"role": "system", "content": system_prompt})
            
        # 2. Inject User Memories if available
        if memories:
            memory_text = "Relevant User Memories:\n" + "\n".join([f"- {m}" for m in memories])
            payload.append({"role": "system", "content": memory_text})
            
        # 3. Inject RAG Document Context if available
        if rag_chunks:
            rag_text = "Retrieved Document Context:\n" + "\n".join(rag_chunks)
            payload.append({"role": "system", "content": rag_text})
            
        # 4. Append Conversation History
        for msg in history:
            payload.append({"role": msg.get("role"), "content": msg.get("content")})
            
        return payload