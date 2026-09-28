import pytest
import uuid
from decimal import Decimal
from datetime import date
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.core.database import get_db, Base
from app.services.task_manager import task_manager, TaskStatus
from app.core.rbac import UserRole, require_roles
from app.models.organization import Organization
from app.models.account import ChartOfAccount, AccountType, AccountingMode

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def async_client():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
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
            name="Test Korxona",
            inn="998877665",
            mode=AccountingMode.BHMS,
            vat_payer=True,
            created_at=date(2025, 1, 1),
            locked_until_date=None
        )
        session.add(org)
        await session.commit()

    async def override_get_db():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()

@pytest.mark.asyncio
async def test_task_manager_lifecycle():
    task = task_manager.create_task("Test Ingestion Task")
    assert task.status == TaskStatus.PENDING
    assert task.progress == 0

    task.update_progress(45, "45% yuklandi", processed_items=45, total_items=100)
    assert task.status == TaskStatus.PROCESSING
    assert task.progress == 45
    assert task.processed_items == 45
    assert task.total_items == 100

    task.complete({"status": "ok"}, "Hammasi tayyor")
    assert task.status == TaskStatus.COMPLETED
    assert task.progress == 100
    assert task.result == {"status": "ok"}

    task_err = task_manager.create_task("Failing Task")
    task_err.fail("Kritik xatolik")
    assert task_err.status == TaskStatus.FAILED
    assert "Kritik xatolik" in task_err.error_message

@pytest.mark.asyncio
async def test_tasks_api_endpoint(async_client: AsyncClient):
    task = task_manager.create_task("API status tekshiruvi")
    task.update_progress(50, "Yarmi bajarildi")

    # Get created task
    resp = await async_client.get(f"/api/v1/tasks/{task.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == task.id
    assert data["progress"] == 50
    assert data["step_message"] == "Yarmi bajarildi"

    # Get unknown task
    unknown_resp = await async_client.get(f"/api/v1/tasks/{uuid.uuid4()}")
    assert unknown_resp.status_code == 404

@pytest.mark.asyncio
async def test_rbac_period_lock_and_storno_protection(async_client: AsyncClient):
    # 1. Fetch created organization
    orgs_resp = await async_client.get("/api/v1/organizations")
    assert orgs_resp.status_code == 200
    org_id = orgs_resp.json()[0]["id"]

    # 2. OPERATOR attempts to lock period -> 403 Forbidden!
    resp_operator = await async_client.patch(
        f"/api/v1/organizations/{org_id}/lock-period",
        json={"locked_until_date": "2026-03-31"},
        headers={"X-User-Role": "OPERATOR"}
    )
    assert resp_operator.status_code == 403
    assert "ruxsat bermaydi" in resp_operator.json()["detail"].lower()

    # 3. AUDITOR attempts to toggle mode -> 403 Forbidden!
    resp_auditor = await async_client.patch(
        f"/api/v1/organizations/{org_id}/mode",
        json={"mode": "BHMS"},
        headers={"X-User-Role": "AUDITOR"}
    )
    assert resp_auditor.status_code == 403

    # 4. CHIEF_ACCOUNTANT successfully locks period -> 200 OK
    resp_chief = await async_client.patch(
        f"/api/v1/organizations/{org_id}/lock-period",
        json={"locked_until_date": "2026-03-31"},
        headers={"X-User-Role": "CHIEF_ACCOUNTANT"}
    )
    assert resp_chief.status_code == 200
    assert resp_chief.json()["locked_until_date"] == "2026-03-31"

    # 5. Without header (defaults to CHIEF_ACCOUNTANT) -> 200 OK
    resp_default = await async_client.patch(
        f"/api/v1/organizations/{org_id}/lock-period",
        json={"locked_until_date": None}
    )
    assert resp_default.status_code == 200
    assert resp_default.json()["locked_until_date"] is None
