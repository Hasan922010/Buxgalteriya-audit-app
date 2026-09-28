import os
from decimal import Decimal
from app.services.parsers.didox_parser import DidoxParser
from app.services.parsers.bank_parser import BankParser
import pandas as pd

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_data")

def test_didox_parser():
    file_path = os.path.join(SAMPLE_DIR, "sample_didox.xlsx")
    assert os.path.exists(file_path)

    df = pd.read_excel(file_path)
    is_match, conf = DidoxParser.detect_format(df, list(df.columns))
    assert is_match == True
    assert conf >= 0.5

    parser = DidoxParser()
    records = parser.parse_file(file_path)
    assert len(records) == 3

    rec1 = records[0]
    assert rec1.doc_number == "EHF-101"
    assert rec1.counterparty_inn == "301234567"
    assert rec1.total_amount == Decimal("4480000.00")
    assert rec1.vat_amount == Decimal("480000.00")
    assert rec1.ikpu_code == "01712001001000000"

def test_bank_parser():
    file_path = os.path.join(SAMPLE_DIR, "sample_bank.xlsx")
    assert os.path.exists(file_path)

    df = pd.read_excel(file_path)
    is_match, conf = BankParser.detect_format(df, list(df.columns))
    assert is_match == True

    parser = BankParser()
    records = parser.parse_file(file_path)
    assert len(records) == 3

    rec1 = records[0] # Kirim (Inflow)
    assert rec1.doc_number == "PP-501"
    assert rec1.counterparty_inn == "309876543"
    assert rec1.total_amount == Decimal("25000000.00")
    assert rec1.debit_account == "5110"
    assert rec1.credit_account == "4000"

    rec3 = records[2] # Tax payment
    assert rec3.doc_number == "PP-503"
    assert rec3.total_amount == Decimal("2400000.00")
    assert rec3.debit_account == "6800" # Tax payable
    assert rec3.credit_account == "5110" # Bank account

def test_soliq_sales_parser_and_smart_mapper():
    from app.services.parsers.smart_excel_mapper import SmartExcelMapper
    from app.services.parsers.soliq_parser import SoliqParser

    headers = [
        "№",
        "Маҳсулот (хизмат) номи",
        "Штрих (GTIN) код",
        "Махсулотлар ва хизматлар идентификацион коди (МХИК)",
        "Ўртача маҳсулот (хизмат) қиймати",
        "Маҳсулотнинг охирги сотилган вақти",
        "Сотилган маҳсулот (хизмат) сони (дона/кг)",
        "Сотилган маҳсулот (хизмат) суммаси",
        "Қайтарилган маҳсулот (хизмат) сони (дона/кг)",
        "Қайтарилган маҳсулот (хизмат) суммаси"
    ]

    # Test auto mapping
    mapping = SmartExcelMapper._heuristic_mapping(headers)
    assert mapping.doc_num_col == "№"
    assert mapping.item_name_col == "Маҳсулот (хизмат) номи"
    assert mapping.barcode_col == "Штрих (GTIN) код"
    assert mapping.ikpu_col == "Махсулотлар ва хизматлар идентификацион коди (МХИК)"
    assert mapping.price_col == "Ўртача маҳсулот (хизмат) қиймати"
    assert mapping.date_col == "Маҳсулотнинг охирги сотилган вақти"
    assert mapping.qty_col == "Сотилган маҳсулот (хизмат) сони (дона/кг)"
    assert mapping.return_qty_col == "Қайтарилган маҳсулот (хизмат) сони (дона/кг)"
    assert mapping.return_sum_col == "Қайтарилган маҳсулот (хизмат) суммаси"

def test_modular_document_parsers():
    from app.modules.documents.parsers.didox_parser import DidoxParser as ModularDidoxParser
    from app.modules.documents.parsers.bank_parser import BankParser as ModularBankParser
    from app.modules.documents.services import DocumentIngestionService
    from sqlalchemy.ext.asyncio import AsyncSession

    didox_path = os.path.join(SAMPLE_DIR, "sample_didox.xlsx")
    bank_path = os.path.join(SAMPLE_DIR, "sample_bank.xlsx")

    # 1. Test Modular Didox Parser
    didox_parser = ModularDidoxParser()
    didox_records = didox_parser.parse_file(didox_path)
    assert len(didox_records) == 3
    assert didox_records[0].doc_number == "EHF-101"
    assert didox_records[0].total_amount == Decimal("4480000.00")
    assert didox_records[0].debit_account == "2900"
    assert didox_records[0].credit_account == "6000"

    # 2. Test Modular Bank Parser
    bank_parser = ModularBankParser()
    bank_records = bank_parser.parse_file(bank_path)
    assert len(bank_records) == 3
    # First record is Kirim (5110 Debit, 4000 Credit)
    assert bank_records[0].debit_account == "5110"
    assert bank_records[0].credit_account == "4000"
    assert bank_records[0].total_amount == Decimal("25000000.00")

    # 3. Test Ingestion Service preview
    service = DocumentIngestionService(session=None)
    preview = service.inspect_and_preview(didox_path, "sample_didox.xlsx")
    assert preview.detected_type == "DIDOX"
    assert preview.total_rows == 3
    assert len(preview.parsed_records) == 3


