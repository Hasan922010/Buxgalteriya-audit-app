import pytest
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.database import Base
from app.models.account import ChartOfAccount, AccountType, AccountingMode
from app.models.organization import Organization
from app.models.counterparty import Counterparty
from app.models.inventory import InventoryItem
from app.models.transaction import Transaction
from app.models.audit_log import AuditLog
from app.services.accounting_engine import AccountingEngine
from app.services.tax_engine import TaxEngine

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def stage1_session():
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

        org = Organization(
            id=uuid.uuid4(),
            name="Mega Global Audit MCHJ",
            inn="112233445",
            mode=AccountingMode.BHMS,
            vat_payer=True,
            created_at=date(2025, 1, 1),
            locked_until_date=None
        )
        session.add(org)

        cp = Counterparty(
            id=uuid.uuid4(),
            organization_id=org.id,
            name="Samarqand Ta'minot XK",
            inn="987654321",
            is_supplier=True
        )
        session.add(cp)

        item = InventoryItem(
            id=uuid.uuid4(),
            organization_id=org.id,
            name="A4 Qog'oz",
            unit="dona"
        )
        session.add(item)
        await session.commit()

        yield {
            "session": session,
            "org": org,
            "cp": cp,
            "item": item
        }

    await engine.dispose()

def test_tax_engine_versioning():
    """Verify Uzbekistan VAT rate changes across historical dates."""
    # 2022 (Historical 15% rate)
    rate_2022 = TaxEngine.get_vat_rate(date(2022, 5, 20))
    assert rate_2022 == Decimal("0.15")

    calc_2022 = TaxEngine.calculate_vat_from_total(Decimal("1150000.00"), date(2022, 5, 20), is_vat_payer=True)
    assert calc_2022["vat_amount"] == Decimal("150000.00")
    assert calc_2022["base_amount"] == Decimal("1000000.00")

    # 2023+ (Current 12% rate)
    rate_2025 = TaxEngine.get_vat_rate(date(2025, 2, 10))
    assert rate_2025 == Decimal("0.12")

    calc_2025 = TaxEngine.calculate_vat_from_total(Decimal("1120000.00"), date(2025, 2, 10), is_vat_payer=True)
    assert calc_2025["vat_amount"] == Decimal("120000.00")
    assert calc_2025["base_amount"] == Decimal("1000000.00")

@pytest.mark.asyncio
async def test_storno_reversal_and_audit_trail(stage1_session):
    """Test creating transaction, checking balances, and performing Storno reversal."""
    session = stage1_session["session"]
    org = stage1_session["org"]
    cp = stage1_session["cp"]
    item = stage1_session["item"]

    # 1. Create a transaction: Receipt of goods (Dt 2900, Kt 6000, 10,000,000 UZS)
    tx = Transaction(
        id=uuid.uuid4(),
        organization_id=org.id,
        doc_number="INV-001",
        doc_date=date(2025, 3, 1),
        doc_type="EHF",
        debit_account="2900",
        credit_account="6000",
        counterparty_id=cp.id,
        item_id=item.id,
        quantity=Decimal("100"),
        price=Decimal("100000"),
        total_amount=Decimal("10000000.00"),
        vat_rate=Decimal("12"),
        vat_amount=Decimal("1200000.00"),
        description="Faktura INV-001 qabuli",
        is_reversed=False
    )
    session.add(tx)
    await session.commit()

    # Verify initial OSV includes the turnover
    osv_before = await AccountingEngine.calculate_oborotka(session, org.id, date(2025, 1, 1), date(2025, 12, 31))
    assert osv_before.total_turnover_debit == Decimal("10000000.00")

    # 2. Perform Storno
    storno_result = await AccountingEngine.storno_transaction(
        session=session,
        organization_id=org.id,
        transaction_id=tx.id,
        reason="Noto'g'ri narx kiritilgan",
        performed_by="Bosh Buxgalter Test"
    )
    assert storno_result["status"] == "success"

    # 3. Verify OSV after storno (should be 0.00 since original is marked is_reversed=True)
    osv_after = await AccountingEngine.calculate_oborotka(session, org.id, date(2025, 1, 1), date(2025, 12, 31))
    assert osv_after.total_turnover_debit == Decimal("0.00")

    # 4. Verify Audit Log was recorded
    audit_res = await session.execute(select(AuditLog).where(AuditLog.organization_id == org.id))
    logs = audit_res.scalars().all()
    assert len(logs) >= 1
    assert logs[0].action == "STORNO_TRANSACTION"

@pytest.mark.asyncio
async def test_period_locking_enforcement(stage1_session):
    """Test that period locking prevents reversing or modifying transactions on or before lock date."""
    session = stage1_session["session"]
    org = stage1_session["org"]
    cp = stage1_session["cp"]

    # Set period lock to 2025-01-31
    org.locked_until_date = date(2025, 1, 31)
    await session.commit()

    # Create transaction inside locked period (2025-01-15)
    tx_locked = Transaction(
        id=uuid.uuid4(),
        organization_id=org.id,
        doc_number="LOCKED-01",
        doc_date=date(2025, 1, 15),
        doc_type="EHF",
        debit_account="2900",
        credit_account="6000",
        counterparty_id=cp.id,
        total_amount=Decimal("5000000.00"),
        is_reversed=False
    )
    session.add(tx_locked)
    await session.commit()

    # Attempt to storno inside locked period must fail
    with pytest.raises(ValueError, match="Davr qulflangan"):
        await AccountingEngine.storno_transaction(
            session=session,
            organization_id=org.id,
            transaction_id=tx_locked.id,
            reason="Sinov storno"
        )
