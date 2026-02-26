from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_conversation_service, get_db
from app.schemas.conversation import (
    ConversationDetailResponse,
    ConversationResponse,
    CreateConversationRequest,
    MessageCreateRequest,
    MessageResponse,
)
from app.services.conversation_service import ConversationService


router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    payload: CreateConversationRequest,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
):
    conversation = service.create_conversation(db, payload.user_id, payload.mode)
    return ConversationResponse.model_validate(conversation)


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    user_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
):
    conversations = service.list_conversations(db=db, user_id=user_id, page=page, page_size=page_size)
    return [ConversationResponse.model_validate(item) for item in conversations]


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
):
    conversation, messages = service.get_conversation_with_messages(db, conversation_id)
    return ConversationDetailResponse(
        conversation=ConversationResponse.model_validate(conversation),
        messages=[MessageResponse.model_validate(message) for message in messages],
    )


@router.post("/{conversation_id}/messages", response_model=list[MessageResponse])
async def add_message(
    conversation_id: str,
    payload: MessageCreateRequest,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
):
    user_message, assistant_message = await service.add_user_message_and_respond(db, conversation_id, payload.content)
    return [MessageResponse.model_validate(user_message), MessageResponse.model_validate(assistant_message)]


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
):
    service.delete_conversation(db, conversation_id)
    return {"status": "deleted"}
