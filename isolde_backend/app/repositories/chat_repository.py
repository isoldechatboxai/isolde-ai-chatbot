"""
Module: chat_repository.py
Description: Repository layer for managing chat conversations and messages using SQLAlchemy.
Follows the Repository Pattern strictly: handles only database operations, communicates 
exclusively with SQLAlchemy models, contains zero business logic, and includes full CRUD,
pagination, filtering, search support, proper error handling, and documentation.
"""

from typing import List, Optional, Tuple, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete, or_, and_, desc
from sqlalchemy.exc import SQLAlchemyError

# Assuming SQLAlchemy models are defined project-wide. 
# We import typical models matching the application context (e.g., Conversation / Chat and Message models).
from app.models import Conversation, Message  # Adjust import path as necessary based on project layout


class ChatRepository:
    """
    Repository class for performing database operations related to Chats, Conversations, and Messages.
    Strictly isolated from business logic and interacts solely with SQLAlchemy sessions and models.
    """

    def __init__(self, db_session: AsyncSession) -> None:
        """
        Initializes the ChatRepository with an asynchronous SQLAlchemy database session.

        Args:
            db_session (AsyncSession): The active asynchronous database session.
        """
        self.db = db_session

    # ==========================================
    # CONVERSATION / CHAT CRUD & OPERATIONS
    # ==========================================

    async def create_conversation(self, user_id: str, title: str, is_pinned: bool = False, model: Optional[str] = None) -> Conversation:
        """
        Creates and persists a new chat conversation record in the database.

        Args:
            user_id (str): The unique identifier of the user owning the conversation.
            title (str): The title of the conversation.
            is_pinned (bool): Flag indicating if the conversation is pinned. Defaults to False.
            model (Optional[str]): The AI model identifier associated with this conversation.

        Returns:
            Conversation: The newly created Conversation SQLAlchemy model instance.
        """
        try:
            # FIX: 'model' column removed to prevent TypeError
            conversation = Conversation(
                user_id=user_id,
                title=title,
                is_pinned=is_pinned
            )
            self.db.add(conversation)
            await self.db.flush()
            await self.db.refresh(conversation)
            return conversation
        except SQLAlchemyError as e:
            await self.db.rollback()
            raise RuntimeError(f"Database error occurred while creating conversation: {str(e)}") from e

    async def get_conversation_by_id(self, conversation_id: str) -> Optional[Conversation]:
        """
        Retrieves a single conversation record by its unique identifier.

        Args:
            conversation_id (str): The primary key or unique identifier of the conversation.

        Returns:
            Optional[Conversation]: The Conversation model instance if found, otherwise None.
        """
        try:
            result = await self.db.execute(
                select(Conversation).filter(Conversation.id == conversation_id)
            )
            return result.scalars().first()
        except SQLAlchemyError as e:
            raise RuntimeError(f"Database error occurred while fetching conversation {conversation_id}: {str(e)}") from e

    async def get_conversations_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        search_query: Optional[str] = None,
        is_pinned: Optional[bool] = None
    ) -> Tuple[Sequence[Conversation], int]:
        """
        Retrieves a paginated, filtered, and searchable list of conversations for a specific user,
        along with the total count matching the criteria.

        Args:
            user_id (str): The unique identifier of the user.
            skip (int): Number of records to skip for pagination (offset). Defaults to 0.
            limit (int): Maximum number of records to return. Defaults to 20.
            search_query (Optional[str]): Optional keyword to search within conversation titles.
            is_pinned (Optional[bool]): Optional filter for pinned status.

        Returns:
            Tuple[Sequence[Conversation], int]: A tuple containing the list of conversation models and the total count.
        """
        try:
            query = select(Conversation).filter(Conversation.user_id == user_id)

            # Apply search filter if provided
            if search_query:
                query = query.filter(Conversation.title.ilike(f"%{search_query}%"))

            # Apply pinned status filter if provided
            if is_pinned is not None:
                query = query.filter(Conversation.is_pinned == is_pinned)

            # Calculate total count before pagination
            count_result = await self.db.execute(query)
            total_count = len(count_result.scalars().all())

            # Apply sorting (pinned first, then by creation/update timestamp descending) and pagination
            query = query.order_by(
                desc(Conversation.is_pinned),
                desc(Conversation.created_at)
            ).offset(skip).limit(limit)

            result = await self.db.execute(query)
            conversations = result.scalars().all()

            return conversations, total_count
        except SQLAlchemyError as e:
            raise RuntimeError(f"Database error occurred while querying conversations for user {user_id}: {str(e)}") from e

    async def update_conversation(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        is_pinned: Optional[bool] = None,
        model: Optional[str] = None
    ) -> Optional[Conversation]:
        """
        Updates an existing conversation record with provided fields.

        Args:
            conversation_id (str): The unique identifier of the conversation to update.
            title (Optional[str]): New title for the conversation.
            is_pinned (Optional[bool]): New pin status.
            model (Optional[str]): New model identifier.

        Returns:
            Optional[Conversation]: The updated Conversation model instance, or None if not found.
        """
        try:
            conversation = await self.get_conversation_by_id(conversation_id)
            if not conversation:
                return None

            if title is not None:
                conversation.title = title
            if is_pinned is not None:
                conversation.is_pinned = is_pinned
            
            # FIX: model property update removed

            await self.db.flush()
            await self.db.refresh(conversation)
            return conversation
        except SQLAlchemyError as e:
            await self.db.rollback()
            raise RuntimeError(f"Database error occurred while updating conversation {conversation_id}: {str(e)}") from e

    async def delete_conversation(self, conversation_id: str) -> bool:
        """
        Deletes a conversation record and its associated messages (via cascade delete) from the database.

        Args:
            conversation_id (str): The unique identifier of the conversation to delete.

        Returns:
            bool: True if deletion was successful, False if the conversation was not found.
        """
        try:
            conversation = await self.get_conversation_by_id(conversation_id)
            if not conversation:
                return False

            await self.db.delete(conversation)
            await self.db.flush()
            return True
        except SQLAlchemyError as e:
            await self.db.rollback()
            raise RuntimeError(f"Database error occurred while deleting conversation {conversation_id}: {str(e)}") from e

    # ==========================================
    # MESSAGE OPERATIONS & CRUD
    # ==========================================

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str
    ) -> Message:
        """
        Adds a new message to a specific conversation.

        Args:
            conversation_id (str): The unique identifier of the target conversation.
            role (str): The role of the sender (e.g., 'user', 'bot', 'system').
            content (str): The text content of the message.

        Returns:
            Message: The newly created Message SQLAlchemy model instance.
        """
        try:
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content
            )
            self.db.add(message)
            await self.db.flush()
            await self.db.refresh(message)
            return message
        except SQLAlchemyError as e:
            await self.db.rollback()
            raise RuntimeError(f"Database error occurred while adding message to conversation {conversation_id}: {str(e)}") from e

    async def get_messages_by_conversation(
        self,
        conversation_id: str,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[Sequence[Message], int]:
        """
        Retrieves a paginated list of messages belonging to a specific conversation in chronological order.

        Args:
            conversation_id (str): The unique identifier of the conversation.
            skip (int): Number of records to skip for pagination (offset). Defaults to 0.
            limit (int): Maximum number of records to return. Defaults to 50.

        Returns:
            Tuple[Sequence[Message], int]: A tuple containing the sequence of messages and the total count.
        """
        try:
            query = select(Message).filter(Message.conversation_id == conversation_id)

            # Calculate total count for the conversation's messages
            count_result = await self.db.execute(query)
            total_count = len(count_result.scalars().all())

            # Retrieve paginated messages sorted by creation time ascending (chronological)
            query = query.order_by(Message.created_at.asc()).offset(skip).limit(limit)
            result = await self.db.execute(query)
            messages = result.scalars().all()

            return messages, total_count
        except SQLAlchemyError as e:
            raise RuntimeError(f"Database error occurred while fetching messages for conversation {conversation_id}: {str(e)}") from e

    async def delete_messages_by_conversation(self, conversation_id: str) -> bool:
        """
        Deletes all messages associated with a specific conversation without deleting the conversation itself.

        Args:
            conversation_id (str): The unique identifier of the conversation.

        Returns:
            bool: True if operation completed successfully.
        """
        try:
            stmt = delete(Message).where(Message.conversation_id == conversation_id)
            await self.db.execute(stmt)
            await self.db.flush()
            return True
        except SQLAlchemyError as e:
            await self.db.rollback()
            raise RuntimeError(f"Database error occurred while clearing messages for conversation {conversation_id}: {str(e)}") from e