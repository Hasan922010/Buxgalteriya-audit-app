import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.database import engine
from app.db.seed import seed_database
from app.main import app


@pytest.fixture(autouse=True)
async def seeded_db():
    await seed_database()
    yield
    await engine.dispose()


@pytest.fixture
def reset_disabled(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_SYSTEM_RESET", False)


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _first_org_id(client: AsyncClient) -> str:
    orgs = (await client.get("/api/v1/organizations")).json()
    return orgs[0]["id"]


@pytest.mark.asyncio
async def test_factory_reset_forbidden_when_disabled(reset_disabled):
    async with await _client() as client:
        resp = await client.post("/api/v1/system/factory-reset", json={"confirmation": "TOZALASH"})
        assert resp.status_code == 403
        assert "ALLOW_SYSTEM_RESET" in resp.json()["detail"]
        assert len((await client.get("/api/v1/organizations")).json()) >= 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path_tpl",
    ["/api/v1/system/organizations/{org_id}/reset-data", "/api/v1/organizations/{org_id}/reset-data"],
)
async def test_org_reset_forbidden_when_disabled(reset_disabled, path_tpl):
    async with await _client() as client:
        org_id = await _first_org_id(client)
        resp = await client.post(path_tpl.format(org_id=org_id))
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_factory_reset_requires_chief_accountant_role():
    async with await _client() as client:
        resp = await client.post(
            "/api/v1/system/factory-reset",
            json={"confirmation": "TOZALASH"},
            headers={"X-User-Role": "OPERATOR"},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_system_org_reset_requires_privileged_role():
    async with await _client() as client:
        org_id = await _first_org_id(client)
        resp = await client.post(
            f"/api/v1/system/organizations/{org_id}/reset-data",
            headers={"X-User-Role": "AUDITOR"},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_factory_reset_writes_backup_before_wiping():
    async with await _client() as client:
        resp = await client.post("/api/v1/system/factory-reset", json={"confirmation": "TOZALASH"})
        assert resp.status_code == 200
        backup_name = resp.json()["pre_reset_backup"]
        assert os.path.exists(os.path.join(settings.BACKUP_DIR, backup_name))


@pytest.mark.asyncio
async def test_org_reset_writes_backup_before_wiping():
    async with await _client() as client:
        org_id = await _first_org_id(client)
        resp = await client.post(f"/api/v1/organizations/{org_id}/reset-data")
        assert resp.status_code == 200
        backup_name = resp.json()["pre_reset_backup"]
        assert os.path.exists(os.path.join(settings.BACKUP_DIR, backup_name))


@pytest.mark.asyncio
async def test_org_reset_unknown_org_returns_404():
    async with await _client() as client:
        resp = await client.post(f"/api/v1/system/organizations/{uuid.uuid4()}/reset-data")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_factory_reset_failure_reports_backup_to_restore(monkeypatch):
    import app.core.reset_database as reset_module

    async def broken_reset(*args, **kwargs):
        raise RuntimeError("simulated failure mid-reset")

    monkeypatch.setattr(reset_module, "factory_reset_database", broken_reset)
    async with await _client() as client:
        resp = await client.post("/api/v1/system/factory-reset", json={"confirmation": "TOZALASH"})
    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert "backup_" in detail and ".json" in detail
    assert "simulated failure" in detail
