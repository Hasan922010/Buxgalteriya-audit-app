from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.core.auth import require_org_path_access, require_superuser
from app.models.user import User
from app.core.database import get_db
from app.core.rbac import ROLE_LABELS, UserRole, require_roles, require_system_reset_enabled
from app.core.reset_database import ResetAfterBackupError, factory_reset_with_backup, reset_organization_with_backup

router = APIRouter(dependencies=[Depends(require_system_reset_enabled)])

class FactoryResetRequest(BaseModel):
    confirmation: str

class OrgResetRequest(BaseModel):
    confirmation: bool = True

@router.post("/factory-reset")
async def factory_reset_system(
    payload: FactoryResetRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_superuser),
    current_role: UserRole = Depends(require_roles([UserRole.CHIEF_ACCOUNTANT]))
):
    """
    Cleans the entire database: removes all organizations, transactions,
    counterparties, inventory, documents, and audit logs.
    Re-seeds standard Uzbekistan BHMS Chart of Accounts and creates a fresh Demo organization.
    Requires ALLOW_SYSTEM_RESET=True and typing 'TOZALASH' or 'RESET' to confirm.
    A full backup is written before anything is deleted.
    """
    clean_confirm = payload.confirmation.strip().upper()
    if clean_confirm not in ["TOZALASH", "RESET"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tasdiqlash kodi noto'g'ri. Tizimni noldan tozalash uchun 'TOZALASH' yoki 'RESET' so'zini kiriting."
        )

    try:
        return await factory_reset_with_backup(session=db, performed_by=ROLE_LABELS[current_role])
    except ResetAfterBackupError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Zaxira nusxasi yaratilmadi, hech narsa o'chirilmadi: {e}")

@router.post("/organizations/{org_id}/reset-data", dependencies=[Depends(require_org_path_access)])
async def reset_organization_endpoint(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_role: UserRole = Depends(require_roles([UserRole.CHIEF_ACCOUNTANT, UserRole.DIRECTOR]))
):
    """
    Resets all transactions, inventory, counterparties, and logs for a specific organization,
    while preserving the organization profile and BHMS chart of accounts.
    An organization backup is written before anything is deleted.
    """
    try:
        return await reset_organization_with_backup(session=db, org_id=org_id, performed_by=ROLE_LABELS[current_role])
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except ResetAfterBackupError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tozalashda xatolik: {e}")
