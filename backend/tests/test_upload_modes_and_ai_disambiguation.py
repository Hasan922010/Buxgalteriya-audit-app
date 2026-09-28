import pytest
import io
import uuid
from decimal import Decimal
from datetime import date
import pymupdf

from app.modules.accounting.item_disambiguator import ItemDisambiguator
from app.modules.accounting.services import AccountingService
from app.modules.accounting.schemas import OrganizationCreate, TransactionCreate
from app.modules.accounting.models import AccountingMode, InventoryItem
from app.modules.documents.schemas import ParsedRecordItem
from app.modules.documents.services import DocumentIngestionService
from app.modules.ocr.pdf_table_extractor import PDFTableExtractor
from app.modules.ocr.excel_exporter import OCRExcelExporter


def test_item_disambiguator_distinguishes_subtle_suffixes():
    """Verifies that trailing modifiers / suffixes result in distinct items."""
    # Physical state & qualities
    assert ItemDisambiguator.are_distinct_items("G'isht M-100 pishiq", "G'isht M-100 xom") is True
    assert ItemDisambiguator.are_distinct_items("Kraska oq", "Kraska qora") is True

    # Weight / volume differences
    assert ItemDisambiguator.are_distinct_items("Qog'oz A4 80g", "Qog'oz A4 75g") is True
    assert ItemDisambiguator.are_distinct_items("Sement M-400 50kg", "Sement M-400 25kg") is True
    assert ItemDisambiguator.are_distinct_items("Moy 5L", "Moy 1L") is True

    # Dimensions & multipliers
    assert ItemDisambiguator.are_distinct_items("Truba d-20mm", "Truba d-25mm") is True
    assert ItemDisambiguator.are_distinct_items("Kabel VVG 3x1.5", "Kabel VVG 3x2.5") is True

    # Grades & product tiers
    assert ItemDisambiguator.are_distinct_items("Un 1-nav", "Un 2-nav") is True
    assert ItemDisambiguator.are_distinct_items("SvetoCopy Classic", "SvetoCopy Premium") is True

    # Identical items with different case or whitespace should NOT be distinct
    assert ItemDisambiguator.are_distinct_items("Qog'oz A4 80g", "qog'oz  a4  80g") is False
    assert ItemDisambiguator.are_distinct_items("G'isht M-100 pishiq", "G\u2018isht M-100 pishiq") is False


def test_find_best_match_preserves_item_separation():
    """Verifies candidate lookup strictly rejects items with conflicting suffixes."""
    class DummyItem:
        def __init__(self, id, name, ikpu_code=None):
            self.id = id
            self.name = name
            self.ikpu_code = ikpu_code

    pool = [
        DummyItem(1, "G'isht M-100 xom", "02501001001000000"),
        DummyItem(2, "Qog'oz A4 75g", "04802001001000000"),
        DummyItem(3, "Truba d-20mm", "03901001001000000"),
    ]

    # Target: "G'isht M-100 pishiq" shares IKPU with item 1, but suffix conflicts!
    match = ItemDisambiguator.find_best_match("G'isht M-100 pishiq", pool, "02501001001000000")
    assert match is None  # MUST NOT MATCH!

    # Target: "qog'oz a4 75g" matches item 2
    match2 = ItemDisambiguator.find_best_match("qog'oz a4 75g", pool, "04802001001000000")
    assert match2 is not None
    assert match2.id == 2


@pytest.mark.asyncio
async def test_accounting_service_item_separation_in_db(db_session):
    """
    Tests that two items with identical MXIK (IKPU) code but different
    trailing suffixes create two distinct InventoryItem rows in the database.
    """
    service = AccountingService(db_session)
    org = await service.create_organization(
        OrganizationCreate(
            name="Disambiguation Test Org",
            inn="777666555",
            mode=AccountingMode.BHMS,
            vat_payer=True
        )
    )

    shared_ikpu = "02501001001000000"

    # Insert Item 1: "G'isht M-100 pishiq"
    item1 = await service.get_or_create_inventory_item(
        org_id=org.id,
        name="G'isht M-100 pishiq",
        ikpu_code=shared_ikpu,
        unit="dona"
    )

    # Insert Item 2: "G'isht M-100 xom" with SAME IKPU!
    item2 = await service.get_or_create_inventory_item(
        org_id=org.id,
        name="G'isht M-100 xom",
        ikpu_code=shared_ikpu,
        unit="dona"
    )

    # Items MUST be distinct!
    assert item1.id != item2.id
    assert item1.name == "G'isht M-100 pishiq"
    assert item2.name == "G'isht M-100 xom"

    # Re-fetching "g'isht m-100 pishiq" should match item1
    item1_again = await service.get_or_create_inventory_item(
        org_id=org.id,
        name="g'isht m-100 pishiq",
        ikpu_code=shared_ikpu,
        unit="dona"
    )
    assert item1_again.id == item1.id


@pytest.mark.asyncio
async def test_upload_modes_initial_balance_posting(db_session):
    """
    Verifies that uploading with operation_type="INITIAL_BALANCE" posts
    Debit 2900 / Credit 8300 with 0% VAT.
    """
    service = AccountingService(db_session)
    ingestion_service = DocumentIngestionService(db_session)

    org = await service.create_organization(
        OrganizationCreate(
            name="Initial Balance Test Org",
            inn="888777666",
            mode=AccountingMode.BHMS,
            vat_payer=True
        )
    )

    record = ParsedRecordItem(
        doc_number="INIT-01",
        doc_date=date.today(),
        item_name="Ombordagi boshlang'ich sement",
        unit="qop",
        quantity=Decimal("100"),
        price=Decimal("65000"),
        total_amount=Decimal("6500000"),
        vat_rate=Decimal("12"),  # Incoming might have VAT, but initial balances have 0% VAT
        vat_amount=Decimal("780000"),
        operation_type="INITIAL_BALANCE"
    )

    result = await ingestion_service.commit_parsed_records(
        org_id=org.id,
        records=[record],
        operation_type="INITIAL_BALANCE"
    )

    assert result["success"] is True
    assert result["committed_count"] == 1

    # Verify transaction in DB
    tx = await service.tx_repo.get_by_id(uuid.UUID(result["transaction_ids"][0]))
    assert tx is not None
    assert tx.debit_account == "2900"
    assert tx.credit_account == "8300"
    assert tx.vat_rate == Decimal("0")
    assert tx.vat_amount == Decimal("0")
    assert tx.doc_type == "INITIAL_BALANCE"


def test_pdf_table_extractor_and_excel_export():
    """
    Creates a sample in-memory PDF with a structured table, extracts items
    using PDFTableExtractor, and verifies that OCRExcelExporter generates a valid .xlsx file.
    """
    # 1. Create a synthetic PDF with PyMuPDF
    pdf_doc = pymupdf.open()
    page = pdf_doc.new_page()

    # Draw invoice header text
    page.insert_text((50, 50), "HISOBVARAQ-FAKTURA No. 405", fontsize=14)
    page.insert_text((50, 70), "Sana: 15.09.2026", fontsize=10)
    page.insert_text((50, 90), "Yetkazib beruvchi: OOO GRAND STROY INN: 301234567", fontsize=10)
    page.insert_text((50, 110), "Xaridor: OOO INVEST TECH INN: 209876543", fontsize=10)

    # Draw a table with rects and text
    table_data = [
        ["T/r", "Tovar nomi", "O'lchov", "Miqdor", "Narx", "Jami summa"],
        ["1", "Sement M-400 (50kg)", "qop", "50", "60000", "3000000"],
        ["2", "Armatura 12mm", "metr", "200", "15000", "3000000"]
    ]

    # Draw table text
    y = 150
    for row in table_data:
        x = 50
        for cell in row:
            page.insert_text((x, y), cell, fontsize=9)
            x += 80
        y += 25

    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()

    # 2. Extract structured document from PDF
    extracted = PDFTableExtractor.extract_document_from_pdf(pdf_bytes)
    assert extracted is not None
    assert extracted.doc_number == "405"
    assert extracted.supplier_inn == "301234567"
    assert extracted.buyer_inn == "209876543"

    # 3. Export to authentic Excel (.xlsx)
    excel_buf = OCRExcelExporter.export_document_to_excel(extracted)
    assert excel_buf is not None
    excel_bytes = excel_buf.getvalue()
    assert len(excel_bytes) > 1000  # Valid Excel file size
    assert excel_bytes[:4] == b"PK\x03\x04"  # Standard ZIP / XLSX magic signature
