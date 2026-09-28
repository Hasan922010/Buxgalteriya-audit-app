import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.accounting.schemas import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationOut,
    ChartOfAccountOut,
    CounterpartyCreate,
    CounterpartyUpdate,
    CounterpartyOut,
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemOut,
    TransactionCreate,
    TransactionOut,
    TransactionFilter
)
from app.modules.accounting.services import AccountingService

router = APIRouter()

# --- Organizations ---
@router.post("/organizations", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
async def create_organization(data: OrganizationCreate, db: AsyncSession = Depends(get_db)):
    service = AccountingService(db)
    return await service.create_organization(data)

@router.get("/organizations", response_model=List[OrganizationOut])
async def list_organizations(db: AsyncSession = Depends(get_db)):
    service = AccountingService(db)
    return await service.list_organizations()

@router.get("/organizations/{org_id}", response_model=OrganizationOut)
async def get_organization(org_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = AccountingService(db)
    return await service.get_organization(org_id)

@router.patch("/organizations/{org_id}", response_model=OrganizationOut)
async def update_organization(org_id: uuid.UUID, data: OrganizationUpdate, db: AsyncSession = Depends(get_db)):
    service = AccountingService(db)
    return await service.update_organization(org_id, data)

# --- Accounts ---
@router.get("/accounts", response_model=List[ChartOfAccountOut])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    service = AccountingService(db)
    return await service.account_repo.list_all()

# --- Counterparties ---
@router.post("/counterparties", response_model=CounterpartyOut, status_code=status.HTTP_201_CREATED)
async def create_counterparty(data: CounterpartyCreate, db: AsyncSession = Depends(get_db)):
    service = AccountingService(db)
    return await service.counterparty_repo.create(data)

@router.get("/counterparties", response_model=List[CounterpartyOut])
async def list_counterparties(organization_id: uuid.UUID = Query(...), db: AsyncSession = Depends(get_db)):
    service = AccountingService(db)
    return await service.counterparty_repo.list_by_org(organization_id)

# --- Inventory Items ---
@router.post("/inventory", response_model=InventoryItemOut, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(data: InventoryItemCreate, db: AsyncSession = Depends(get_db)):
    service = AccountingService(db)
    return await service.inventory_repo.create(data)

@router.get("/inventory", response_model=List[InventoryItemOut])
async def list_inventory_items(organization_id: uuid.UUID = Query(...), db: AsyncSession = Depends(get_db)):
    service = AccountingService(db)
    return await service.inventory_repo.list_by_org(organization_id)

# --- Transactions ---
@router.post("/transactions", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
async def create_transaction(data: TransactionCreate, db: AsyncSession = Depends(get_db)):
    service = AccountingService(db)
    tx = await service.record_transaction(data)
    return tx

@router.get("/transactions", response_model=List[TransactionOut])
async def list_transactions(
    organization_id: uuid.UUID = Query(...),
    account: Optional[str] = None,
    counterparty_id: Optional[uuid.UUID] = None,
    item_id: Optional[uuid.UUID] = None,
    doc_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    service = AccountingService(db)
    filter_params = TransactionFilter(
        organization_id=organization_id,
        account=account,
        counterparty_id=counterparty_id,
        item_id=item_id,
        doc_type=doc_type
    )
    return await service.list_transactions(filter_params)

@router.post("/transactions/{tx_id}/storno", response_model=TransactionOut)
async def storno_transaction(
    tx_id: uuid.UUID,
    reason: str = Query("Xatolik tuzatish (Storno)"),
    db: AsyncSession = Depends(get_db)
):
    service = AccountingService(db)
    return await service.create_storno_reversal(tx_id, reason=reason)
