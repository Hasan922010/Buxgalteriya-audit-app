import uuid
from typing import List, Optional, Sequence
from datetime import date
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.accounting.models import (
    Organization,
    ChartOfAccount,
    Counterparty,
    InventoryItem,
    Transaction
)
from app.modules.accounting.schemas import (
    OrganizationCreate,
    OrganizationUpdate,
    CounterpartyCreate,
    CounterpartyUpdate,
    InventoryItemCreate,
    InventoryItemUpdate,
    TransactionCreate,
    TransactionUpdate,
    TransactionFilter
)

class OrganizationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, org_id: uuid.UUID) -> Optional[Organization]:
        result = await self.session.execute(select(Organization).where(Organization.id == org_id))
        return result.scalar_one_or_none()

    async def get_by_inn(self, inn: str) -> Optional[Organization]:
        result = await self.session.execute(select(Organization).where(Organization.inn == inn))
        return result.scalar_one_or_none()

    async def list_all(self) -> Sequence[Organization]:
        result = await self.session.execute(select(Organization).order_by(Organization.name))
        return result.scalars().all()

    async def create(self, data: OrganizationCreate) -> Organization:
        org = Organization(**data.model_dump())
        self.session.add(org)
        await self.session.flush()
        await self.session.refresh(org)
        return org

    async def update(self, org: Organization, data: OrganizationUpdate) -> Organization:
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(org, k, v)
        await self.session.flush()
        await self.session.refresh(org)
        return org


class AccountRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_code(self, code: str) -> Optional[ChartOfAccount]:
        result = await self.session.execute(select(ChartOfAccount).where(ChartOfAccount.code == code))
        return result.scalar_one_or_none()

    async def list_all(self, active_only: bool = True) -> Sequence[ChartOfAccount]:
        query = select(ChartOfAccount)
        if active_only:
            query = query.where(ChartOfAccount.is_active == True)
        result = await self.session.execute(query.order_by(ChartOfAccount.code))
        return result.scalars().all()

    async def create_or_update(self, code: str, name: str, account_type, is_active: bool = True) -> ChartOfAccount:
        acc = await self.get_by_code(code)
        if acc:
            acc.name = name
            acc.account_type = account_type
            acc.is_active = is_active
        else:
            acc = ChartOfAccount(code=code, name=name, account_type=account_type, is_active=is_active)
            self.session.add(acc)
        await self.session.flush()
        await self.session.refresh(acc)
        return acc


class CounterpartyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, cp_id: uuid.UUID) -> Optional[Counterparty]:
        result = await self.session.execute(select(Counterparty).where(Counterparty.id == cp_id))
        return result.scalar_one_or_none()

    async def get_by_inn(self, org_id: uuid.UUID, inn: str) -> Optional[Counterparty]:
        result = await self.session.execute(
            select(Counterparty).where(
                and_(Counterparty.organization_id == org_id, Counterparty.inn == inn)
            )
        )
        return result.scalar_one_or_none()

    async def list_by_org(self, org_id: uuid.UUID) -> Sequence[Counterparty]:
        result = await self.session.execute(
            select(Counterparty).where(Counterparty.organization_id == org_id).order_by(Counterparty.name)
        )
        return result.scalars().all()

    async def create(self, data: CounterpartyCreate) -> Counterparty:
        cp = Counterparty(**data.model_dump())
        self.session.add(cp)
        await self.session.flush()
        await self.session.refresh(cp)
        return cp

    async def update(self, cp: Counterparty, data: CounterpartyUpdate) -> Counterparty:
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(cp, k, v)
        await self.session.flush()
        await self.session.refresh(cp)
        return cp


class InventoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, item_id: uuid.UUID) -> Optional[InventoryItem]:
        result = await self.session.execute(select(InventoryItem).where(InventoryItem.id == item_id))
        return result.scalar_one_or_none()

    async def get_by_ikpu(self, org_id: uuid.UUID, ikpu_code: str) -> Optional[InventoryItem]:
        result = await self.session.execute(
            select(InventoryItem).where(
                and_(InventoryItem.organization_id == org_id, InventoryItem.ikpu_code == ikpu_code)
            )
        )
        return result.scalar_one_or_none()

    async def find_matching_item(
        self,
        org_id: uuid.UUID,
        name: str,
        ikpu_code: Optional[str] = None
    ) -> Optional[InventoryItem]:
        """
        Uses ItemDisambiguator to find an existing item without improperly merging
        items with conflicting suffix modifiers or distinct specifications.
        """
        from app.modules.accounting.item_disambiguator import ItemDisambiguator

        # Fetch candidate items from the organization
        stmt = select(InventoryItem).where(InventoryItem.organization_id == org_id)
        if ikpu_code:
            stmt = stmt.where(InventoryItem.ikpu_code == ikpu_code)
        res = await self.session.execute(stmt)
        candidates = list(res.scalars().all())

        if not candidates and ikpu_code:
            # Fallback to check all org items in case IKPU was empty previously
            all_res = await self.session.execute(
                select(InventoryItem).where(InventoryItem.organization_id == org_id)
            )
            candidates = list(all_res.scalars().all())

        return ItemDisambiguator.find_best_match(name, candidates, ikpu_code)

    async def list_by_org(self, org_id: uuid.UUID) -> Sequence[InventoryItem]:
        result = await self.session.execute(
            select(InventoryItem).where(InventoryItem.organization_id == org_id).order_by(InventoryItem.name)
        )
        return result.scalars().all()

    async def create(self, data: InventoryItemCreate) -> InventoryItem:
        item = InventoryItem(**data.model_dump())
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def update(self, item: InventoryItem, data: InventoryItemUpdate) -> InventoryItem:
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(item, k, v)
        await self.session.flush()
        await self.session.refresh(item)
        return item


class TransactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, tx_id: uuid.UUID) -> Optional[Transaction]:
        result = await self.session.execute(
            select(Transaction)
            .options(selectinload(Transaction.counterparty), selectinload(Transaction.item))
            .where(Transaction.id == tx_id)
        )
        return result.scalar_one_or_none()

    async def create(self, data: TransactionCreate) -> Transaction:
        tx = Transaction(**data.model_dump())
        self.session.add(tx)
        await self.session.flush()
        await self.session.refresh(tx)
        return tx

    async def update(self, tx: Transaction, data: TransactionUpdate) -> Transaction:
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(tx, k, v)
        await self.session.flush()
        await self.session.refresh(tx)
        return tx

    async def list_by_filter(self, filter_params: TransactionFilter) -> Sequence[Transaction]:
        query = select(Transaction).where(Transaction.organization_id == filter_params.organization_id)

        if filter_params.from_date:
            query = query.where(Transaction.doc_date >= filter_params.from_date)
        if filter_params.to_date:
            query = query.where(Transaction.doc_date <= filter_params.to_date)
        if filter_params.account:
            query = query.where(
                (Transaction.debit_account == filter_params.account) |
                (Transaction.credit_account == filter_params.account)
            )
        if filter_params.counterparty_id:
            query = query.where(Transaction.counterparty_id == filter_params.counterparty_id)
        if filter_params.item_id:
            query = query.where(Transaction.item_id == filter_params.item_id)
        if filter_params.doc_type:
            query = query.where(Transaction.doc_type == filter_params.doc_type)

        query = query.options(
            selectinload(Transaction.counterparty),
            selectinload(Transaction.item)
        ).order_by(Transaction.doc_date.asc(), Transaction.created_at.asc())

        result = await self.session.execute(query)
        return result.scalars().all()
