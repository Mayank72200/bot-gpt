from datetime import datetime
from pydantic import BaseModel


class DocumentUploadRequest(BaseModel):
    user_id: str
    title: str
    text: str


class DocumentResponse(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    chunk_count: int
