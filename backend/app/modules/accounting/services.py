import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Sequence, List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounting.models import (
    Organization,
    ChartOfAccount,
    Counterparty,
    InventoryItem,
    Transaction,
    AccountingMode,
    AccountType
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
from app.modules.accounting.repositories import (
    OrganizationRepository,
    AccountRepository,
    CounterpartyRepository,
    InventoryRepository,
    TransactionRepository
)

class AccountingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.org_repo = OrganizationRepository(session)
        self.account_repo = AccountRepository(session)
        self.counterparty_repo = CounterpartyRepository(session)
        self.inventory_repo = InventoryRepository(session)
        self.tx_repo = TransactionRepository(session)

    # --- Organization Logic ---
    async def create_organization(self, data: OrganizationCreate) -> Organization:
        existing = await self.org_repo.get_by_inn(data.inn)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tashkilot STIR {data.inn} allaqachon mavjud."
            )
        return await self.org_repo.create(data)

    async def get_organization(self, org_id: uuid.UUID) -> Organization:
        org = await self.org_repo.get_by_id(org_id)
        if not org:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tashkilot topilmadi.")
        return org

    async def list_organizations(self) -> Sequence[Organization]:
        return await self.org_repo.list_all()

    async def update_organization(self, org_id: uuid.UUID, data: OrganizationUpdate) -> Organization:
        org = await self.get_organization(org_id)
        return await self.org_repo.update(org, data)

    # --- Counterparty Logic ---
    async def get_or_create_counterparty(
        self,
        org_id: uuid.UUID,
        name: str,
        inn: Optional[str] = None,
        is_supplier: bool = True,
        is_client: bool = False
    ) -> Counterparty:
        if inn:
            existing = await self.counterparty_repo.get_by_inn(org_id, inn)
            if existing:
                return existing
        cp_data = CounterpartyCreate(
            organization_id=org_id,
            name=name,
            inn=inn,
            is_supplier=is_supplier,
            is_client=is_client
        )
        return await self.counterparty_repo.create(cp_data)

    # --- Inventory Item Logic ---
    async def get_or_create_inventory_item(
        self,
        org_id: uuid.UUID,
        name: str,
        ikpu_code: Optional[str] = None,
        unit: str = "dona"
    ) -> InventoryItem:
        existing = await self.inventory_repo.find_matching_item(org_id, name, ikpu_code)
        if existing:
            return existing
        item_data = InventoryItemCreate(
            organization_id=org_id,
            name=name,
            ikpu_code=ikpu_code,
            unit=unit
        )
        return await self.inventory_repo.create(item_data)

    # --- Transaction & Double Entry Logic ---
    async def record_transaction(self, tx_data: TransactionCreate) -> Transaction:
        org = await self.get_organization(tx_data.organization_id)

        # 1. Period Lock Validation
        if org.locked_until_date and tx_data.doc_date <= org.locked_until_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Hisobot davri {org.locked_until_date} gacha yopilgan. Ushbu sanada tranzaksiya kiritish taqiqlangan."
            )

        # 2. Dual Mode Enforcement
        if org.mode == AccountingMode.BHMS:
            if not tx_data.debit_account or not tx_data.credit_account:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="BHMS rejimida Debit va Kredit schotlari ko'rsatilishi shart."
                )
            # Verify accounts exist
            deb = await self.account_repo.get_by_code(tx_data.debit_account)
            kred = await self.account_repo.get_by_code(tx_data.credit_account)
            if not deb or not kred:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ko'rsatilgan schot(lar) BHMS schotlar rejasida mavjud emas: {tx_data.debit_account}, {tx_data.credit_account}"
                )
        else:
            # SIMPLE mode: auto-fallback if accounts not provided
            if not tx_data.debit_account or not tx_data.credit_account:
                if tx_data.doc_type == "EHF":
                    tx_data.debit_account = tx_data.debit_account or "2900"
                    tx_data.credit_account = tx_data.credit_account or "6000"
                elif tx_data.doc_type in ["BANK_PAYMENT", "BANK"]:
                    tx_data.debit_account = tx_data.debit_account or "6000"
                    tx_data.credit_account = tx_data.credit_account or "5110"
                else:
                    tx_data.debit_account = tx_data.debit_account or "1000"
                    tx_data.credit_account = tx_data.credit_account or "6000"

        # 3. Mathematical precision: ensure Decimal calculations
        qty = Decimal(str(tx_data.quantity))
        price = Decimal(str(tx_data.price))
        vat_rate = Decimal(str(tx_data.vat_rate))
        total = Decimal(str(tx_data.total_amount))

        if vat_rate > 0 and tx_data.vat_amount == 0:
            calc_vat = (qty * price * (vat_rate / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            tx_data.vat_amount = calc_vat

        return await self.tx_repo.create(tx_data)

    async def create_storno_reversal(
        self,
        tx_id: uuid.UUID,
        reason: str = "Xatolik tuzatish (Storno)"
    ) -> Transaction:
        """Create a red-storno reversal for an existing transaction."""
        original = await self.tx_repo.get_by_id(tx_id)
        if not original:
            raise HTTPException(status_code=404, detail="Tranzaksiya topilmadi.")
        if original.is_reversed:
            raise HTTPException(status_code=400, detail="Ushbu tranzaksiya allaqachon storno qilingan.")

        org = await self.get_organization(original.organization_id)
        if org.locked_until_date and original.doc_date <= org.locked_until_date:
            raise HTTPException(
                status_code=400,
                detail=f"Davr yopilgan ({org.locked_until_date}). Storno operatsiyasini bajarib bo'lmaydi."
            )

        storno_data = TransactionCreate(
            organization_id=original.organization_id,
            doc_number=f"STORNO-{original.doc_number or str(original.id)[:8]}",
            doc_date=original.doc_date,
            doc_type=original.doc_type,
            debit_account=original.debit_account,
            credit_account=original.credit_account,
            counterparty_id=original.counterparty_id,
            item_id=original.item_id,
            quantity=-abs(original.quantity),
            price=original.price,
            vat_rate=original.vat_rate,
            vat_amount=-abs(original.vat_amount),
            total_amount=-abs(original.total_amount),
            description=f"STORNO: {reason} (Asl tranzaksiya: {original.id})"
        )

        storno_tx = await self.tx_repo.create(storno_data)
        storno_tx.is_reversed = True
        storno_tx.reversal_ref_id = original.id
        storno_tx.reversal_reason = reason

        original.is_reversed = True
        original.reversal_ref_id = storno_tx.id
        original.reversal_reason = reason

        await self.session.flush()
        return storno_tx

    async def list_transactions(self, filter_params: TransactionFilter) -> Sequence[Transaction]:
        return await self.tx_repo.list_by_filter(filter_params)
