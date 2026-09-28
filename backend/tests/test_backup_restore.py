"""Backup restore: the safety snapshots written before resets must actually be restorable."""
import json
import os
import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.db.seed import seed_database
from app.main import app
from app.models.counterparty import Counterparty
from app.models.organization import Organization
from app.models.transaction import Transaction


@pytest.fixture(autouse=True)
async def seeded_db():
    await seed_database()
    yield
    await engine.dispose()


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _org_with_data() -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        org = Organization(name=f"Restore {uuid.uuid4().hex[:6]}", inn=f"{uuid.uuid4().int % 10**9:09d}")
        session.add(org)
        await session.flush()
        cp = Counterparty(organization_id=org.id, name="Hamkor MCHJ", inn="301111222", mfo="00873", phone="+998901234567")
        session.add(cp)
        await session.flush()
        original = Transaction(organization_id=org.id, counterparty_id=cp.id, doc_number="INV-1", doc_date=date(2025, 3, 1),
                               doc_type="EHF", debit_account="2900", credit_account="6000", total_amount=Decimal("1500000.00"),
                               raw_payload="{'row': 1}")
        session.add(original)
        await session.flush()
        session.add(Transaction(organization_id=org.id, doc_number="STORNO-INV-1", doc_date=date(2025, 4, 1), doc_type="EHF",
                                debit_account="2900", credit_account="6000", total_amount=Decimal("-1500000.00"),
                                is_reversed=True, reversal_ref_id=original.id, reversal_reason="Xato"))
        await session.commit()
        return org.id


async def _counts(org_id: uuid.UUID):
    async with AsyncSessionLocal() as session:
        txs = (await session.execute(select(func.count()).select_from(Transaction).where(Transaction.organization_id == org_id))).scalar_one()
        cps = (await session.execute(select(func.count()).select_from(Counterparty).where(Counterparty.organization_id == org_id))).scalar_one()
        return txs, cps


async def _backup(client: AsyncClient, org_id=None) -> str:
    body = {"organization_id": str(org_id)} if org_id else {}
    resp = await client.post("/api/v1/backup/create", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["filename"]


async def _restore(client: AsyncClient, filename: str, confirmation: str = "TIKLASH"):
    return await client.post(f"/api/v1/backup/{filename}/restore", json={"confirmation": confirmation})


@pytest.mark.asyncio
async def test_restore_undoes_organization_reset():
    org_id = await _org_with_data()
    async with _client() as client:
        filename = await _backup(client, org_id)
        await client.post(f"/api/v1/organizations/{org_id}/reset-data")
        assert await _counts(org_id) == (0, 0)

        resp = await _restore(client, filename)

    assert resp.status_code == 200, resp.text
    assert await _counts(org_id) == (2, 1)
    assert os.path.exists(os.path.join(settings.BACKUP_DIR, resp.json()["pre_restore_backup"]))


@pytest.mark.asyncio
async def test_restore_replaces_changes_made_after_the_snapshot_and_keeps_all_fields():
    org_id = await _org_with_data()
    async with _client() as client:
        filename = await _backup(client, org_id)
        async with AsyncSessionLocal() as session:
            session.add(Transaction(organization_id=org_id, doc_number="LATER", doc_date=date(2025, 5, 1), doc_type="BANK",
                                    debit_account="5110", credit_account="6000", total_amount=Decimal("1.00")))
            await session.commit()

        resp = await _restore(client, filename)

    assert resp.status_code == 200, resp.text
    async with AsyncSessionLocal() as session:
        txs = (await session.execute(select(Transaction).where(Transaction.organization_id == org_id))).scalars().all()
        cp = (await session.execute(select(Counterparty).where(Counterparty.organization_id == org_id))).scalar_one()
    assert "LATER" not in {t.doc_number for t in txs}
    storno = next(t for t in txs if t.doc_number == "STORNO-INV-1")
    original = next(t for t in txs if t.doc_number == "INV-1")
    assert storno.reversal_ref_id == original.id and storno.reversal_reason == "Xato"
    assert original.raw_payload == "{'row': 1}"
    assert (cp.mfo, cp.phone) == ("00873", "+998901234567")


@pytest.mark.asyncio
async def test_full_backup_restores_organization_removed_by_factory_reset():
    org_id = await _org_with_data()
    async with _client() as client:
        filename = await _backup(client)  # full snapshot (superuser in tests)
        reset = await client.post("/api/v1/system/factory-reset", json={"confirmation": "TOZALASH"})
        assert reset.status_code == 200

        resp = await _restore(client, filename)

    assert resp.status_code == 200, resp.text
    assert await _counts(org_id) == (2, 1)


@pytest.mark.asyncio
async def test_restore_requires_confirmation_and_enabled_flag(monkeypatch):
    org_id = await _org_with_data()
    async with _client() as client:
        filename = await _backup(client, org_id)
        wrong = await _restore(client, filename, confirmation="ha")
        monkeypatch.setattr(settings, "ALLOW_SYSTEM_RESET", False)
        disabled = await _restore(client, filename)
    assert wrong.status_code == 400
    assert disabled.status_code == 403


@pytest.mark.asyncio
async def test_restore_rejects_corrupted_backup():
    name = f"backup_corrupt_{uuid.uuid4().hex[:8]}.json"
    with open(os.path.join(settings.BACKUP_DIR, name), "w", encoding="utf-8") as fh:
        json.dump({"backup_version": "9.9", "organization_id": "ALL", "data": {}}, fh)
    async with _client() as client:
        resp = await _restore(client, name)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_restore_reverts_inn_changed_after_snapshot():
    org_id = await _org_with_data()
    async with _client() as client:
        filename = await _backup(client, org_id)
        async with AsyncSessionLocal() as session:
            org = (await session.execute(select(Organization).where(Organization.id == org_id))).scalar_one()
            original_inn = org.inn
            org.inn = f"{uuid.uuid4().int % 10**9:09d}"
            await session.commit()
        resp = await _restore(client, filename)
    assert resp.status_code == 200, resp.text
    async with AsyncSessionLocal() as session:
        org = (await session.execute(select(Organization).where(Organization.id == org_id))).scalar_one()
    assert org.inn == original_inn
