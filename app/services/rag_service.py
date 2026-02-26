from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError
from app.models.document import Document
from app.vector_store.faiss_index import FaissIndexManager
from app.services.embedding_service import EmbeddingService


class RagService:
    def __init__(self, embedding_service: EmbeddingService, faiss_manager: FaissIndexManager, top_k: int):
        self.embedding_service = embedding_service
        self.faiss_manager = faiss_manager
        self.top_k = top_k

    async def retrieve_context(self, db: Session, user_id: str, query: str) -> list[str]:
        has_docs = db.query(Document.id).filter(Document.user_id == user_id).first() is not None
        if not has_docs:
            raise BadRequestError(code="RAG_NO_DOCUMENTS", message="No documents available for RAG mode.")

        query_vector = await self.embedding_service.embed_text(query)
        return self.faiss_manager.search_by_vector(
            query_vector=query_vector,
            top_k=self.top_k,
            metadata_filter={"user_id": user_id},
        )
