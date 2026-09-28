import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import accessible_org_ids, get_current_user, grant_org_access, require_org_path_access
from app.core.rbac import UserRole, require_roles, require_system_reset_enabled, ROLE_LABELS
from app.models.user import User
from app.models.organization import Organization
from app.models.account import AccountingMode
from app.models.audit_log import AuditLog
from app.services.accounting_engine import AccountingEngine
from app.services.tax_engine import TaxEngine
from app.schemas.organization import OrganizationRead, OrganizationCreate, OrganizationUpdate, OrganizationLockRequest
from app.schemas.audit_log import AuditLogRead, StornoRequest

router = APIRouter()

class ModeToggleRequest(BaseModel):
    mode: AccountingMode

@router.get("/tax/rules")
async def get_tax_rules():
    """
    Returns active and historical Uzbekistan VAT (QQS) rules matrix.
    """
    return TaxEngine.get_all_rules()

@router.get("", response_model=List[OrganizationRead])
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the organizations the current user may access.
    """
    q = select(Organization).order_by(Organization.name)
    allowed = await accessible_org_ids(db, current_user)
    if allowed is not None:
        q = q.where(Organization.id.in_(allowed))
    results = (await db.execute(q)).scalars().all()
    return results

@router.get("/{org_id}", response_model=OrganizationRead, dependencies=[Depends(require_org_path_access)])
async def get_organization(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    q = select(Organization).where(Organization.id == org_id)
    org = (await db.execute(q)).scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Tashkilot topilmadi")
    return org

@router.post("", response_model=OrganizationRead)
async def create_organization(
    data: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_role: UserRole = Depends(require_roles([UserRole.CHIEF_ACCOUNTANT, UserRole.DIRECTOR]))
):
    existing = await db.execute(select(Organization).where(Organization.inn == data.inn))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Ushbu STIR bilan ro'yxatdan o'tgan korxona mavjud")

    org = Organization(
        name=data.name,
        inn=data.inn,
        mode=data.mode,
        vat_payer=data.vat_payer,
        locked_until_date=data.locked_until_date
    )
    db.add(org)
    await db.flush()
    await grant_org_access(db, current_user, org.id)
    await db.commit()
    await db.refresh(org)
    return org

@router.patch("/{org_id}/mode", response_model=OrganizationRead, dependencies=[Depends(require_org_path_access)])
async def toggle_organization_mode(
    org_id: uuid.UUID,
    payload: ModeToggleRequest,
    db: AsyncSession = Depends(get_db),
    current_role: UserRole = Depends(require_roles([UserRole.CHIEF_ACCOUNTANT]))
):
    """
    Toggles between SIMPLE (Oddiy) and BHMS (Professional schotlar rejasi) mode
    without breaking historical data. Protected: CHIEF_ACCOUNTANT only.
    """
    q = select(Organization).where(Organization.id == org_id)
    org = (await db.execute(q)).scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Tashkilot topilmadi")

    org.mode = payload.mode
    log = AuditLog(
        organization_id=org.id,
        action="MODE_TOGGLE",
        entity_type="organization",
        entity_id=str(org.id),
        performed_by=ROLE_LABELS.get(current_role, "Bosh Buxgalter"),
        details=f"Buxgalteriya rejimi {payload.mode.value} ga o'zgartirildi."
    )
    db.add(log)
    await db.commit()
    await db.refresh(org)
    return org

@router.patch("/{org_id}/lock-period", response_model=OrganizationRead, dependencies=[Depends(require_org_path_access)])
async def lock_organization_period(
    org_id: uuid.UUID,
    payload: OrganizationLockRequest,
    db: AsyncSession = Depends(get_db),
    current_role: UserRole = Depends(require_roles([UserRole.CHIEF_ACCOUNTANT]))
):
    """
    Locks or unlocks a financial accounting period.
    Any transactions prior to or on locked_until_date cannot be modified or added.
    Protected: CHIEF_ACCOUNTANT only.
    """
    q = select(Organization).where(Organization.id == org_id)
    org = (await db.execute(q)).scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Tashkilot topilmadi")

    org.locked_until_date = payload.locked_until_date

    action = "LOCK_PERIOD" if payload.locked_until_date else "UNLOCK_PERIOD"
    details = (
        f"Hisobot davri {payload.locked_until_date} sanasigacha qulflandi."
        if payload.locked_until_date
        else "Hisobot davri qulfi ochildi."
    )
    log = AuditLog(
        organization_id=org.id,
        action=action,
        entity_type="organization",
        entity_id=str(org.id),
        performed_by=ROLE_LABELS.get(current_role, "Bosh Buxgalter"),
        details=details
    )
    db.add(log)
    await db.commit()
    await db.refresh(org)
    return org

@router.post("/{org_id}/transactions/{tx_id}/storno", dependencies=[Depends(require_org_path_access)])
async def storno_transaction_endpoint(
    org_id: uuid.UUID,
    tx_id: uuid.UUID,
    payload: StornoRequest,
    db: AsyncSession = Depends(get_db),
    current_role: UserRole = Depends(require_roles([UserRole.CHIEF_ACCOUNTANT]))
):
    """
    Performs an immutable Storno (reversal entry) on a financial transaction.
    Protected: CHIEF_ACCOUNTANT only.
    """
    try:
        res = await AccountingEngine.storno_transaction(
            session=db,
            organization_id=org_id,
            transaction_id=tx_id,
            reason=payload.reason,
            performed_by=payload.performed_by or ROLE_LABELS.get(current_role, "Bosh Buxgalter")
        )
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.get("/{org_id}/audit-logs", response_model=List[AuditLogRead], dependencies=[Depends(require_org_path_access)])
async def list_audit_logs(
    org_id: uuid.UUID,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves the chronological audit trail and activity log for the organization.
    """
    q = select(AuditLog).where(AuditLog.organization_id == org_id).order_by(AuditLog.created_at.desc()).limit(limit)
    return (await db.execute(q)).scalars().all()

@router.post("/{org_id}/reset-data", dependencies=[Depends(require_org_path_access)])
async def reset_org_data(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_role: UserRole = Depends(require_roles([UserRole.CHIEF_ACCOUNTANT, UserRole.DIRECTOR])),
    _reset_enabled: None = Depends(require_system_reset_enabled)
):
    """
    Cleans all transactions, inventory, counterparties, and logs for this organization.
    Requires ALLOW_SYSTEM_RESET=True; writes an organization backup first.
    """
    from app.core.reset_database import reset_organization_with_backup
    try:
        return await reset_organization_with_backup(
            session=db, org_id=org_id, performed_by=ROLE_LABELS.get(current_role, "Bosh Buxgalter")
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


