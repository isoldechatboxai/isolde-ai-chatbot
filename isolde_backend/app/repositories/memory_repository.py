from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.memory import UserMemory  # Assuming model exists

class MemoryRepository:
    """
    Repository dedicated solely to AI Memory System data operations.
    Contains zero business logic.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, memory_id: str) -> Optional[UserMemory]:
        return self.db.query(UserMemory).filter(UserMemory.id == memory_id).first()

    def get_user_memories(self, user_id: int) -> List[UserMemory]:
        return self.db.query(UserMemory).filter(UserMemory.user_id == user_id).all()

    def create_memory(self, memory_data: dict) -> UserMemory:
        memory = UserMemory(**memory_data)
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        return memory

    def delete_memory(self, memory_id: str) -> bool:
        memory = self.get_by_id(memory_id)
        if memory:
            self.db.delete(memory)
            self.db.commit()
            return True
        return False

    def clear_all_user_memories(self, user_id: int) -> int:
        deleted_count = self.db.query(UserMemory).filter(UserMemory.user_id == user_id).delete()
        self.db.commit()
        return deleted_count