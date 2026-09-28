"""Security review note: /documents/commit-parsed must respect the period lock and be all-or-nothing."""
import uuid
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal, engine
from app.db.seed import seed_database
from app.main import app
from app.models.organization import Organization
from app.models.transaction import Transaction


@pytest.mark.asyncio
async def test_commit_parsed_rejects_locked_period_without_partial_writes():
    await seed_database()
    async with AsyncSessionLocal() as session:
        org = Organization(name=f"Lock {uuid.uuid4().hex[:6]}", inn=f"{uuid.uuid4().int % 10**9:09d}",
                           locked_until_date=date(2025, 3, 31))
        session.add(org)
        await session.commit()
        org_id = org.id

    records = [
        {"doc_number": "OPEN-1", "doc_date": "2025-05-10", "item_name": "Non", "total_amount": "1000"},    # open period
        {"doc_number": "LOCKED-1", "doc_date": "2025-02-10", "item_name": "Sut", "total_amount": "2000"},  # locked period
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/documents/commit-parsed",
                                 json={"organization_id": str(org_id), "records": records})

    async with AsyncSessionLocal() as session:
        count = (await session.execute(
            select(func.count()).select_from(Transaction).where(Transaction.organization_id == org_id)
        )).scalar_one()
    await engine.dispose()

    assert resp.status_code == 400
    assert count == 0
