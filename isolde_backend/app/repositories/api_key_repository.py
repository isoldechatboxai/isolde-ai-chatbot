from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.api_key_model import ApiKey  # Assuming model exists

class ApiKeyRepository:
    """
    Repository dedicated solely to Enterprise API Key management and validation data operations.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, key_id: str) -> Optional[ApiKey]:
        return self.db.query(ApiKey).filter(ApiKey.id == key_id).first()

    def get_by_key_hash(self, key_hash: str) -> Optional[ApiKey]:
        return self.db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()

    def get_user_keys(self, user_id: int) -> List[ApiKey]:
        return self.db.query(ApiKey).filter(ApiKey.user_id == user_id).all()

    def create(self, data: dict) -> ApiKey:
        api_key = ApiKey(**data)
        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)
        return api_key

    def update(self, api_key: ApiKey, data: dict) -> ApiKey:
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