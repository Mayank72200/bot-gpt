import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError
from app.models.user import User


class UserService:
    def create_user(self, db: Session, email: str, user_id: str | None = None) -> User:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            return existing

        user = User(id=user_id or str(uuid.uuid4()), email=email)
        db.add(user)
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            raise BadRequestError(code="DB_COMMIT_FAILED", message="Failed to create user.") from exc
        db.refresh(user)
        return user

    def list_users(self, db: Session, page: int = 1, page_size: int = 20) -> list[User]:
        offset = (page - 1) * page_size
        return db.query(User).order_by(User.created_at.desc()).offset(offset).limit(page_size).all()
