import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, verify_token
from app.core.config import get_settings
from app.models.models import User
from app.services.github import get_github_oauth_url, exchange_code_for_token, get_github_user
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

_state_store: dict[str, bool] = {}  # TODO: use Redis in production


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


@router.get("/github/login")
async def github_login():
    state = secrets.token_urlsafe(32)
    _state_store[state] = True
    return {"url": get_github_oauth_url(state)}


@router.get("/github/callback")
async def github_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    if state not in _state_store:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    del _state_store[state]

    try:
        access_token = await exchange_code_for_token(code)
        gh_user = await get_github_user(access_token)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"GitHub auth failed: {str(e)}")

    github_id = str(gh_user["id"])
    result = await db.execute(select(User).where(User.github_id == github_id))
    user = result.scalar_one_or_none()

    if not user:
        # New user — create account
        user = User(
            email=gh_user.get("email") or f"{gh_user['login']}@github.local",
            github_id=github_id,
            github_username=gh_user["login"],
            github_access_token=access_token,
            full_name=gh_user.get("name"),
            avatar_url=gh_user.get("avatar_url"),
        )
        db.add(user)
        await db.flush()
    else:
        user.github_access_token = access_token
        user.github_username = gh_user["login"]
        user.avatar_url = gh_user.get("avatar_url")

    jwt_token = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))

    # Redirect to frontend with tokens
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/auth/callback?access_token={jwt_token}&refresh_token={refresh}"
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    user_id = verify_token(body.refresh_token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )
