import os
import pytest
import uuid
from decimal import Decimal
from datetime import date
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete

from app.main import app
from app.core.database import engine, AsyncSessionLocal
from app.db.seed import seed_database
from app.models.organization import Organization
from app.models.account import AccountingMode, ChartOfAccount
from app.models.counterparty import Counterparty
from app.models.transaction import Transaction

@pytest.fixture(autouse=True)
async def cleanup_and_seed():
    await seed_database()
    yield
    await engine.dispose()

@pytest.mark.asyncio
async def test_multi_tenancy_data_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Use random INNs to avoid collisions in repeated test runs
        inn_a = f"99{uuid.uuid4().int % 10000000:07d}"
        inn_b = f"88{uuid.uuid4().int % 10000000:07d}"

        # 1. Create two distinct organizations via API
        resp_a = await client.post(
            "/api/v1/organizations",
            json={"name": "Kompaniya Alpha MCHJ", "inn": inn_a, "mode": "BHMS", "vat_payer": True}
        )
        assert resp_a.status_code == 200
        org_a = resp_a.json()
        org_a_id = org_a["id"]

        resp_b = await client.post(
            "/api/v1/organizations",
            json={"name": "Kompaniya Beta MCHJ", "inn": inn_b, "mode": "BHMS", "vat_payer": False}
        )
        assert resp_b.status_code == 200
        org_b = resp_b.json()
        org_b_id = org_b["id"]

        assert org_a_id != org_b_id

        # 2. Add counterparties to each organization
        async with AsyncSessionLocal() as session:
            cp_a = Counterparty(
                organization_id=uuid.UUID(org_a_id),
                name="Alpha Yetkazib Beruvchi",
                inn="100000001",
                is_supplier=True,
                is_client=False
            )
            cp_b = Counterparty(
                organization_id=uuid.UUID(org_b_id),
                name="Beta Yetkazib Beruvchi",
                inn="200000002",
                is_supplier=True,
                is_client=False
            )
            session.add_all([cp_a, cp_b])
            await session.commit()
            await session.refresh(cp_a)
            await session.refresh(cp_b)
            cp_a_id = cp_a.id
            cp_b_id = cp_b.id

            # 3. Add transactions for each org with distinct amounts
            tx_a = Transaction(
                organization_id=uuid.UUID(org_a_id),
                doc_number="DOC-ALPHA-01",
                doc_date=date(2025, 3, 1),
                doc_type="BANK",
                debit_account="5110",
                credit_account="6000",
                counterparty_id=cp_a_id,
                total_amount=Decimal("5000000.00"),
                description="Alpha hisobiga tushum"
            )
            tx_b = Transaction(
                organization_id=uuid.UUID(org_b_id),
                doc_number="DOC-BETA-01",
                doc_date=date(2025, 3, 1),
                doc_type="BANK",
                debit_account="5110",
                credit_account="6000",
                counterparty_id=cp_b_id,
                total_amount=Decimal("12000000.00"),
                description="Beta hisobiga tushum"
            )
            session.add_all([tx_a, tx_b])
            await session.commit()

        # 4. Verify Trial Balance (Oborotka) for Org A has ONLY Org A's numbers
        rep_a = await client.get(
            f"/api/v1/reports/oborotka?organization_id={org_a_id}&from_date=2025-01-01&to_date=2025-12-31"
        )
        assert rep_a.status_code == 200
        data_a = rep_a.json()
        assert data_a["is_balanced"] == True
        assert Decimal(str(data_a["total_turnover_debit"])) == Decimal("5000000.00")
        assert Decimal(str(data_a["total_turnover_credit"])) == Decimal("5000000.00")

        # 5. Verify Trial Balance for Org B has ONLY Org B's numbers
        rep_b = await client.get(
            f"/api/v1/reports/oborotka?organization_id={org_b_id}&from_date=2025-01-01&to_date=2025-12-31"
        )
        assert rep_b.status_code == 200
        data_b = rep_b.json()
        assert data_b["is_balanced"] == True
        assert Decimal(str(data_b["total_turnover_debit"])) == Decimal("12000000.00")
        assert Decimal(str(data_b["total_turnover_credit"])) == Decimal("12000000.00")

        # 6. Verify Org A's Akt Sverka does not include Org B's counterparty or transaction
        sverka_a = await client.get(
            f"/api/v1/reports/akt-sverka?organization_id={org_a_id}&counterparty_id={cp_a_id}&from_date=2025-01-01&to_date=2025-12-31"
        )
        assert sverka_a.status_code == 200
        sverka_data_a = sverka_a.json()
        assert sverka_data_a["counterparty_name"] == "Alpha Yetkazib Beruvchi"
        assert len(sverka_data_a["items"]) == 1
        assert Decimal(str(sverka_data_a["items"][0]["credit"])) == Decimal("5000000.00")


@pytest.mark.asyncio
async def test_reset_organization_data_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        inn_1 = f"11{uuid.uuid4().int % 10000000:07d}"
        inn_2 = f"22{uuid.uuid4().int % 10000000:07d}"

        # Create Org 1 and Org 2
        resp_1 = await client.post(
            "/api/v1/organizations",
            json={"name": "Org Bir MCHJ", "inn": inn_1, "mode": "BHMS"}
        )
        org1_id = resp_1.json()["id"]

        resp_2 = await client.post(
            "/api/v1/organizations",
            json={"name": "Org Ikki MCHJ", "inn": inn_2, "mode": "BHMS"}
        )
        org2_id = resp_2.json()["id"]

        # Insert transactions in both
        async with AsyncSessionLocal() as session:
            session.add(Transaction(
                organization_id=uuid.UUID(org1_id),
                doc_number="TX-1",
                doc_date=date(2025, 2, 1),
                doc_type="BANK",
                debit_account="5110",
                credit_account="6000",
                total_amount=Decimal("3000000.00")
            ))
            session.add(Transaction(
                organization_id=uuid.UUID(org2_id),
                doc_number="TX-2",
                doc_date=date(2025, 2, 1),
                doc_type="BANK",
                debit_account="5110",
                credit_account="6000",
                total_amount=Decimal("7000000.00")
            ))
            await session.commit()

        # Reset Org 1 only
        reset_resp = await client.post(f"/api/v1/organizations/{org1_id}/reset-data")
        assert reset_resp.status_code == 200
        reset_data = reset_resp.json()
        assert reset_data["success"] == True
        assert reset_data["deleted_transactions"] == 1

        # Check Org 1 Oborotka: should have 0 turnover
        rep1 = await client.get(
            f"/api/v1/reports/oborotka?organization_id={org1_id}&from_date=2025-01-01&to_date=2025-12-31"
        )
        assert rep1.status_code == 200
        assert Decimal(str(rep1.json()["total_turnover_debit"])) == Decimal("0.00")

        # Check Org 2 Oborotka: MUST BE INTACT (7,000,000 UZS)
        rep2 = await client.get(
            f"/api/v1/reports/oborotka?organization_id={org2_id}&from_date=2025-01-01&to_date=2025-12-31"
        )
        assert rep2.status_code == 200
        assert Decimal(str(rep2.json()["total_turnover_debit"])) == Decimal("7000000.00")

        # Verify Org 1 entity itself still exists
        orgs_list = (await client.get("/api/v1/organizations")).json()
        org_ids = [o["id"] for o in orgs_list]
        assert org1_id in org_ids
        assert org2_id in org_ids


@pytest.mark.asyncio
async def test_factory_reset_database_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Invalid confirmation keyword rejected
        bad_resp = await client.post(
            "/api/v1/system/factory-reset",
            json={"confirmation": "NOT_CORRECT"}
        )
        assert bad_resp.status_code == 400
        assert "TOZALASH" in bad_resp.json()["detail"]

        # Valid factory reset execution
        good_resp = await client.post(
            "/api/v1/system/factory-reset",
            json={"confirmation": "TOZALASH"}
        )
        assert good_resp.status_code == 200
        data = good_resp.json()
        assert data["success"] == True
        assert "created_demo_org_id" in data

        # Verify database is in fresh clean state
        orgs = (await client.get("/api/v1/organizations")).json()
        assert len(orgs) == 1
        clean_org = orgs[0]
        assert clean_org["inn"] == "123456789"

        # Verify BHMS accounts are present
        accounts = (await client.get("/api/v1/accounts")).json()
        assert len(accounts) >= 20
