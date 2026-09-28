import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import ensure_org_access, get_current_user, require_org_query_access
from app.core.database import get_db
from app.models.user import User
from app.models.counterparty import Counterparty
from app.schemas.counterparty import CounterpartyRead, CounterpartyCreate

router = APIRouter()

@router.get("", response_model=List[CounterpartyRead], dependencies=[Depends(require_org_query_access)])
async def list_counterparties(
    organization_id: uuid.UUID = Query(...),
    search: Optional[str] = Query(None),
    is_supplier: Optional[bool] = Query(None),
    is_client: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns list of counterparties for the specified organization.
    """
    q = select(Counterparty).where(Counterparty.organization_id == organization_id)
    if search:
        q = q.where(Counterparty.name.ilike(f"%{search}%") | Counterparty.inn.like(f"%{search}%"))
    if is_supplier is not None:
        q = q.where(Counterparty.is_supplier == is_supplier)
    if is_client is not None:
        q = q.where(Counterparty.is_client == is_client)
    q = q.order_by(Counterparty.name)
    results = (await db.execute(q)).scalars().all()
    return results

@router.post("", response_model=CounterpartyRead)
async def create_counterparty(
    data: CounterpartyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new counterparty.
    """
    await ensure_org_access(db, current_user, data.organization_id)
    cp = Counterparty(
        organization_id=data.organization_id,
        name=data.name,
        inn=data.inn,
        mfo=data.mfo,
        bank_account=data.bank_account,
        is_supplier=data.is_supplier,
        is_client=data.is_client
    )
    db.add(cp)
    await db.commit()
    await db.refresh(cp)
    return cp
