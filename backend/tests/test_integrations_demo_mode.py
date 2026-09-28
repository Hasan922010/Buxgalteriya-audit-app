import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.db.seed import seed_database
from app.main import app
from app.models.transaction import Transaction


@pytest.fixture(autouse=True)
async def seeded_db():
    await seed_database()
    yield
    await engine.dispose()


async def _tx_count() -> int:
    async with AsyncSessionLocal() as session:
        return (await session.execute(select(func.count()).select_from(Transaction))).scalar_one()


async def _org_id(client: AsyncClient) -> str:
    return (await client.get("/api/v1/organizations")).json()[0]["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["didox", "soliq"])
async def test_sync_is_blocked_and_writes_nothing_when_demo_mode_off(monkeypatch, provider):
    monkeypatch.setattr(settings, "INTEGRATIONS_DEMO_MODE", False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        org_id = await _org_id(client)
        before = await _tx_count()

        resp = await client.post(f"/api/v1/integrations/{provider}/sync", json={"organization_id": org_id})

        assert resp.status_code == 503
        assert "demo" in resp.json()["detail"].lower()
        assert await _tx_count() == before


@pytest.mark.asyncio
async def test_status_reports_not_configured_when_demo_mode_off(monkeypatch):
    monkeypatch.setattr(settings, "INTEGRATIONS_DEMO_MODE", False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        data = (await client.get("/api/v1/integrations/status")).json()
    for provider in ("didox", "soliq"):
        assert data[provider]["success"] is False
        assert data[provider]["status"] == "NOT_CONFIGURED"
        assert data[provider]["demo_mode"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["didox", "soliq"])
async def test_test_connection_endpoint_is_honest_when_demo_mode_off(monkeypatch, provider):
    monkeypatch.setattr(settings, "INTEGRATIONS_DEMO_MODE", False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        data = (await client.post(f"/api/v1/integrations/{provider}/test")).json()
    assert data["success"] is False
    assert data["status"] == "NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_sync_works_and_is_labelled_demo_when_demo_mode_on(monkeypatch):
    monkeypatch.setattr(settings, "INTEGRATIONS_DEMO_MODE", True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        org_id = await _org_id(client)
        status_data = (await client.get("/api/v1/integrations/status")).json()
        resp = await client.post("/api/v1/integrations/didox/sync", json={"organization_id": org_id})

    assert status_data["didox"]["demo_mode"] is True
    assert resp.status_code == 200
    assert resp.json()["demo_mode"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter_name", ["DidoxAdapter", "SoliqAdapter"])
async def test_adapters_refuse_direct_sync_when_demo_mode_off(monkeypatch, adapter_name):
    """Review finding: the gate must live in the adapters, not only in the HTTP endpoint."""
    import app.services.integrations as integrations
    from app.services.integrations.base_adapter import IntegrationDemoModeDisabled

    monkeypatch.setattr(settings, "INTEGRATIONS_DEMO_MODE", False)
    adapter = getattr(integrations, adapter_name)()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        org_id = await _org_id(client)
    before = await _tx_count()

    async with AsyncSessionLocal() as session:
        with pytest.raises(IntegrationDemoModeDisabled):
            await adapter.sync_documents(session=session, organization_id=org_id)

    assert await _tx_count() == before
