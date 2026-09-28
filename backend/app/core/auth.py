"""Authentication (JWT bearer tokens) and organization-level access control."""
import uuid
from typing import List, Optional, Set

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import InvalidToken, decode_access_token
from app.models.organization import Organization
from app.models.user import User, UserOrganization

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Tizimga kirish talab qilinadi yoki sessiya muddati tugagan",
    headers={"WWW-Authenticate": "Bearer"},
)
_ORG_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tashkilot topilmadi")


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not token:
        raise _UNAUTHORIZED
    try:
        claims = decode_access_token(token)
        user_id = uuid.UUID(claims["sub"])
    except (InvalidToken, ValueError):
        raise _UNAUTHORIZED
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        raise _UNAUTHORIZED
    return user


async def require_superuser(user: User = Depends(get_current_user)) -> User:
    if not user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Faqat tizim administratori uchun")
    return user


async def accessible_org_ids(db: AsyncSession, user: User) -> Optional[Set[uuid.UUID]]:
    """Organization ids the user may access; None means all (superuser)."""
    if user.is_superuser:
        return None
    rows = await db.execute(select(UserOrganization.organization_id).where(UserOrganization.user_id == user.id))
    return set(rows.scalars().all())


async def ensure_org_access(db: AsyncSession, user: User, org_id: uuid.UUID) -> None:
    """404 (not 403) for foreign organizations so ids of other tenants are not disclosed."""
    allowed = await accessible_org_ids(db, user)
    if allowed is not None and org_id not in allowed:
        raise _ORG_NOT_FOUND


async def require_org_path_access(
    org_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Route dependency for endpoints with an `{org_id}` path parameter."""
    await ensure_org_access(db, user, org_id)


async def require_org_query_access(
    organization_id: uuid.UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Route dependency for endpoints with an `?organization_id=` query parameter."""
    await ensure_org_access(db, user, organization_id)


async def get_accessible_org(db: AsyncSession, user: User, org_id: uuid.UUID) -> Organization:
    await ensure_org_access(db, user, org_id)
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        raise _ORG_NOT_FOUND
    return org


async def grant_org_access(db: AsyncSession, user: User, org_id: uuid.UUID) -> None:
    if user.is_superuser:
        return
    exists = await db.execute(select(UserOrganization).where(
        UserOrganization.user_id == user.id, UserOrganization.organization_id == org_id
    ))
    if not exists.scalar_one_or_none():
        db.add(UserOrganization(user_id=user.id, organization_id=org_id))


def filter_by_orgs(org_ids: Optional[Set[uuid.UUID]], items: List[dict], key: str = "organization_id") -> List[dict]:
    if org_ids is None:
        return items
    allowed = {str(o) for o in org_ids}
    return [it for it in items if str(it.get(key)) in allowed]
