"""User management: creation, organization membership, bootstrap administrator."""
import logging
import uuid
from typing import Iterable, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rbac import UserRole
from app.core.security import get_password_hash
from app.models.organization import Organization
from app.models.user import User, UserOrganization
from app.schemas.auth import UserRead

logger = logging.getLogger("user_service")


class UserServiceError(ValueError):
    """Business-rule violation (duplicate username, unknown organization, ...)."""


async def get_by_username(db: AsyncSession, username: str) -> Optional[User]:
    return (await db.execute(select(User).where(func.lower(User.username) == username.lower()))).scalar_one_or_none()


async def organization_ids_of(db: AsyncSession, user: User) -> List[uuid.UUID]:
    if user.is_superuser:
        return list((await db.execute(select(Organization.id).order_by(Organization.name))).scalars().all())
    rows = await db.execute(select(UserOrganization.organization_id).where(UserOrganization.user_id == user.id))
    return list(rows.scalars().all())


async def to_read(db: AsyncSession, user: User) -> UserRead:
    return UserRead(
        id=user.id,
        username=user.username,
        full_name=user.full_name or "",
        role=UserRole(user.role),
        is_superuser=user.is_superuser,
        is_active=user.is_active,
        created_at=user.created_at,
        organization_ids=await organization_ids_of(db, user),
    )


async def set_memberships(db: AsyncSession, user: User, org_ids: Iterable[uuid.UUID]) -> None:
    wanted = set(org_ids)
    if wanted:
        found = set((await db.execute(select(Organization.id).where(Organization.id.in_(wanted)))).scalars().all())
        missing = wanted - found
        if missing:
            raise UserServiceError(f"Tashkilot topilmadi: {', '.join(str(m) for m in missing)}")
    await db.execute(delete(UserOrganization).where(UserOrganization.user_id == user.id))
    db.add_all(UserOrganization(user_id=user.id, organization_id=o) for o in wanted)


async def create_user(
    db: AsyncSession,
    username: str,
    password: str,
    role: UserRole,
    full_name: str = "",
    is_superuser: bool = False,
    organization_ids: Iterable[uuid.UUID] = (),
) -> User:
    if await get_by_username(db, username):
        raise UserServiceError(f"'{username}' login allaqachon band")
    user = User(
        username=username,
        full_name=full_name,
        password_hash=get_password_hash(password),
        role=role.value,
        is_superuser=is_superuser,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await set_memberships(db, user, organization_ids)
    await db.flush()
    return user


async def bootstrap_admin_if_needed(db: AsyncSession) -> Optional[User]:
    """Creates the first superuser from BOOTSTRAP_ADMIN_* settings when no users exist."""
    user_count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    if user_count:
        return None
    if not settings.BOOTSTRAP_ADMIN_USERNAME or not settings.BOOTSTRAP_ADMIN_PASSWORD:
        logger.warning(
            "Foydalanuvchilar yo'q. Administrator yaratish uchun BOOTSTRAP_ADMIN_USERNAME/PASSWORD sozlang "
            "yoki `python -m app.core.create_user` buyrug'idan foydalaning."
        )
        return None
    admin = await create_user(
        db,
        username=settings.BOOTSTRAP_ADMIN_USERNAME,
        password=settings.BOOTSTRAP_ADMIN_PASSWORD,
        role=UserRole.CHIEF_ACCOUNTANT,
        full_name="Tizim administratori",
        is_superuser=True,
    )
    await db.commit()
    logger.info("Boshlang'ich administrator yaratildi: %s", admin.username)
    return admin
