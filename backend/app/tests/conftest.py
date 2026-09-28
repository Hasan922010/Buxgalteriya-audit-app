import uuid
import pytest
import numpy as np
import cv2
import pymupdf
from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.database import Base
from app.models.account import ChartOfAccount, AccountType, AccountingMode
from app.models.organization import Organization
from app.models.counterparty import Counterparty
from app.models.inventory import InventoryItem
from app.models.transaction import Transaction

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        # 1. Seed Chart of Accounts
        accounts = [
            ChartOfAccount(code="1000", name="Materiallar", account_type=AccountType.ASSET),
            ChartOfAccount(code="2900", name="Tovarlar", account_type=AccountType.ASSET),
            ChartOfAccount(code="4000", name="Xaridorlar", account_type=AccountType.ASSET),
            ChartOfAccount(code="5000", name="Kassa", account_type=AccountType.ASSET),
            ChartOfAccount(code="5110", name="Hisob-kitob schoti", account_type=AccountType.ASSET),
            ChartOfAccount(code="6000", name="Mol yetkazib beruvchilar", account_type=AccountType.LIABILITY),
            ChartOfAccount(code="9000", name="Daromadlar", account_type=AccountType.REVENUE),
            ChartOfAccount(code="9400", name="Davr xarajatlari", account_type=AccountType.EXPENSE),
        ]
        session.add_all(accounts)

        # 2. Seed Test Organization
        org = Organization(
            id=uuid.uuid4(),
            name="Master Test MCHJ",
            inn="305123456",
            mode=AccountingMode.BHMS,
            vat_payer=True,
            created_at=date(2025, 1, 1)
        )
        session.add(org)

        # 3. Seed Counterparty & Inventory Item
        cp = Counterparty(
            id=uuid.uuid4(),
            organization_id=org.id,
            name="Imkon Savdo QK",
            inn="201999888",
            is_supplier=True,
            is_client=True
        )
        session.add(cp)

        item = InventoryItem(
            id=uuid.uuid4(),
            organization_id=org.id,
            name="Po'lat armatura 12mm",
            ikpu_code="07212000001000000",
            unit="tn",
            min_stock_alert=Decimal("10.0")
        )
        session.add(item)
        await session.commit()

        yield session

        await session.close()
    await engine.dispose()

@pytest.fixture
def sample_degraded_image():
    """Generates a synthetic noisy and slightly rotated image for OCR enhancement testing."""
    img = np.ones((400, 600, 3), dtype=np.uint8) * 240
    # Add text
    cv2.putText(img, "HISOBVARAQ-FAKTURA 123", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2)
    cv2.putText(img, "STIR: 305123456", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 2)
    cv2.putText(img, "JAMI: 15,000,000.00 UZS", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 2)
    # Add noise
    noise = np.random.normal(0, 15, img.shape).astype(np.uint8)
    noisy = cv2.add(img, noise)
    return noisy

@pytest.fixture
def sample_pdf_bytes():
    """Creates a minimal in-memory PDF with text using PyMuPDF."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842) # A4
    page.insert_text((50, 100), "DIDOX ELEKTRON HISOBVARAQ-FAKTURA", fontsize=16)
    page.insert_text((50, 140), "Yetkazib beruvchi: OOO TEST BIZNES", fontsize=12)
    page.insert_text((50, 170), "STIR: 301234567", fontsize=12)
    page.insert_text((50, 200), "Tovar: Beton M300 | 10 m3 | 850 000 UZS", fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
