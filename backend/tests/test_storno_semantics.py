"""Audit finding M6: a red storno must not rewrite the original (possibly already reported) period."""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.organization import Organization
from app.models.transaction import Transaction
from app.services.accounting_engine import AccountingEngine

YEAR_2025 = (date(2025, 1, 1), date(2025, 12, 31))


async def _org(session) -> Organization:
    return (await session.execute(select(Organization))).scalars().first()


async def _post_receipt(session, org) -> Transaction:
    tx = Transaction(
        id=uuid.uuid4(), organization_id=org.id, doc_number="INV-9", doc_date=date(2025, 3, 1), doc_type="EHF",
        debit_account="2900", credit_account="6000", quantity=Decimal("10"), total_amount=Decimal("1000000.00"),
    )
    session.add(tx)
    await session.commit()
    return tx


async def _storno(session, org, tx_id):
    return await AccountingEngine.storno_transaction(session, org.id, tx_id, reason="Xato summa", performed_by="Test")


@pytest.mark.asyncio
async def test_original_period_is_not_rewritten_by_storno(db_session):
    org = await _org(db_session)
    tx = await _post_receipt(db_session, org)

    await _storno(db_session, org, tx.id)

    osv_2025 = await AccountingEngine.calculate_oborotka(db_session, org.id, *YEAR_2025)
    assert osv_2025.total_turnover_debit == Decimal("1000000.00")


@pytest.mark.asyncio
async def test_storno_entry_offsets_the_original_in_its_own_period(db_session):
    org = await _org(db_session)
    tx = await _post_receipt(db_session, org)

    await _storno(db_session, org, tx.id)

    today_period = await AccountingEngine.calculate_oborotka(db_session, org.id, date.today(), date.today())
    assert today_period.total_turnover_debit == Decimal("-1000000.00")
    cumulative = await AccountingEngine.calculate_oborotka(db_session, org.id, date(2025, 1, 1), date.today())
    assert cumulative.total_turnover_debit == Decimal("0.00")


@pytest.mark.asyncio
async def test_storno_cannot_be_applied_twice_or_to_a_storno_entry(db_session):
    org = await _org(db_session)
    tx = await _post_receipt(db_session, org)
    result = await _storno(db_session, org, tx.id)

    with pytest.raises(ValueError):
        await _storno(db_session, org, tx.id)
    with pytest.raises(ValueError):
        await _storno(db_session, org, uuid.UUID(result["storno_transaction_id"]))


@pytest.mark.asyncio
async def test_material_report_reflects_storno_in_storno_period(db_session):
    from app.models.inventory import InventoryItem
    org = await _org(db_session)
    item = (await db_session.execute(select(InventoryItem).where(InventoryItem.organization_id == org.id))).scalars().first()
    tx = Transaction(
        id=uuid.uuid4(), organization_id=org.id, item_id=item.id, doc_number="K-9", doc_date=date(2025, 3, 1),
        doc_type="EHF", debit_account="2900", credit_account="6000", quantity=Decimal("10"),
        total_amount=Decimal("1000000.00"),
    )
    db_session.add(tx)
    await db_session.commit()

    await _storno(db_session, org, tx.id)

    in_2025 = (await AccountingEngine.calculate_material_report(db_session, org.id, *YEAR_2025, item_id=item.id)).items[0]
    now = (await AccountingEngine.calculate_material_report(db_session, org.id, date.today(), date.today(), item_id=item.id)).items[0]
    assert in_2025.final_qty == Decimal("10.000")
    assert now.final_qty == Decimal("0.000")
