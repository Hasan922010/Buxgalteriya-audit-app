"""Regression tests for audit finding H1: material report opening balance / negative stock."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.inventory import InventoryItem
from app.models.organization import Organization
from app.models.transaction import Transaction
from app.services.accounting_engine import AccountingEngine

MARCH = (date(2025, 3, 1), date(2025, 3, 31))


async def _org_and_item(session):
    org = (await session.execute(select(Organization))).scalars().first()
    item = (await session.execute(select(InventoryItem).where(InventoryItem.organization_id == org.id))).scalars().first()
    return org, item


def _tx(org, item, day, qty, total, doc_type, debit, credit, number):
    return Transaction(
        organization_id=org.id, item_id=item.id, doc_number=number, doc_date=day, doc_type=doc_type,
        debit_account=debit, credit_account=credit, quantity=Decimal(qty), total_amount=Decimal(total),
    )


def _purchase(org, item, day, qty, total, n="K"):
    return _tx(org, item, day, qty, total, "EHF", "2900", "6000", n)


async def _report_row(session, org, item):
    rep = await AccountingEngine.calculate_material_report(session, org.id, *MARCH, item_id=item.id)
    return rep.items[0]


@pytest.mark.asyncio
async def test_sale_before_period_reduces_opening_stock(db_session):
    """A retail sale (5000/9000, sale price) before the period must not be counted as an inflow."""
    org, item = await _org_and_item(db_session)
    db_session.add_all([
        _purchase(org, item, date(2025, 2, 1), "100", "5000000.00"),                 # 100 @ 50 000
        _tx(org, item, date(2025, 2, 10), "40", "3200000.00", "SOLIQ_SALES", "5000", "9000", "S-1"),  # sold @ 80 000
    ])
    await db_session.commit()

    row = await _report_row(db_session, org, item)

    assert row.initial_qty == Decimal("60.000")
    assert row.initial_sum == Decimal("3000000.00")  # at cost, not at sale price


@pytest.mark.asyncio
async def test_prior_outflow_is_costed_at_running_average(db_session):
    org, item = await _org_and_item(db_session)
    db_session.add_all([
        _purchase(org, item, date(2025, 1, 5), "100", "5000000.00", "K-1"),   # 100 @ 50 000
        _purchase(org, item, date(2025, 1, 20), "100", "7000000.00", "K-2"),  # 100 @ 70 000 -> avg 60 000
        # dispatch recorded with a wrong amount; cost must come from the running average
        _tx(org, item, date(2025, 2, 1), "50", "1.00", "STOCK", "9100", "2900", "CH-1"),
    ])
    await db_session.commit()

    row = await _report_row(db_session, org, item)

    assert row.initial_qty == Decimal("150.000")
    assert row.initial_sum == Decimal("9000000.00")  # 12 000 000 - 50 * 60 000


@pytest.mark.asyncio
async def test_unrelated_transactions_do_not_change_stock(db_session):
    """A payment linked to the item (bank 5110/6000) is neither an inflow nor an outflow."""
    org, item = await _org_and_item(db_session)
    db_session.add_all([
        _purchase(org, item, date(2025, 2, 1), "10", "100000.00"),
        _tx(org, item, date(2025, 2, 5), "10", "100000.00", "BANK", "6000", "5110", "B-1"),
    ])
    await db_session.commit()

    row = await _report_row(db_session, org, item)

    assert row.initial_qty == Decimal("10.000")
    assert row.initial_sum == Decimal("100000.00")


@pytest.mark.asyncio
async def test_negative_stock_is_reported_not_hidden(db_session):
    org, item = await _org_and_item(db_session)
    db_session.add_all([
        _purchase(org, item, date(2025, 3, 2), "10", "100000.00"),
        _tx(org, item, date(2025, 3, 5), "15", "1.00", "STOCK", "9100", "2900", "CH-1"),
    ])
    await db_session.commit()

    row = await _report_row(db_session, org, item)

    assert row.final_qty == Decimal("-5.000")
    assert row.has_negative_stock is True


@pytest.mark.asyncio
async def test_period_figures_unchanged_for_simple_case(db_session):
    org, item = await _org_and_item(db_session)
    db_session.add_all([
        _purchase(org, item, date(2025, 3, 1), "100", "5000000.00", "K-1"),
        _purchase(org, item, date(2025, 3, 5), "100", "7000000.00", "K-2"),
        _tx(org, item, date(2025, 3, 10), "50", "3000000.00", "STOCK", "9100", "2900", "CH-1"),
    ])
    await db_session.commit()

    row = await _report_row(db_session, org, item)

    assert (row.inflow_qty, row.inflow_sum) == (Decimal("200.000"), Decimal("12000000.00"))
    assert (row.outflow_qty, row.outflow_sum) == (Decimal("50.000"), Decimal("3000000.00"))
    assert (row.final_qty, row.final_sum) == (Decimal("150.000"), Decimal("9000000.00"))
    assert row.has_negative_stock is False
