from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.rag import RAGDocumentChunk  # Assuming model exists

class RAGRepository:
    """
    Repository dedicated solely to RAG (Retrieval-Augmented Generation) vector chunks and metadata.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_chunk_by_id(self, chunk_id: str) -> Optional[RAGDocumentChunk]:
        return self.db.query(RAGDocumentChunk).filter(RAGDocumentChunk.id == chunk_id).first()

    def get_chunks_by_document(self, document_id: str) -> List[RAGDocumentChunk]:
        return self.db.query(RAGDocumentChunk).filter(RAGDocumentChunk.document_id == document_id).all()

    def create_chunk(self, data: dict) -> RAGDocumentChunk:
        chunk = RAGDocumentChunk(**data)
        self.db.add(chunk)
        self.db.commit()
        self.db.refresh(chunk)
        return chunk

    def delete_chunks_by_document(self, document_id: str) -> int:
        deleted_count = self.db.query(RAGDocumentChunk).filter(RAGDocumentChunk.document_id == document_id).delete()
        self.db.commit()
        return deleted_count