import pytest
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from fastapi import HTTPException

from app.models.organization import Organization
from app.models.counterparty import Counterparty
from app.models.inventory import InventoryItem
from app.models.transaction import Transaction
from app.modules.accounting.services import AccountingService
from app.modules.accounting.schemas import TransactionCreate
from app.modules.reports.services import ReportingService

@pytest.mark.asyncio
async def test_double_entry_balance_and_decimal_math(db_session):
    """
    Verifies that every recorded transaction strictly enforces Decimal precision
    and maintains double-entry equality (Debit == Credit).
    """
    accounting_service = AccountingService(db_session)
    reporting_service = ReportingService(db_session)

    # 1. Fetch seeded org
    org_res = await db_session.execute(select(Organization))
    org = org_res.scalar_one()

    # 2. Record Purchase Transaction: Kirim (Debit: 2900 Tovarlar, Credit: 6000 Mol yetkazib beruvchilar)
    tx1_data = TransactionCreate(
        organization_id=org.id,
        doc_number="PUR-001",
        doc_date=date(2025, 2, 1),
        doc_type="EHF",
        debit_account="2900",
        credit_account="6000",
        quantity=Decimal("15.500"),
        price=Decimal("1250000.75"),
        vat_rate=Decimal("12.00"),
        vat_amount=Decimal("2325001.40"),
        total_amount=Decimal("21700013.03"),
        description="Tovar xaridi"
    )
    tx1 = await accounting_service.record_transaction(tx1_data)
    assert tx1.id is not None
    assert isinstance(tx1.total_amount, Decimal)
    assert tx1.debit_account == "2900"
    assert tx1.credit_account == "6000"

    # 3. Record Bank Payment to Supplier: Chiqim (Debit: 6000, Credit: 5110 Bank)
    tx2_data = TransactionCreate(
        organization_id=org.id,
        doc_number="BANK-001",
        doc_date=date(2025, 2, 5),
        doc_type="BANK_PAYMENT",
        debit_account="6000",
        credit_account="5110",
        quantity=Decimal("0"),
        price=Decimal("0"),
        total_amount=Decimal("21700013.03"),
        description="Ta'minotchiga to'lov"
    )
    tx2 = await accounting_service.record_transaction(tx2_data)
    assert tx2.id is not None

    # 4. Record Sales Revenue: Realizatsiya (Debit: 4000 Xaridorlar, Credit: 9000 Daromad)
    tx3_data = TransactionCreate(
        organization_id=org.id,
        doc_number="SALE-001",
        doc_date=date(2025, 2, 10),
        doc_type="EHF",
        debit_account="4000",
        credit_account="9000",
        quantity=Decimal("10.000"),
        price=Decimal("2500000.00"),
        vat_rate=Decimal("12.00"),
        vat_amount=Decimal("3000000.00"),
        total_amount=Decimal("28000000.00"),
        description="Mahsulot sotildi"
    )
    tx3 = await accounting_service.record_transaction(tx3_data)
    assert tx3.id is not None

    await db_session.commit()

    # 5. Verify Trial Balance (OSV) Mathematical Integrity: Total Debit == Total Credit
    osv = await reporting_service.get_trial_balance(
        organization_id=org.id,
        from_date=date(2025, 1, 1),
        to_date=date(2025, 12, 31)
    )

    # Enforce trial balance equality: Total Turnover Debit == Total Turnover Credit
    turnover_debit = getattr(osv, "total_turnover_debit", None) or getattr(osv, "total_period_debit", Decimal("0"))
    turnover_credit = getattr(osv, "total_turnover_credit", None) or getattr(osv, "total_period_credit", Decimal("0"))
    assert turnover_debit == turnover_credit, f"Trial balance mismatch: {turnover_debit} != {turnover_credit}"

    # Enforce final balances equality
    assert osv.total_final_debit == osv.total_final_credit, f"Final balance mismatch: {osv.total_final_debit} != {osv.total_final_credit}"
    assert osv.is_balanced is True

@pytest.mark.asyncio
async def test_period_lock_enforcement(db_session):
    """
    Verifies that backdated transactions prior to or on locked_until_date are strictly rejected.
    """
    accounting_service = AccountingService(db_session)
    org_res = await db_session.execute(select(Organization))
    org = org_res.scalar_one()

    # Lock period up to 2025-01-31
    org.locked_until_date = date(2025, 1, 31)
    await db_session.commit()

    # Attempt to post in locked period (2025-01-15)
    tx_blocked = TransactionCreate(
        organization_id=org.id,
        doc_number="LOCK-TEST",
        doc_date=date(2025, 1, 15),
        doc_type="EHF",
        debit_account="2900",
        credit_account="6000",
        total_amount=Decimal("5000000.00")
    )
    with pytest.raises(HTTPException) as exc_info:
        await accounting_service.record_transaction(tx_blocked)
    assert exc_info.value.status_code == 400
    assert "yopilgan" in exc_info.value.detail

@pytest.mark.asyncio
async def test_storno_reversal_balance(db_session):
    """
    Verifies that a Storno reversal creates equal negative entries,
    bringing the net ledger balance back to zero.
    """
    accounting_service = AccountingService(db_session)
    org_res = await db_session.execute(select(Organization))
    org = org_res.scalar_one()
    org.locked_until_date = None
    await db_session.commit()

    # Record initial transaction
    tx_orig_data = TransactionCreate(
        organization_id=org.id,
        doc_number="ERR-001",
        doc_date=date(2025, 3, 1),
        doc_type="EHF",
        debit_account="1000",
        credit_account="6000",
        quantity=Decimal("5.0"),
        price=Decimal("100000.00"),
        total_amount=Decimal("500000.00"),
        description="Xato kiritilgan xarid"
    )
    tx_orig = await accounting_service.record_transaction(tx_orig_data)
    await db_session.commit()

    # Create Storno
    storno_tx = await accounting_service.create_storno_reversal(tx_orig.id, reason="Noto'g'ri summa")
    assert storno_tx.is_reversed is True
    assert storno_tx.total_amount == -Decimal("500000.00")
    assert storno_tx.reversal_ref_id == tx_orig.id
    assert tx_orig.is_reversed is True

    # Net sum of both transactions must be exactly zero
    assert (tx_orig.total_amount + storno_tx.total_amount) == Decimal("0.00")
