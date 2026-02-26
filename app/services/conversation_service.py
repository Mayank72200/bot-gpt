from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from instructions.rag_instructions import RAG_SYSTEM_INSTRUCTIONS
from app.models.conversation import Conversation, ConversationMode
from app.models.message import Message
from app.models.user import User
from app.services.context_manager import ContextManager
from app.services.llm_service import LLMService
from app.services.rag_service import RagService


class ConversationService:
    def __init__(
        self,
        llm_service: LLMService,
        context_manager: ContextManager,
        rag_service: RagService,
        rag_context_max_tokens: int | None = None,
        response_token_reserve: int = 600,
    ):
        self.llm_service = llm_service
        self.context_manager = context_manager
        self.rag_service = rag_service
        self.rag_context_max_tokens = rag_context_max_tokens or int(context_manager.max_context_tokens * 0.45)
        self.response_token_reserve = response_token_reserve
        self.base_system_prompt = "You are BOT GPT, a helpful assistant."
        self.rag_instruction_prompt = RAG_SYSTEM_INSTRUCTIONS.strip() or (
            "You are BOT GPT in RAG mode. Ground your answer in retrieved context, "
            "avoid hallucinations, and ask for clarification when context is insufficient."
        )

    @staticmethod
    def _deduplicate_chunks(chunks: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for chunk in chunks:
            normalized = " ".join(chunk.split())
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(chunk)
        return deduped

    def create_conversation(self, db: Session, user_id: str, mode: str) -> Conversation:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFoundError("User not found.")

        conversation = Conversation(user_id=user_id, mode=ConversationMode(mode))
        db.add(conversation)
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            raise BadRequestError(code="DB_COMMIT_FAILED", message="Failed to create conversation.") from exc
        db.refresh(conversation)
        return conversation

    def list_conversations(self, db: Session, user_id: str, page: int = 1, page_size: int = 20) -> list[Conversation]:
        offset = (page - 1) * page_size
        return (
            db.query(Conversation)
            .filter(Conversation.user_id == user_id, Conversation.is_active.is_(True))
            .order_by(Conversation.updated_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

    def get_conversation_with_messages(self, db: Session, conversation_id: str) -> tuple[Conversation, list[Message]]:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id, Conversation.is_active.is_(True)).first()
        if not conversation:
            raise NotFoundError("Invalid conversation ID.")

        messages = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.sequence_number.asc(), Message.created_at.asc())
            .all()
        )
        return conversation, messages

    async def add_user_message_and_respond(self, db: Session, conversation_id: str, content: str) -> tuple[Message, Message]:
        conversation, messages = self.get_conversation_with_messages(db, conversation_id)
        next_seq = messages[-1].sequence_number + 1 if messages else 1

        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=content,
            token_count=self.context_manager.estimate_tokens(content),
            sequence_number=next_seq,
        )
        db.add(user_msg)
        db.flush()

        refreshed_messages = messages + [user_msg]

        prompt_messages: list[dict] = [{"role": "system", "content": self.base_system_prompt}]

        if conversation.summary:
            prompt_messages.append({"role": "system", "content": f"Conversation summary: {conversation.summary}"})

        if conversation.mode == ConversationMode.RAG:
            prompt_messages.append({"role": "system", "content": self.rag_instruction_prompt})
            rag_chunks = await self.rag_service.retrieve_context(db, conversation.user_id, content)
            if rag_chunks:
                deduped_chunks = self._deduplicate_chunks(rag_chunks)
                selected_chunks = self.context_manager.select_full_chunks_with_budget(
                    deduped_chunks,
                    self.rag_context_max_tokens,
                )
                context_block = "\n\n".join(selected_chunks)
                prompt_messages.append({"role": "system", "content": f"Retrieved context:\n{context_block}"})

        # Hard cap: keep only the last N messages (default 10) to prevent
        # token-limit / context-window issues in both OPEN and RAG modes.
        trimmed = self.context_manager.last_n_messages(refreshed_messages)

        for msg in trimmed:
            prompt_messages.append({"role": msg.role, "content": msg.content})

        llm_response = await self.llm_service.generate_chat(prompt_messages)
        assistant_content = llm_response["content"]
        assistant_tokens = llm_response["token_estimate"]

        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_content,
            token_count=assistant_tokens,
            sequence_number=next_seq + 1,
        )

        db.add(assistant_msg)
        conversation.updated_at = datetime.utcnow()

        old_messages_count = max(0, len(refreshed_messages) - len(trimmed))
        if old_messages_count > 6:
            summarized = " ".join(m.content for m in refreshed_messages[:3])
            conversation.summary = (summarized[:400] + "...") if len(summarized) > 400 else summarized

        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            raise BadRequestError(code="DB_COMMIT_FAILED", message="Failed to persist messages.") from exc

        db.refresh(user_msg)
        db.refresh(assistant_msg)
        return user_msg, assistant_msg

    def delete_conversation(self, db: Session, conversation_id: str) -> None:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation:
            raise NotFoundError("Invalid conversation ID.")

        conversation.is_active = False
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            raise BadRequestError(code="DB_COMMIT_FAILED", message="Failed to delete conversation.") from exc
