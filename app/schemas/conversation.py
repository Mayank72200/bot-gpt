from datetime import datetime
from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    user_id: str
    mode: str = Field(default="OPEN", pattern="^(OPEN|RAG)$")


class ConversationResponse(BaseModel):
    id: str
    user_id: str
    mode: str
    summary: str | None
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class MessageCreateRequest(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: int
    conversation_id: str
    role: str
    content: str
    token_count: int
    sequence_number: int
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationDetailResponse(BaseModel):
    conversation: ConversationResponse
    messages: list[MessageResponse]
