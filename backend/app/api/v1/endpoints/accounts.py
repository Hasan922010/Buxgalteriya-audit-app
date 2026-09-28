from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.models.account import ChartOfAccount, AccountType

router = APIRouter()

class AccountRead(BaseModel):
    code: str
    name: str
    account_type: str
    is_active: bool

    model_config = {"from_attributes": True}


@router.get("", response_model=List[AccountRead])
async def list_accounts(
    search: Optional[str] = Query(None),
    account_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns standard Uzbekistan BHMS Chart of Accounts.
    """
    q = select(ChartOfAccount).where(ChartOfAccount.is_active == True)
    if search:
        q = q.where(ChartOfAccount.code.like(f"%{search}%") | ChartOfAccount.name.ilike(f"%{search}%"))
    if account_type:
        q = q.where(ChartOfAccount.account_type == account_type)
    q = q.order_by(ChartOfAccount.code)
    results = (await db.execute(q)).scalars().all()
    return results
