"""
Module: memory_service.py
Description: Service layer for managing AI conversation memory. 
It retrieves past messages to provide context (Short-term memory) and 
can be extended for long-term summarization.
"""

from typing import List, Dict, Any
from app.repositories.chat_repository import ChatRepository
# தேவைப்பட்டால் MemoryRepository-ஐ இம்போர்ட் செய்து கொள்ளலாம்
# from app.repositories.memory_repository import MemoryRepository

class MemoryService:
    """
    Service class for handling AI conversation context and memory.
    """

    def __init__(self, chat_repo: ChatRepository) -> None:
        """
        Initializes the MemoryService with necessary repositories.
        
        Args:
            chat_repo (ChatRepository): Repository to fetch chat history.
        """
        self.chat_repo = chat_repo
        # self.memory_repo = memory_repo 

    async def get_conversation_context(self, conversation_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Retrieves the last 'N' messages of a conversation to feed into the AI prompt as context.
        
        Args:
            conversation_id (str): The unique ID of the conversation.
            limit (int): Number of recent messages to retrieve (default is 10).
            
        Returns:
            List[Dict[str, str]]: A list of message dictionaries formatted for AI models (e.g., Gemini/OpenAI).
        """
        # ChatRepository மூலம் பழைய மெசேஜ்களை எடுக்கிறோம்
        messages, _ = await self.chat_repo.get_messages_by_conversation(
            conversation_id=conversation_id, 
            skip=0, 
            limit=limit
        )

        # AI-க்கு புரியும் வகையில் List of Dictionaries ஆக மாற்றுவது
        context = []
        for msg in messages:
            context.append({
                "role": msg.role,
                "content": msg.content
            })
            
        return context

    async def summarize_and_save_memory(self, conversation_id: str, ai_response: str) -> None:
        """
        Placeholder for Long-term memory feature.
        In the future, this can summarize long chats and save them to a Vector DB or Memory table.
        """
        # TODO: Integrate with summarize logic or vector_store
        pass