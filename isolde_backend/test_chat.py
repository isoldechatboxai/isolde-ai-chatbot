import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# 🌟 FIX: உங்களது செட்டப் படி 'db'-ஐ import செய்கிறோம்
from app.extensions import db
from app.models import *  # மாடல்களை ரெஜிஸ்டர் செய்ய

from app.repositories.chat_repository import ChatRepository
from app.services.chat_service import ChatService

# Test SQLite asynchronous database URL (in-memory for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

async def run_tests():
    print("🚀 Starting Chat Repository & Service Tests...")

    # 1. Setup async engine and session
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
    async with engine.begin() as conn:
        # 🌟 FIX: 'Base.metadata' க்கு பதிலாக 'db.Model.metadata' பயன்படுத்துகிறோம்
        await conn.run_sync(db.Model.metadata.create_all)

    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        # 2. Initialize Repository and Service
        repo = ChatRepository(session)
        service = ChatService(repo)

        # 3. Test creating a conversation via Service
        print("📝 Testing conversation creation...")
        convo_data = await service.create_new_conversation(
            user_id="test_user_123",
            title="My First Test Chat",
            model="Flash-Lite Extended"
        )
        print(f"✅ Conversation Created: {convo_data}")
        convo_id = convo_data["id"]

        # 4. Test adding a message
        print("💬 Testing message appending...")
        msg_data = await service.append_message_to_chat(
            conversation_id=convo_id,
            role="user",
            content="Hello Isolde, how are you?"
        )
        print(f"✅ Message Added: {msg_data}")

        # 5. Test retrieving conversations
        print("🔍 Testing fetching user conversations...")
        user_convos = await service.get_user_conversations(user_id="test_user_123")
        print(f"✅ User Conversations: {user_convos}")

        # 6. Test retrieving messages
        print("📜 Testing fetching chat messages...")
        messages = await service.get_chat_messages(conversation_id=convo_id)
        print(f"✅ Chat Messages: {messages}")

        print("🎉 All Tests Passed Successfully!")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_tests())