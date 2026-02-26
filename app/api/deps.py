from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.services.context_manager import ContextManager
from app.services.conversation_service import ConversationService
from app.services.document_service import DocumentService
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.rag_service import RagService
from app.services.user_service import UserService
from app.vector_store.faiss_index import FaissIndexManager


def get_settings_dep() -> Settings:
    return get_settings()


def get_faiss_manager(settings: Settings = Depends(get_settings_dep)) -> FaissIndexManager:
    manager = FaissIndexManager(
        settings.vector_index_path,
        settings.vector_dim,
        mistral_api_key=settings.mistral_api_key,
        mistral_base_url=settings.mistral_base_url,
        mistral_embedding_model=settings.mistral_embedding_model,
    )
    manager.initialize()
    return manager


def get_llm_service(settings: Settings = Depends(get_settings_dep)) -> LLMService:
    return LLMService(settings)


def get_embedding_service(llm_service: LLMService = Depends(get_llm_service)) -> EmbeddingService:
    return EmbeddingService(llm_service)


def get_rag_service(
    settings: Settings = Depends(get_settings_dep),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    faiss_manager: FaissIndexManager = Depends(get_faiss_manager),
) -> RagService:
    return RagService(embedding_service=embedding_service, faiss_manager=faiss_manager, top_k=settings.rag_top_k)


def get_context_manager(settings: Settings = Depends(get_settings_dep)) -> ContextManager:
    return ContextManager(
        max_context_tokens=settings.max_context_tokens,
        min_recent_messages=settings.sliding_window_min_messages,
        max_history_messages=settings.max_history_messages,
    )


def get_conversation_service(
    settings: Settings = Depends(get_settings_dep),
    llm_service: LLMService = Depends(get_llm_service),
    context_manager: ContextManager = Depends(get_context_manager),
    rag_service: RagService = Depends(get_rag_service),
) -> ConversationService:
    return ConversationService(
        llm_service=llm_service,
        context_manager=context_manager,
        rag_service=rag_service,
        rag_context_max_tokens=settings.rag_context_max_tokens,
        response_token_reserve=settings.response_token_reserve,
    )


def get_document_service(
    settings: Settings = Depends(get_settings_dep),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    faiss_manager: FaissIndexManager = Depends(get_faiss_manager),
) -> DocumentService:
    return DocumentService(settings=settings, embedding_service=embedding_service, faiss_manager=faiss_manager)


def get_user_service() -> UserService:
    return UserService()


__all__ = ["get_db", "get_conversation_service", "get_document_service"]
