import secrets
import time
import uuid
from collections import defaultdict, deque
from typing import Deque, Dict, List

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_superuser
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User
from app.schemas.auth import PasswordChange, TokenResponse, UserCreate, UserRead, UserUpdate
from app.services import user_service
from app.services.user_service import UserServiceError

router = APIRouter()

MAX_FAILED_LOGINS = 5
FAILED_LOGIN_WINDOW_SECONDS = 300
# Verified against for unknown usernames so response time does not reveal which logins exist
_DUMMY_HASH = bcrypt.hashpw(secrets.token_bytes(16), bcrypt.gensalt()).decode("ascii")


class LoginThrottle:
    """In-memory sliding window of failed logins per (client ip, username)."""

    def __init__(self) -> None:
        self._failures: Dict[str, Deque[float]] = defaultdict(deque)

    def _recent(self, key: str) -> Deque[float]:
        window = self._failures[key]
        cutoff = time.monotonic() - FAILED_LOGIN_WINDOW_SECONDS
        while window and window[0] < cutoff:
            window.popleft()
        return window

    def is_blocked(self, key: str) -> bool:
        return len(self._recent(key)) >= MAX_FAILED_LOGINS

    def record_failure(self, key: str) -> None:
        self._recent(key).append(time.monotonic())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)


login_throttle = LoginThrottle()


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """Exchanges username + password for a bearer access token."""
    client_ip = request.client.host if request.client else "unknown"
    throttle_key = f"{client_ip}:{form.username.lower()}"
    if login_throttle.is_blocked(throttle_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Juda ko'p noto'g'ri urinish. Birozdan keyin qayta urinib ko'ring.",
        )

    user = await user_service.get_by_username(db, form.username)
    password_ok = verify_password(form.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not password_ok or not user.is_active:
        login_throttle.record_failure(throttle_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login yoki parol noto'g'ri",
            headers={"WWW-Authenticate": "Bearer"},
        )

    login_throttle.reset(throttle_key)
    token = create_access_token(str(user.id), {"role": user.role})
    return TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=await user_service.to_read(db, user),
    )


@router.get("/me", response_model=UserRead)
async def read_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await user_service.to_read(db, user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChange, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Joriy parol noto'g'ri")
    try:
        user.password_hash = get_password_hash(payload.new_password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/users", response_model=List[UserRead])
async def list_users(_: User = Depends(require_superuser), db: AsyncSession = Depends(get_db)):
    users = (await db.execute(select(User).order_by(User.username))).scalars().all()
    return [await user_service.to_read(db, u) for u in users]


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, _: User = Depends(require_superuser), db: AsyncSession = Depends(get_db)):
    try:
        user = await user_service.create_user(
            db,
            username=payload.username,
            password=payload.password,
            role=payload.role,
            full_name=payload.full_name,
            is_superuser=payload.is_superuser,
            organization_ids=payload.organization_ids,
        )
    except UserServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return await user_service.to_read(db, user)


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    admin: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foydalanuvchi topilmadi")
    if user.id == admin.id and payload.is_active is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="O'zingizni bloklay olmaysiz")
    if user.id == admin.id and payload.is_superuser is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="O'zingizdan administrator huquqini ola olmaysiz")
    try:
        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.role is not None:
            user.role = payload.role.value
        if payload.is_active is not None:
            user.is_active = payload.is_active
        if payload.is_superuser is not None:
            user.is_superuser = payload.is_superuser
        if payload.password is not None:
            user.password_hash = get_password_hash(payload.password)
        if payload.organization_ids is not None:
            await user_service.set_memberships(db, user, payload.organization_ids)
        await db.flush()
    except (UserServiceError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return await user_service.to_read(db, user)
