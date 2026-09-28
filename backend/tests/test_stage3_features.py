import pytest
import uuid
import os
from datetime import date
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.core.config import settings
from app.core.database import get_db, Base
from app.services.integrations.didox_adapter import DidoxAdapter
from app.services.integrations.soliq_adapter import SoliqAdapter
from app.services.backup_engine import BackupEngine, BACKUP_DIR
from app.models.organization import Organization
from app.models.account import ChartOfAccount, AccountType, AccountingMode
from app.models.transaction import Transaction

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def stage3_client_and_org():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    org_id = uuid.uuid4()

    async with Session() as session:
        accounts = [
            ChartOfAccount(code="1000", name="Materiallar", account_type=AccountType.ASSET),
            ChartOfAccount(code="2900", name="Tovarlar", account_type=AccountType.ASSET),
            ChartOfAccount(code="5000", name="Kassa", account_type=AccountType.ASSET),
            ChartOfAccount(code="5110", name="Bank hisobi", account_type=AccountType.ASSET),
            ChartOfAccount(code="6000", name="Mol yetkazib beruvchilar", account_type=AccountType.LIABILITY),
            ChartOfAccount(code="9000", name="Sotishdan daromad", account_type=AccountType.REVENUE),
        ]
        session.add_all(accounts)
        org = Organization(
            id=org_id,
            name="Mega Savdo Integratsiya MCHJ",
            inn="556677889",
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
        yield client, org_id, Session

    app.dependency_overrides.clear()
    await engine.dispose()

@pytest.mark.asyncio
async def test_didox_adapter_direct_sync(stage3_client_and_org, monkeypatch):
    # Adapters only fabricate demo documents; they are gated behind demo mode
    monkeypatch.setattr(settings, "INTEGRATIONS_DEMO_MODE", True)
    _, org_id, Session = stage3_client_and_org
    adapter = DidoxAdapter()

    # 1. Test connectivity
    conn_res = await adapter.test_connection({"api_token": "test_token_123"})
    assert conn_res["success"] is True
    assert conn_res["status"] == "CONNECTED"

    # 2. Sync documents
    async with Session() as session:
        res = await adapter.sync_documents(
            session=session,
            organization_id=org_id,
            from_date=date(2026, 3, 15)
        )
        assert res["success"] is True
        assert res["synced_count"] >= 2
        assert res["total_amount"] > 0

    # 3. Test period lock enforcement in Didox adapter
    async with Session() as session:
        org = await session.get(Organization, org_id)
        org.locked_until_date = date(2026, 3, 31)
        await session.commit()

        with pytest.raises(ValueError) as exc_info:
            await adapter.sync_documents(
                session=session,
                organization_id=org_id,
                from_date=date(2026, 3, 20)
            )
        assert "Davr qulflangan" in str(exc_info.value)

@pytest.mark.asyncio
async def test_soliq_adapter_direct_sync(stage3_client_and_org, monkeypatch):
    # Adapters only fabricate demo documents; they are gated behind demo mode
    monkeypatch.setattr(settings, "INTEGRATIONS_DEMO_MODE", True)
    _, org_id, Session = stage3_client_and_org
    adapter = SoliqAdapter()

    # 1. Test connectivity
    conn_res = await adapter.test_connection({"nkm_serial": "NKM_UZ_99988"})
    assert conn_res["success"] is True
    assert conn_res["status"] == "ONLINE"

    # 2. Sync receipts
    async with Session() as session:
        # unlock period
        org = await session.get(Organization, org_id)
        org.locked_until_date = None
        await session.commit()

        res = await adapter.sync_documents(
            session=session,
            organization_id=org_id,
            from_date=date(2026, 4, 1)
        )
        assert res["success"] is True
        assert res["synced_count"] == 2
        assert res["total_amount"] == 36800000.0

@pytest.mark.asyncio
async def test_backup_engine_creation_and_integrity(stage3_client_and_org):
    _, org_id, Session = stage3_client_and_org

    async with Session() as session:
        backup_res = await BackupEngine.create_backup(session=session, organization_id=org_id)
        assert "backup_id" in backup_res
        assert backup_res["size_bytes"] > 0
        assert len(backup_res["checksum_sha256"]) == 64  # SHA256 hex length
        filename = backup_res["filename"]

        # Verify listing
        backups = BackupEngine.list_backups()
        assert any(b["filename"] == filename for b in backups)

        # Verify cryptographic integrity
        verify_res = BackupEngine.verify_backup(filename)
        assert verify_res["valid"] is True
        assert verify_res["actual_checksum"] == backup_res["checksum_sha256"]

@pytest.mark.asyncio
async def test_integrations_and_backup_api_rbac(stage3_client_and_org):
    client, org_id, _ = stage3_client_and_org

    # 1. Integrations Status API
    status_resp = await client.get("/api/v1/integrations/status")
    assert status_resp.status_code == 200
    stat_data = status_resp.json()
    # Real API integration is not wired yet: status must not claim a live connection
    assert stat_data["didox"]["status"] == "NOT_CONFIGURED"
    assert stat_data["soliq"]["status"] == "NOT_CONFIGURED"

    # 2. OPERATOR attempts to create backup -> 403 Forbidden!
    op_backup_resp = await client.post(
        "/api/v1/backup/create",
        json={"organization_id": str(org_id)},
        headers={"X-User-Role": "OPERATOR"}
    )
    assert op_backup_resp.status_code == 403
    assert "ruxsat bermaydi" in op_backup_resp.json()["detail"].lower()

    # 3. CHIEF_ACCOUNTANT creates backup -> 200 OK
    chief_backup_resp = await client.post(
        "/api/v1/backup/create",
        json={"organization_id": str(org_id)},
        headers={"X-User-Role": "CHIEF_ACCOUNTANT"}
    )
    assert chief_backup_resp.status_code == 200
    assert "backup_id" in chief_backup_resp.json()

    # 4. List backups API
    list_resp = await client.get("/api/v1/backup/list")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) > 0
