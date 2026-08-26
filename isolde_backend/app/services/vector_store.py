# app/services/vector_store.py
from abc import ABC, abstractmethod

class BaseVectorStore(ABC):
    @abstractmethod
    def upsert(self, vector_id: str, vector: list, metadata: dict):
        pass

    @abstractmethod
    def query(self, vector: list, top_k: int = 5):
        pass

class PineconeVectorStore(BaseVectorStore):
    def upsert(self, vector_id: str, vector: list, metadata: dict):
        raise NotImplementedError("Pinecone storage is not configured.")

    def query(self, vector: list, top_k: int = 5):
        raise NotImplementedError("Pinecone storage is not configured.")
