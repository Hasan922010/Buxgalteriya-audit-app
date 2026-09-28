"""Unparseable dates / amounts must be reported as row errors, never booked as 'today' or 0."""
import os
import uuid
from datetime import date
from decimal import Decimal

import openpyxl
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.db.seed import seed_database
from app.main import app
from app.models.organization import Organization
from app.models.transaction import Transaction
from app.services.parsers.didox_parser import DidoxParser
from app.services.parsers.normalize import UnparseableValue, require_amount, require_date

SAMPLE_DIDOX = os.path.join(os.path.dirname(__file__), "sample_data", "sample_didox.xlsx")


def test_require_helpers_default_only_for_empty_cells():
    assert require_date(None, date(2025, 1, 1)) == date(2025, 1, 1)
    assert require_date("", date(2025, 1, 1)) == date(2025, 1, 1)
    assert require_date("03.04.2025", date(2025, 1, 1)) == date(2025, 4, 3)
    assert require_amount(None, Decimal("0")) == Decimal("0")
    assert require_amount("1 250,50", Decimal("0")) == Decimal("1250.50")
    with pytest.raises(UnparseableValue):
        require_date("31.02.2025", date(2025, 1, 1))
    with pytest.raises(UnparseableValue):
        require_amount("12abc", Decimal("0"))


def test_didox_parser_reports_bad_date_instead_of_using_today(tmp_path):
    wb = openpyxl.load_workbook(SAMPLE_DIDOX)
    ws = wb.active
    ws["C2"] = "32.13.2025"  # first data row, 'Sana' column
    broken = tmp_path / "didox_broken.xlsx"
    wb.save(broken)

    parser = DidoxParser()
    records = parser.parse_file(str(broken))

    assert all(r.doc_date != date.today() for r in records)
    assert len(parser.row_errors) == 1
    assert "32.13.2025" in parser.row_errors[0]


@pytest.mark.asyncio
async def test_manual_mapping_import_returns_row_errors():
    await seed_database()
    async with AsyncSessionLocal() as session:
        org = Organization(name=f"Rows {uuid.uuid4().hex[:6]}", inn=f"{uuid.uuid4().int % 10**9:09d}")
        session.add(org)
        await session.commit()
        org_id = org.id

    file_id = f"{uuid.uuid4()}_rows.csv"
    with open(os.path.join(settings.UPLOAD_DIR, file_id), "w", encoding="utf-8") as fh:
        fh.write("Sana;Tovar nomi;Summa\n")
        fh.write('03.04.2025;Non;"10 000,00"\n')
        fh.write('31.02.2025;Sut;"20 000,00"\n')   # impossible date
        fh.write('05.04.2025;Tuz;"12abc"\n')       # garbage amount

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/documents/commit", json={
            "file_id": file_id, "organization_id": str(org_id), "format_type": "GENERIC_EXCEL",
            "doc_type": "SOLIQ_SALES",
            "mapping": {"date_col": "Sana", "item_name_col": "Tovar nomi", "total_col": "Summa"},
        })

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["imported_count"] == 1
    assert body["errors_count"] == 2
    assert any("31.02.2025" in e for e in body["error_details"])
    assert any("12abc" in e for e in body["error_details"])
    async with AsyncSessionLocal() as session:
        txs = (await session.execute(select(Transaction).where(Transaction.organization_id == org_id))).scalars().all()
    await engine.dispose()
    assert [t.doc_date for t in txs] == [date(2025, 4, 3)]
