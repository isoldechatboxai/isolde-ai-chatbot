"""
Module: chat_service.py
Description: Service layer implementing all business logic for chats and messages.
Follows the Service Layer pattern strictly: contains all business logic, communicates 
exclusively with repositories, never directly accesses SQLAlchemy models, uses type hints,
proper exception handling, documentation, and maintains backward compatibility.
"""

from typing import List, Optional, Tuple, Sequence, Dict, Any
from app.repositories.chat_repository import ChatRepository


class ChatService:
    """
    Service class handling business logic for chat conversations and messages.
    Interacts solely with the ChatRepository and remains completely decoupled from SQLAlchemy models.
    """

    def __init__(self, chat_repository: ChatRepository) -> None:
        """
        Initializes the ChatService with an instance of ChatRepository.

        Args:
            chat_repository (ChatRepository): The repository handling database operations for chats.
        """
        self.chat_repository = chat_repository

    # ==========================================
    # CONVERSATION BUSINESS LOGIC & OPERATIONS
    # ==========================================

    async def create_new_conversation(
        self,
        user_id: str,
        title: Optional[str] = None,
        is_pinned: bool = False,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Business logic to create a new conversation for a user. Handles default titles and structure.

        Args:
            user_id (str): The unique identifier of the user.
            title (Optional[str]): Custom title for the conversation. Defaults to "New conversation" if empty.
            is_pinned (bool): Pin status flag.
            model (Optional[str]): Selected AI model identifier.

        Returns:
            Dict[str, Any]: Dictionary representation of the conversation data for upper layers.
        """
        try:
            resolved_title = title.strip() if title else "New conversation"
            conversation = await self.chat_repository.create_conversation(
                user_id=user_id,
                title=resolved_title,
                is_pinned=is_pinned,
                model=model
            )
            return self._serialize_conversation(conversation)
        except Exception as e:
            raise RuntimeError(f"Service error while creating conversation: {str(e)}") from e

    async def get_user_conversations(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        search_query: Optional[str] = None,
        is_pinned: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Business logic to retrieve paginated and filtered conversations for a user.

        Args:
            user_id (str): The unique identifier of the user.
            skip (int): Number of records to skip for pagination.
            limit (int): Maximum records to return.
            search_query (Optional[str]): Optional keyword filter for titles.
            is_pinned (Optional[bool]): Optional pinned status filter.

        Returns:
            Dict[str, Any]: Contains list of serialized conversations and total count.
        """
        try:
            conversations, total_count = await self.chat_repository.get_conversations_by_user(
                user_id=user_id,
                skip=skip,
                limit=limit,
                search_query=search_query,
                is_pinned=is_pinned
            )
            return {
                "conversations": [self._serialize_conversation(c) for c in conversations],
                "total": total_count,
                "skip": skip,
                "limit": limit
            }
        except Exception as e:
            raise RuntimeError(f"Service error while fetching conversations for user {user_id}: {str(e)}") from e

    async def get_conversation_details(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves specific conversation details by its ID.

        Args:
            conversation_id (str): The unique identifier of the conversation.

        Returns:
            Optional[Dict[str, Any]]: Serialized conversation dict or None if not found.
        """
        try:
            conversation = await self.chat_repository.get_conversation_by_id(conversation_id)
            if not conversation:
                return None
            return self._serialize_conversation(conversation)
        except Exception as e:
            raise RuntimeError(f"Service error while fetching conversation details {conversation_id}: {str(e)}") from e

    async def update_conversation_metadata(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        is_pinned: Optional[bool] = None,
        model: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Updates conversation metadata such as title, pin status, or associated model.

        Args:
            conversation_id (str): The unique identifier of the conversation.
            title (Optional[str]): New title.
            is_pinned (Optional[bool]): New pin status.
            model (Optional[str]): New model identifier.

        Returns:
            Optional[Dict[str, Any]]: Updated serialized conversation or None if not found.
        """
        try:
            updated = await self.chat_repository.update_conversation(
                conversation_id=conversation_id,
                title=title,
                is_pinned=is_pinned,
                model=model
            )
            if not updated:
                return None
            return self._serialize_conversation(updated)
        except Exception as e:
            raise RuntimeError(f"Service error while updating conversation {conversation_id}: {str(e)}") from e

    async def remove_conversation(self, conversation_id: str) -> bool:
        """
        Deletes a conversation and its dependent data entirely.

        Args:
            conversation_id (str): The unique identifier of the conversation.

        Returns:
            bool: True if deleted successfully, False otherwise.
        """
        try:
            return await self.chat_repository.delete_conversation(conversation_id)
        except Exception as e:
            raise RuntimeError(f"Service error while deleting conversation {conversation_id}: {str(e)}") from e

    # ==========================================
    # MESSAGE BUSINESS LOGIC & OPERATIONS
    # ==========================================

    async def append_message_to_chat(
        self,
        conversation_id: str,
        role: str,
        content: str
    ) -> Dict[str, Any]:
        """
        Business logic to add a new message to an active conversation thread.

        Args:
            conversation_id (str): Target conversation identifier.
            role (str): Sender role ('user', 'bot', 'system').
            content (str): Message payload text.

        Returns:
            Dict[str, Any]: Serialized message object.
        """
        try:
            if not content or not content.strip():
                raise ValueError("Message content cannot be empty.")
            
            message = await self.chat_repository.add_message(
                conversation_id=conversation_id,
                role=role,
                content=content
            )
            return self._serialize_message(message)
        except Exception as e:
            raise RuntimeError(f"Service error while adding message to conversation {conversation_id}: {str(e)}") from e

    async def get_chat_messages(
        self,
        conversation_id: str,
        skip: int = 0,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Retrieves paginated messages for a conversation thread in chronological order.

        Args:
            conversation_id (str): Target conversation identifier.
            skip (int): Pagination offset.
            limit (int): Pagination limit.

        Returns:
            Dict[str, Any]: Serialized list of messages and metadata.
        """
        try:
            messages, total_count = await self.chat_repository.get_messages_by_conversation(
                conversation_id=conversation_id,
                skip=skip,
                limit=limit
            )
            return {
                "messages": [self._serialize_message(m) for m in messages],
                "total": total_count,
                "skip": skip,
                "limit": limit
            }
        except Exception as e:
            raise RuntimeError(f"Service error while retrieving messages for conversation {conversation_id}: {str(e)}") from e

    async def clear_chat_messages(self, conversation_id: str) -> bool:
        """
        Clears all message history inside a conversation without removing the conversation header.

        Args:
            conversation_id (str): Target conversation identifier.

        Returns:
            bool: True if cleared successfully.
        """
        try:
            return await self.chat_repository.delete_messages_by_conversation(conversation_id)
        except Exception as e:
            raise RuntimeError(f"Service error while clearing messages for conversation {conversation_id}: {str(e)}") from e

    # ==========================================
    # PRIVATE HELPER SERIALIZERS
    # ==========================================

    def _serialize_conversation(self, conversation: Any) -> Dict[str, Any]:
        """Maps conversation model attributes safely into a standard dictionary dictionary."""
        return {
            "id": getattr(conversation, "id", None),
            "user_id": getattr(conversation, "user_id", None),
            "title": getattr(conversation, "title", "New conversation"),
            "is_pinned": getattr(conversation, "is_pinned", False),
            "model": getattr(conversation, "model", None),
            "created_at": getattr(conversation, "created_at", None),
            "updated_at": getattr(conversation, "updated_at", None),
        }

    def _serialize_message(self, message: Any) -> Dict[str, Any]:
        """Maps message model attributes safely into a standard dictionary."""
        return {
            "id": getattr(message, "id", None),
            "conversation_id": getattr(message, "conversation_id", None),
            "role": getattr(message, "role", "user"),
            "content": getattr(message, "content", ""),
            "created_at": getattr(message, "created_at", None),
        }