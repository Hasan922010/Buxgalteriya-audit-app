"""Regression tests for audit finding H3: the same document must not be booked twice by accident."""
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.db.seed import seed_database
from app.main import app
from app.models.organization import Organization
from app.models.transaction import Transaction

CSV_BODY = 'Sana;Tovar nomi;Summa\n03.04.2025;Non;"125 000,00"\n04.04.2025;Sut;"48 500,50"\n'
MAPPING = {"date_col": "Sana", "item_name_col": "Tovar nomi", "total_col": "Summa"}


@pytest.fixture(autouse=True)
async def seeded_db():
    await seed_database()
    yield
    await engine.dispose()


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _new_org() -> str:
    async with AsyncSessionLocal() as session:
        org = Organization(name=f"Dup {uuid.uuid4().hex[:6]}", inn=f"{uuid.uuid4().int % 10**9:09d}")
        session.add(org)
        await session.commit()
        return str(org.id)


def _upload(body: str = CSV_BODY) -> str:
    file_id = f"{uuid.uuid4()}_kassa.csv"
    with open(os.path.join(settings.UPLOAD_DIR, file_id), "w", encoding="utf-8") as fh:
        fh.write(body)
    return file_id


async def _tx_count(org_id: str) -> int:
    async with AsyncSessionLocal() as session:
        return (await session.execute(
            select(func.count()).select_from(Transaction).where(Transaction.organization_id == uuid.UUID(org_id))
        )).scalar_one()


def _commit_body(file_id: str, org_id: str, **extra) -> dict:
    return {"file_id": file_id, "organization_id": org_id, "format_type": "GENERIC_EXCEL",
            "doc_type": "SOLIQ_SALES", "mapping": MAPPING, **extra}


@pytest.mark.asyncio
async def test_same_file_committed_twice_is_rejected():
    org = await _new_org()
    file_id = _upload()
    async with _client() as client:
        first = await client.post("/api/v1/documents/commit", json=_commit_body(file_id, org))
        count_after_first = await _tx_count(org)
        second = await client.post("/api/v1/documents/commit", json=_commit_body(file_id, org))
    assert first.status_code == 200, first.text
    assert count_after_first == 2
    assert second.status_code == 409
    assert "allaqachon" in second.json()["detail"]
    assert await _tx_count(org) == 2


@pytest.mark.asyncio
async def test_reuploaded_identical_file_is_detected_by_content():
    org = await _new_org()
    async with _client() as client:
        await client.post("/api/v1/documents/commit", json=_commit_body(_upload(), org))
        again = await client.post("/api/v1/documents/commit", json=_commit_body(_upload(), org))
    assert again.status_code == 409
    assert await _tx_count(org) == 2


@pytest.mark.asyncio
async def test_duplicate_can_be_forced_explicitly():
    org = await _new_org()
    file_id = _upload()
    async with _client() as client:
        await client.post("/api/v1/documents/commit", json=_commit_body(file_id, org))
        forced = await client.post("/api/v1/documents/commit", json=_commit_body(file_id, org, allow_duplicate=True))
    assert forced.status_code == 200
    assert await _tx_count(org) == 4


@pytest.mark.asyncio
async def test_same_file_for_another_organization_is_allowed():
    org_a, org_b = await _new_org(), await _new_org()
    file_id = _upload()
    async with _client() as client:
        a = await client.post("/api/v1/documents/commit", json=_commit_body(file_id, org_a))
        b = await client.post("/api/v1/documents/commit", json=_commit_body(file_id, org_b))
    assert (a.status_code, b.status_code) == (200, 200)


@pytest.mark.asyncio
async def test_async_commit_rejects_duplicate_before_starting_task():
    org = await _new_org()
    file_id = _upload()
    async with _client() as client:
        await client.post("/api/v1/documents/commit", json=_commit_body(file_id, org))
        resp = await client.post("/api/v1/documents/commit-async", json=_commit_body(file_id, org))
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_ocr_document_committed_twice_is_rejected():
    org = await _new_org()
    body = {
        "organization_id": org,
        "document": {
            "doc_number": f"EHF-{uuid.uuid4().hex[:6]}", "doc_date": "2025-04-03", "doc_type": "EHF",
            "supplier_name": "Toshkent Savdo MCHJ", "supplier_inn": "301234567",
            "line_items": [{"item_name": "Qog'oz A4", "quantity": "10", "price": "50000", "total_amount": "560000"}],
        },
    }
    async with _client() as client:
        first = await client.post("/api/v1/ocr/commit", json=body)
        second = await client.post("/api/v1/ocr/commit", json=body)
        forced = await client.post("/api/v1/ocr/commit", json={**body, "allow_duplicate": True})
    assert first.status_code == 200, first.text
    assert second.status_code == 409
    assert forced.status_code == 200
    assert await _tx_count(org) == 2


@pytest.mark.asyncio
async def test_concurrent_duplicate_is_rejected_by_database_constraint(monkeypatch):
    """Review HIGH: two requests can both pass the pre-check; the DB must still allow only one."""
    import app.api.v1.endpoints.documents as documents_module

    async def race_window(*args, **kwargs):  # simulate both requests passing the pre-check
        return None

    monkeypatch.setattr(documents_module, "ensure_not_duplicate", race_window)
    org = await _new_org()
    file_id = _upload()
    async with _client() as client:
        first = await client.post("/api/v1/documents/commit", json=_commit_body(file_id, org))
        second = await client.post("/api/v1/documents/commit", json=_commit_body(file_id, org))
    assert first.status_code == 200
    assert second.status_code == 409
    assert await _tx_count(org) == 2


@pytest.mark.asyncio
async def test_ocr_receipts_without_number_but_different_items_are_not_duplicates():
    """Review MEDIUM: same day/total/line count but different lines must not collide."""
    org = await _new_org()

    def receipt(item):
        return {"organization_id": org, "document": {
            "doc_date": "2025-04-03", "doc_type": "CHEK",
            "line_items": [{"item_name": item, "quantity": "1", "price": "10000", "total_amount": "11200"}],
        }}

    async with _client() as client:
        a = await client.post("/api/v1/ocr/commit", json=receipt("Benzin AI-92"))
        b = await client.post("/api/v1/ocr/commit", json=receipt("Tushlik"))
    assert (a.status_code, b.status_code) == (200, 200)
