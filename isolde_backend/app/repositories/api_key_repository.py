from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.api_key import APIKey  # Assuming model exists

class APIKeyRepository:
    """
    Repository dedicated solely to Enterprise API Key management and validation data operations.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, key_id: str) -> Optional[APIKey]:
        return self.db.query(APIKey).filter(APIKey.id == key_id).first()

    def get_by_key_hash(self, key_hash: str) -> Optional[APIKey]:
        return self.db.query(APIKey).filter(APIKey.key_hash == key_hash).first()

    def get_user_keys(self, user_id: int) -> List[APIKey]:
        return self.db.query(APIKey).filter(APIKey.user_id == user_id).all()

    def create(self, data: dict) -> APIKey:
        api_key = APIKey(**data)
        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)
        return api_key

    def update(self, api_key: APIKey, data: dict) -> APIKey:
        for key, value in data.items():
            setattr(api_key, key, value)
        self.db.commit()
        self.db.refresh(api_key)
        return api_key

    def delete(self, key_id: str) -> bool:
        api_key = self.get_by_id(key_id)
        if api_key:
            self.db.delete(api_key)
            self.db.commit()
            return True
        return False