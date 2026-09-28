# --- Test isolation: MUST run before any `app.*` import ---------------------
# Tests exercise factory-reset / reset-data, so they must never touch the
# developer's real database, uploads or backups.
import os
import shutil
import tempfile

_TEST_TMP_DIR = tempfile.mkdtemp(prefix="buxgalter_tests_")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + os.path.join(_TEST_TMP_DIR, "test.db").replace("\\", "/")
os.environ["UPLOAD_DIR"] = os.path.join(_TEST_TMP_DIR, "uploads")
os.environ["BACKUP_DIR"] = os.path.join(_TEST_TMP_DIR, "backups")
os.environ["DEBUG"] = "False"
os.environ["ALLOW_SYSTEM_RESET"] = "True"
os.environ["SECRET_KEY"] = "test-only-secret-key-0123456789-abcdefghijklmnop"
os.environ["BOOTSTRAP_ADMIN_USERNAME"] = ""
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = ""
os.environ["INTEGRATIONS_DEMO_MODE"] = "False"
os.environ["GEMINI_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""

import pytest

from app.core.config import settings

if not settings.DATABASE_URL.startswith("sqlite"):
    pytest.exit(f"Refusing to run tests against non-test database: {settings.DATABASE_URL.split('@')[-1]}", returncode=2)


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TEST_TMP_DIR, ignore_errors=True)


def pytest_configure(config):
    config.addinivalue_line("markers", "real_auth: use real JWT authentication instead of the test user")


@pytest.fixture(autouse=True)
def _test_user_override(request):
    """
    Legacy API tests predate authentication: authenticate them as a superuser whose role
    comes from the X-User-Role header (test-only). Tests marked `real_auth` exercise real JWTs.
    """
    if request.node.get_closest_marker("real_auth"):
        yield
        return

    from types import SimpleNamespace
    from fastapi import Request
    from app.core.auth import get_current_user
    from app.main import app

    async def _fake_user(req: Request):
        return SimpleNamespace(
            id=uuid.UUID(int=0), username="pytest", full_name="Pytest",
            role=(req.headers.get("X-User-Role") or "CHIEF_ACCOUNTANT").strip().upper(),
            is_superuser=True, is_active=True,
        )

    app.dependency_overrides[get_current_user] = _fake_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
# ---------------------------------------------------------------------------

import uuid
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
            ChartOfAccount(code="4410", name="Byudjetga to'lovlar (QQS)", account_type=AccountType.ASSET),
            ChartOfAccount(code="5000", name="Kassa", account_type=AccountType.ASSET),
            ChartOfAccount(code="5110", name="Hisob-kitob schoti", account_type=AccountType.ASSET),
            ChartOfAccount(code="6000", name="Mol yetkazib beruvchilar", account_type=AccountType.LIABILITY),
            ChartOfAccount(code="6410", name="Byudjetga qarzlar (QQS)", account_type=AccountType.LIABILITY),
            ChartOfAccount(code="8300", name="Ustav kapitali", account_type=AccountType.EQUITY),
            ChartOfAccount(code="8700", name="Taqsimlanmagan foyda", account_type=AccountType.EQUITY),
            ChartOfAccount(code="9000", name="Daromadlar", account_type=AccountType.REVENUE),
            ChartOfAccount(code="9100", name="Sotilgan tovarlar tannarxi", account_type=AccountType.EXPENSE),
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
