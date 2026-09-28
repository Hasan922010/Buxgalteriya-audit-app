from enum import Enum
from typing import List, Optional
from fastapi import HTTPException, status, Depends

from app.core.auth import get_current_user
from app.core.config import settings
from app.models.user import User

class UserRole(str, Enum):
    CHIEF_ACCOUNTANT = "CHIEF_ACCOUNTANT"
    OPERATOR = "OPERATOR"
    AUDITOR = "AUDITOR"
    DIRECTOR = "DIRECTOR"

ROLE_LABELS = {
    UserRole.CHIEF_ACCOUNTANT: "Bosh buxgalter",
    UserRole.OPERATOR: "Kassir / Operator",
    UserRole.AUDITOR: "Auditor / Nazoratchi",
    UserRole.DIRECTOR: "Rahbar / Direktor"
}

def get_current_role(user: User = Depends(get_current_user)) -> UserRole:
    """
    The role always comes from the authenticated user record (never from a client header).
    """
    try:
        return UserRole(user.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Foydalanuvchi roli noto'g'ri sozlangan. Administratorga murojaat qiling."
        )

def require_system_reset_enabled() -> None:
    """
    Blocks destructive wipe endpoints unless explicitly enabled via ALLOW_SYSTEM_RESET.
    """
    if not settings.ALLOW_SYSTEM_RESET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ma'lumotlarni tozalash o'chirilgan. Yoqish uchun serverda ALLOW_SYSTEM_RESET=True sozlang."
        )

def require_roles(allowed_roles: List[UserRole]):
    """
    FastAPI dependency to enforce Role-Based Access Control (RBAC).
    Raises HTTP 403 Forbidden if user's role is not within allowed_roles.
    """
    async def role_checker(role: UserRole = Depends(get_current_role)) -> UserRole:
        if role not in allowed_roles:
            allowed_names = [ROLE_LABELS.get(r, r.value) for r in allowed_roles]
            current_name = ROLE_LABELS.get(role, role.value)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Ruxsat etilmagan: Sizning rolingiz ({current_name}) ushbu amalni bajarishga ruxsat bermaydi. "
                       f"Talab qilinadigan rollar: {', '.join(allowed_names)}."
            )
        return role
    return role_checker
