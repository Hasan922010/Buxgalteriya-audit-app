"""Regression tests for audit findings C4 (amount parsing) and H2 (month-first dates)."""
from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from app.modules.documents.parsers.bank_parser import BankParser as ModularBankParser
from app.modules.documents.parsers.didox_parser import DidoxParser as ModularDidoxParser
from app.modules.documents.parsers.soliq_parser import SoliqParser as ModularSoliqParser
from app.services.parsers.bank_parser import BankParser
from app.services.parsers.didox_parser import DidoxParser

AMOUNT_CASES = [
    ("1 234 567,89", Decimal("1234567.89")),
    ("1,234,567.89", Decimal("1234567.89")),
    ("1.234.567,89", Decimal("1234567.89")),
]


@pytest.mark.parametrize("raw, expected", AMOUNT_CASES)
def test_both_didox_parsers_agree_on_text_amounts(raw, expected):
    row = pd.Series({"summa": raw})
    assert ModularDidoxParser()._get_decimal(row, "summa") == expected
    assert DidoxParser._get_decimal(row, "summa") == expected
    assert BankParser._get_decimal(row, "summa") == expected


@pytest.mark.parametrize("parser_cls", [ModularBankParser, ModularSoliqParser])
@pytest.mark.parametrize("raw, expected", AMOUNT_CASES)
def test_keyword_parsers_read_text_amounts(parser_cls, raw, expected):
    row = pd.Series({"Summa": raw})
    assert parser_cls()._extract_decimal(row, ["summa"]) == expected


def test_ambiguous_date_is_read_day_first_everywhere():
    row = pd.Series({"sana": "03.04.2025"})
    expected = date(2025, 4, 3)
    assert ModularDidoxParser()._get_date(row, "sana") == expected
    assert DidoxParser._get_date(row, "sana") == expected
    assert BankParser._get_date(row, "sana") == expected
    assert ModularBankParser()._extract_date(row, ["sana"]) == expected
    assert ModularSoliqParser()._extract_date(row, ["sana"]) == expected


@pytest.mark.asyncio
async def test_manual_mapping_commit_parses_sale_and_return_amounts():
    """Review finding: the return_sum/return_qty path in documents.py still stripped commas."""
    import os
    import uuid as uuid_mod

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select

    from app.core.config import settings
    from app.core.database import AsyncSessionLocal, engine
    from app.db.seed import seed_database
    from app.main import app
    from app.models.transaction import Transaction

    await seed_database()
    file_id = f"{uuid_mod.uuid4()}_kassa.csv"
    with open(os.path.join(settings.UPLOAD_DIR, file_id), "w", encoding="utf-8") as fh:
        fh.write('Sana;Tovar nomi;Summa;Qaytarilgan summa;Qaytarilgan soni\n')
        fh.write('03.04.2025;Non;"1 234 567,89";"12 500,50";"2,5"\n')

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        org_id = (await client.get("/api/v1/organizations")).json()[0]["id"]
        resp = await client.post("/api/v1/documents/commit", json={
            "file_id": file_id,
            "organization_id": org_id,
            "format_type": "GENERIC_EXCEL",
            "doc_type": "SOLIQ_SALES",
            "mapping": {
                "date_col": "Sana", "item_name_col": "Tovar nomi", "total_col": "Summa",
                "return_sum_col": "Qaytarilgan summa", "return_qty_col": "Qaytarilgan soni",
            },
        })
    assert resp.status_code == 200, resp.text

    async with AsyncSessionLocal() as session:
        txs = (await session.execute(
            select(Transaction).where(Transaction.organization_id == uuid_mod.UUID(org_id))
        )).scalars().all()
    await engine.dispose()

    imported = [t for t in txs if "Non" in (t.description or "")]
    sale = next(t for t in imported if t.doc_type != "RETURN")
    ret = next(t for t in imported if t.doc_type == "RETURN")
    assert sale.total_amount == Decimal("1234567.89")
    assert sale.doc_date == date(2025, 4, 3)
    assert ret.total_amount == Decimal("12500.50")
    assert ret.quantity == Decimal("2.5")
