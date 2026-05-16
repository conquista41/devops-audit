from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import verify_token
from app.models.models import User
from pydantic import BaseModel
import uuid

router = APIRouter(prefix="/users", tags=["users"])
bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = verify_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    github_username: str | None
    full_name: str | None
    avatar_url: str | None
    plan: str
    scans_used_this_month: int
    scan_limit: int

    model_config = {"from_attributes": True}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        github_username=current_user.github_username,
        full_name=current_user.full_name,
        avatar_url=current_user.avatar_url,
        plan=current_user.plan.value,
        scans_used_this_month=current_user.scans_used_this_month,
        scan_limit=current_user.scan_limit,
    )
