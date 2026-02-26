import pytest
from langchain_core.embeddings import Embeddings
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.context_manager import ContextManager
from app.services.conversation_service import ConversationService
from app.services.llm_service import LLMService
from app.services.rag_service import RagService
from app.vector_store.faiss_index import FaissIndexManager
from app.models.message import Message


class TestEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.0] * get_settings().vector_dim


class DummyRagService(RagService):
    def __init__(self):
        settings = get_settings()
        faiss_manager = FaissIndexManager(
            settings.vector_index_path,
            settings.vector_dim,
            embedding_provider=TestEmbeddings(),
        )
        faiss_manager.initialize()
        super().__init__(embedding_service=None, faiss_manager=faiss_manager, top_k=2)  # type: ignore[arg-type]

    async def retrieve_context(self, db: Session, user_id: str, query: str) -> list[str]:
        return []


@pytest.mark.asyncio
async def test_conversation_creation_and_message_order(db_session: Session, user_id: str) -> None:
    settings = get_settings().model_copy(deep=True)
    settings.mistral_api_key = ""
    service = ConversationService(
        llm_service=LLMService(settings),
        context_manager=ContextManager(max_context_tokens=4000, min_recent_messages=3),
        rag_service=DummyRagService(),
    )

    conv = service.create_conversation(db_session, user_id=user_id, mode="OPEN")
    assert conv.user_id == user_id

    user_msg, assistant_msg = await service.add_user_message_and_respond(db_session, conv.id, "Hello there")
    assert user_msg.sequence_number == 1
    assert assistant_msg.sequence_number == 2

    db_session.add(
        Message(
            conversation_id=conv.id,
            role="assistant",
            content="third",
            token_count=1,
            sequence_number=3,
        )
    )
    db_session.commit()

    _, messages = service.get_conversation_with_messages(db_session, conv.id)
    seq = [m.sequence_number for m in messages]
    assert seq == sorted(seq)
