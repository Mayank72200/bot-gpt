from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_user_service
from app.schemas.user import UserCreateRequest, UserResponse
from app.services.user_service import UserService


router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse)
async def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    service: UserService = Depends(get_user_service),
):
    user = service.create_user(db=db, email=payload.email, user_id=payload.user_id)
    return UserResponse.model_validate(user)


@router.get("", response_model=list[UserResponse])
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    service: UserService = Depends(get_user_service),
):
    users = service.list_users(db=db, page=page, page_size=page_size)
    return [UserResponse.model_validate(user) for user in users]
