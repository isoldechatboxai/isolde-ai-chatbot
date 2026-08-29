"""Conversation-context service backed by the chat repository.

This module deliberately keeps memory retrieval scoped to one already-authorized
conversation.  Ownership and tenant authorization remain the responsibility of
the route/service layer that resolves the conversation before constructing a
context for a model request.
"""

from typing import Any

from app.repositories.chat_repository import ChatRepository


class MemoryService:
    """Build a bounded, chronological message context for a conversation."""

    def __init__(self, chat_repository: ChatRepository) -> None:
        self.chat_repository = chat_repository

    async def get_conversation_context(
        self, conversation_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Return safe message fields for the most recent context window.

        The repository returns messages in chronological order.  When more
        messages exist than the requested window, selecting the final items
        preserves that order while retaining the newest relevant context.
        """
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            raise ValueError("conversation_id is required")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer between 1 and 100")

        _, total = await self.chat_repository.get_messages_by_conversation(
            conversation_id=conversation_id,
            skip=0,
            limit=1,
        )
        messages, _ = await self.chat_repository.get_messages_by_conversation(
            conversation_id=conversation_id,
            skip=max(total - limit, 0),
            limit=limit,
        )
        # The bounded query prevents unbounded model context construction and
        # preserves chronological ordering for the newest context window.
        return [
            {
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at,
            }
            for message in messages
        ]
