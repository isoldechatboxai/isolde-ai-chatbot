import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.extensions import db
from app.models import *  # மாடல்களை ரெஜிஸ்டர் செய்ய

from app.repositories.chat_repository import ChatRepository
from app.services.memory_service import MemoryService

# Test SQLite asynchronous database URL (in-memory for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

async def run_tests():
    print("🚀 Starting Memory Service Tests...")

    # 1. Setup async engine and session
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(db.Model.metadata.create_all)

    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        # 2. Initialize Repository and Service
        chat_repo = ChatRepository(session)
        memory_service = MemoryService(chat_repo)

        # 3. Create a test conversation
        print("📝 Creating a test conversation...")
        convo = await chat_repo.create_conversation(user_id="user_memory_123", title="Memory Test")
        convo_id = str(convo.id)

        # 4. Add some sample messages
        print("💬 Adding messages to conversation...")
        await chat_repo.add_message(convo_id, role="user", content="Hi Isolde, remember that my favorite color is Blue.")
        await chat_repo.add_message(convo_id, role="bot", content="Got it! I will remember that your favorite color is Blue.")
        await chat_repo.add_message(convo_id, role="user", content="What is my favorite color?")

        # 5. Fetch context using Memory Service
        print("🧠 Fetching Context from Memory Service...")
        context = await memory_service.get_conversation_context(conversation_id=convo_id, limit=3)
        
        print("\n✅ Retrieved Context for AI:")
        for msg in context:
            print(f"[{msg['role'].upper()}]: {msg['content']}")

        print("\n🎉 Memory Service Test Passed Successfully!")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_tests())