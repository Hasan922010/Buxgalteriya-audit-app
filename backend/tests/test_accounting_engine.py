import pytest
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.database import Base
from app.models.account import ChartOfAccount, AccountType, AccountingMode
from app.models.organization import Organization
from app.models.counterparty import Counterparty
from app.models.inventory import InventoryItem
from app.models.transaction import Transaction
from app.services.accounting_engine import AccountingEngine

# Use local test sqlite or postgres
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def test_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        # Seed accounts
        accounts = [
            ChartOfAccount(code="1000", name="Materiallar", account_type=AccountType.ASSET),
            ChartOfAccount(code="2900", name="Tovarlar", account_type=AccountType.ASSET),
            ChartOfAccount(code="4000", name="Xaridorlar", account_type=AccountType.ASSET),
            ChartOfAccount(code="5110", name="Hisob-kitob schoti", account_type=AccountType.ASSET),
            ChartOfAccount(code="6000", name="Mol yetkazib beruvchilar", account_type=AccountType.LIABILITY),
            ChartOfAccount(code="9000", name="Daromadlar", account_type=AccountType.REVENUE),
        ]
        session.add_all(accounts)
        
        # Seed test org
        org = Organization(
            id=uuid.uuid4(),
            name="Test Korxona MCHJ",
            inn="999888777",
            mode=AccountingMode.BHMS,
            vat_payer=True,
            created_at=date(2025, 1, 1)
        )
        session.add(org)

        # Seed test counterparty & item
        cp = Counterparty(
            id=uuid.uuid4(),
            organization_id=org.id,
            name="Test Ta'minotchi",
            inn="111222333",
            is_supplier=True,
            is_client=False
        )
        session.add(cp)

        item = InventoryItem(
            id=uuid.uuid4(),
            organization_id=org.id,
            name="A4 Qog'oz",
            unit="dona",
            min_stock_alert=Decimal("10")
        )
        session.add(item)
        await session.commit()

        yield session, org, cp, item

    await engine.dispose()

@pytest.mark.asyncio
async def test_trial_balance_deterministic_balance(test_session):
    session, org, cp, item = test_session

    # 1. Purchase goods on credit: Dt 2900, Kt 6000 (10,000,000 UZS)
    tx1 = Transaction(
        organization_id=org.id,
        doc_number="INV-001",
        doc_date=date(2025, 2, 1),
        doc_type="EHF",
        debit_account="2900",
        credit_account="6000",
        counterparty_id=cp.id,
        item_id=item.id,
        quantity=Decimal("100"),
        price=Decimal("100000"),
        total_amount=Decimal("10000000.00")
    )
    session.add(tx1)

    # 2. Pay supplier from bank: Dt 6000, Kt 5110 (6,000,000 UZS)
    tx2 = Transaction(
        organization_id=org.id,
        doc_number="BANK-001",
        doc_date=date(2025, 2, 5),
        doc_type="BANK",
        debit_account="6000",
        credit_account="5110",
        counterparty_id=cp.id,
        total_amount=Decimal("6000000.00")
    )
    session.add(tx2)
    await session.commit()

    # Calculate OSV for Feb 2025
    osv = await AccountingEngine.calculate_oborotka(
        session=session,
        organization_id=org.id,
        from_date=date(2025, 2, 1),
        to_date=date(2025, 2, 28)
    )

    # Strict double-entry balance check: Total Debit Turnover == Total Credit Turnover
    assert osv.total_turnover_debit == osv.total_turnover_credit
    assert osv.total_turnover_debit == Decimal("16000000.00")
    assert osv.is_balanced == True

@pytest.mark.asyncio
async def test_material_report_weighted_average_cost(test_session):
    session, org, cp, item = test_session

    # Inflow 1: 100 units at 50,000 UZS = 5,000,000 UZS
    tx1 = Transaction(
        organization_id=org.id,
        doc_number="K-1",
        doc_date=date(2025, 3, 1),
        doc_type="EHF",
        debit_account="2900",
        credit_account="6000",
        item_id=item.id,
        quantity=Decimal("100.000"),
        price=Decimal("50000.00"),
        total_amount=Decimal("5000000.00")
    )
    # Inflow 2: 100 units at 70,000 UZS = 7,000,000 UZS
    # Total available: 200 units, 12,000,000 UZS => Avg price = 60,000 UZS
    tx2 = Transaction(
        organization_id=org.id,
        doc_number="K-2",
        doc_date=date(2025, 3, 5),
        doc_type="EHF",
        debit_account="2900",
        credit_account="6000",
        item_id=item.id,
        quantity=Decimal("100.000"),
        price=Decimal("70000.00"),
        total_amount=Decimal("7000000.00")
    )
    # Outflow: 50 units sold/dispatched
    tx3 = Transaction(
        organization_id=org.id,
        doc_number="CH-1",
        doc_date=date(2025, 3, 10),
        doc_type="STOCK",
        debit_account="9100",
        credit_account="2900",
        item_id=item.id,
        quantity=Decimal("50.000"),
        price=Decimal("60000.00"),
        total_amount=Decimal("3000000.00")
    )
    session.add_all([tx1, tx2, tx3])
    await session.commit()

    mat_rep = await AccountingEngine.calculate_material_report(
        session=session,
        organization_id=org.id,
        from_date=date(2025, 3, 1),
        to_date=date(2025, 3, 31),
        item_id=item.id
    )

    it_rep = mat_rep.items[0]
    assert it_rep.inflow_qty == Decimal("200.000")
    assert it_rep.inflow_sum == Decimal("12000000.00")
    assert it_rep.avg_price == Decimal("60000.00")
    assert it_rep.outflow_qty == Decimal("50.000")
    assert it_rep.outflow_sum == Decimal("3000000.00")
    # Closing stock: 150 units, 9,000,000 UZS
    assert it_rep.final_qty == Decimal("150.000")
    assert it_rep.final_sum == Decimal("9000000.00")
    # Equation test: Initial + Inflow - Outflow == Final
    assert it_rep.initial_qty + it_rep.inflow_qty - it_rep.outflow_qty == it_rep.final_qty
    assert it_rep.initial_sum + it_rep.inflow_sum - it_rep.outflow_sum == it_rep.final_sum

@pytest.mark.asyncio
async def test_akt_sverka_debt_reconciliation(test_session):
    session, org, cp, item = test_session

    # Supplier provided goods for 8,000,000 UZS (Credit on account 6000)
    tx1 = Transaction(
        organization_id=org.id,
        counterparty_id=cp.id,
        doc_number="INV-10",
        doc_date=date(2025, 4, 1),
        doc_type="EHF",
        debit_account="2900",
        credit_account="6000",
        total_amount=Decimal("8000000.00")
    )
    # We paid 5,000,000 UZS from bank
    tx2 = Transaction(
        organization_id=org.id,
        counterparty_id=cp.id,
        doc_number="PP-101",
        doc_date=date(2025, 4, 10),
        doc_type="BANK",
        debit_account="6000",
        credit_account="5110",
        total_amount=Decimal("5000000.00")
    )
    session.add_all([tx1, tx2])
    await session.commit()

    sverka = await AccountingEngine.calculate_akt_sverka(
        session=session,
        organization_id=org.id,
        counterparty_id=cp.id,
        from_date=date(2025, 4, 1),
        to_date=date(2025, 4, 30)
    )

    # Initial (0) + Debit (0) - Credit (8M - 5M = 3M debt to supplier)
    assert sverka.total_credit == Decimal("8000000.00")
    assert sverka.total_debit == Decimal("5000000.00")
    assert sverka.final_debt == Decimal("-3000000.00")
    assert "kreditorlik qarziga ega" in sverka.status_uz
