import os
import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.auth import accessible_org_ids, ensure_org_access, filter_by_orgs, get_current_user
from app.models.user import User
from app.core.database import get_db
from app.core.rbac import UserRole, require_roles, ROLE_LABELS
from app.core.storage import InvalidStoragePath, resolve_backup_path
from app.services.backup_engine import BackupEngine

router = APIRouter()

class CreateBackupRequest(BaseModel):
    organization_id: Optional[uuid.UUID] = None

@router.post("/create")
async def create_system_backup(
    payload: Optional[CreateBackupRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_role: UserRole = Depends(require_roles([UserRole.CHIEF_ACCOUNTANT]))
):
    """
    Creates a SHA256 checksum-verified snapshot of one organization (or of the
    whole database, superuser only). Protected: CHIEF_ACCOUNTANT.
    """
    org_id = payload.organization_id if payload else None
    if org_id is None:
        if not current_user.is_superuser:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="To'liq baza nusxasi faqat administrator uchun")
    else:
        await ensure_org_access(db, current_user, org_id)
    res = await BackupEngine.create_backup(
        session=db,
        organization_id=org_id,
        created_by=ROLE_LABELS.get(current_role, "Bosh Buxgalter")
    )
    return res

@router.get("/list", response_model=List[Dict[str, Any]])
async def list_system_backups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_role: UserRole = Depends(require_roles([UserRole.CHIEF_ACCOUNTANT, UserRole.AUDITOR, UserRole.DIRECTOR]))
):
    """
    Returns the snapshots of organizations the caller can access (all for a superuser).
    """
    return filter_by_orgs(await accessible_org_ids(db, current_user), BackupEngine.list_backups())


async def _ensure_backup_access(db: AsyncSession, user: User, filename: str) -> None:
    try:
        owner = BackupEngine.backup_organization_id(filename)
    except InvalidStoragePath as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zaxira fayli topilmadi")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Zaxira fayli buzilgan")
    if user.is_superuser:
        return
    try:
        owner_id = uuid.UUID(owner)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zaxira fayli topilmadi")
    await ensure_org_access(db, user, owner_id)

@router.get("/{filename}/verify")
async def verify_backup_integrity(
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_role: UserRole = Depends(require_roles([UserRole.CHIEF_ACCOUNTANT, UserRole.AUDITOR]))
):
    """
    Verifies cryptographic hash and JSON structural integrity of a backup snapshot.
    """
    await _ensure_backup_access(db, current_user, filename)
    try:
        return BackupEngine.verify_backup(filename)
    except FileNotFoundError as fe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fe))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Xatolik: {str(e)}")

@router.get("/{filename}/download")
async def download_backup_file(
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_role: UserRole = Depends(require_roles([UserRole.CHIEF_ACCOUNTANT]))
):
    """
    Securely downloads the raw backup file. Protected: CHIEF_ACCOUNTANT with access to its organization.
    """
    await _ensure_backup_access(db, current_user, filename)
    try:
        fp = resolve_backup_path(filename)
    except InvalidStoragePath as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    safe_filename = os.path.basename(fp)
    if not os.path.exists(fp):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zaxira fayli topilmadi")

    return FileResponse(
        path=fp,
        media_type="application/json",
        filename=safe_filename
    )
