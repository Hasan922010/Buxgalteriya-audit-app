import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.rbac import UserRole

USERNAME_PATTERN = r"^[a-zA-Z0-9_.-]{3,64}$"


class UserRead(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str
    role: UserRole
    is_superuser: bool
    is_active: bool
    created_at: Optional[datetime] = None
    organization_ids: List[uuid.UUID] = []

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class UserCreate(BaseModel):
    username: str = Field(..., pattern=USERNAME_PATTERN)
    full_name: str = Field("", max_length=255)
    password: str = Field(..., min_length=8, max_length=72)
    role: UserRole
    is_superuser: bool = False
    organization_ids: List[uuid.UUID] = []


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = Field(None, min_length=8, max_length=72)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    organization_ids: Optional[List[uuid.UUID]] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=72)
