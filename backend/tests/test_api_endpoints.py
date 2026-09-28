import os
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

from app.core.database import engine
from app.db.seed import seed_database

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_data")

@pytest.fixture(autouse=True)
async def cleanup_engine():
    await seed_database()
    yield
    await engine.dispose()


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

@pytest.mark.asyncio
async def test_accounts_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/accounts")
        assert resp.status_code == 200
        accounts = resp.json()
        assert len(accounts) >= 20
        codes = [a["code"] for a in accounts]
        assert "1000" in codes # Materiallar
        assert "2900" in codes # Tovarlar
        assert "5110" in codes # Bank

@pytest.mark.asyncio
async def test_organizations_and_mode_toggle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/organizations")
        assert resp.status_code == 200
        orgs = resp.json()
        assert len(orgs) > 0
        org_id = orgs[0]["id"]

        # Toggle to SIMPLE mode
        toggle_resp = await client.patch(f"/api/v1/organizations/{org_id}/mode", json={"mode": "SIMPLE"})
        assert toggle_resp.status_code == 200
        assert toggle_resp.json()["mode"] == "SIMPLE"

        # Toggle back to BHMS
        toggle_resp2 = await client.patch(f"/api/v1/organizations/{org_id}/mode", json={"mode": "BHMS"})
        assert toggle_resp2.status_code == 200
        assert toggle_resp2.json()["mode"] == "BHMS"

@pytest.mark.asyncio
async def test_upload_and_commit_didox():
    transport = ASGITransport(app=app)
    file_path = os.path.join(SAMPLE_DIR, "sample_didox.xlsx")
    assert os.path.exists(file_path)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Fetch organization
        orgs = (await client.get("/api/v1/organizations")).json()
        org_id = orgs[0]["id"]

        # 2. Upload Didox file
        with open(file_path, "rb") as f:
            files = {"file": ("sample_didox.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            upload_resp = await client.post("/api/v1/documents/upload", files=files)
        assert upload_resp.status_code == 200
        upload_data = upload_resp.json()
        assert upload_data["detected_format"]["format_type"] == "DIDOX_EHF"
        file_id = upload_data["file_id"]

        # 3. Commit transactions
        commit_payload = {
            "file_id": file_id,
            "organization_id": org_id,
            "format_type": "DIDOX_EHF",
            "doc_type": "EHF"
        }
        commit_resp = await client.post("/api/v1/documents/commit", json=commit_payload)
        assert commit_resp.status_code == 200
        commit_data = commit_resp.json()
        assert commit_data["success"] == True
        assert commit_data["imported_count"] == 3

        # 4. Check Trial Balance report (Oborotka)
        rep_resp = await client.get(f"/api/v1/reports/oborotka?organization_id={org_id}&from_date=2025-01-01&to_date=2025-12-31")
        assert rep_resp.status_code == 200
        rep_data = rep_resp.json()
        assert rep_data["is_balanced"] == True
        assert float(rep_data["total_turnover_debit"]) > 0

@pytest.mark.asyncio
async def test_ai_chat_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        chat_payload = {
            "query": "Qaysi kontragentdan qarzimiz ko'p?",
            "report_context": {
                "organization_name": "O'zbekiston Savdo MCHJ",
                "total_payables": "15,000,000.00",
                "monthly_inflow": "25,000,000.00"
            }
        }
        resp = await client.post("/api/v1/ai/chat", json=chat_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert len(data["response"]) > 0
