from datetime import datetime

from pydantic import BaseModel


class UserCreateRequest(BaseModel):
    email: str
    user_id: str | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True
