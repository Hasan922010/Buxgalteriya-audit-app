from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from app.services.parsers.normalize import parse_amount, parse_date


@pytest.mark.parametrize(
    "raw, expected",
    [
        # Uzbek / Russian locale: space thousands, comma decimal
        ("1 234 567,89", "1234567.89"),
        ("1 234 567,89", "1234567.89"),
        ("1 234,5", "1234.5"),
        ("12 500", "12500"),
        ("2,5", "2.5"),
        ("2,500", "2.500"),
        # English locale: comma thousands, dot decimal
        ("1,234,567.89", "1234567.89"),
        ("1,234,567", "1234567"),
        # European dot-thousands
        ("1.234.567,89", "1234567.89"),
        ("1.234.567", "1234567"),
        # Plain / numeric cell values
        ("1234567.89", "1234567.89"),
        ("0.125", "0.125"),
        (1234567.89, "1234567.89"),
        (12500, "12500"),
        (Decimal("99.10"), "99.10"),
        (np.float64(15.5), "15.5"),
        # Currency labels and apostrophe grouping
        ("1 250 000 so'm", "1250000"),
        ("1 250 000,00 сум", "1250000.00"),
        ("UZS 3 000", "3000"),
        ("1'234'567", "1234567"),
        # Negatives
        ("-1 500,25", "-1500.25"),
        ("−1 500", "-1500"),
        ("(2 000,00)", "-2000.00"),
    ],
)
def test_parse_amount_handles_common_formats(raw, expected):
    assert parse_amount(raw) == Decimal(expected)


@pytest.mark.parametrize("raw", [None, "", "   ", float("nan"), np.nan, pd.NA, "-", "nan"])
def test_parse_amount_returns_none_for_empty(raw):
    assert parse_amount(raw) is None


@pytest.mark.parametrize("raw", ["abc", "12abc34", "1,2,3.4.5", "--5", "1.2.3,4,5", True])
def test_parse_amount_returns_none_for_garbage(raw):
    assert parse_amount(raw) is None


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("03.04.2025", date(2025, 4, 3)),
        ("25.04.2025", date(2025, 4, 25)),
        ("03.04.25", date(2025, 4, 3)),
        ("03/04/2025", date(2025, 4, 3)),
        ("03-04-2025", date(2025, 4, 3)),
        ("2025-04-03", date(2025, 4, 3)),
        ("2025.04.03", date(2025, 4, 3)),
        ("03.04.2025 14:30", date(2025, 4, 3)),
        ("03.04.2025 14:30:15", date(2025, 4, 3)),
        ("2025-04-03T10:00:00", date(2025, 4, 3)),
        (" 01.12.2024 ", date(2024, 12, 1)),
        (date(2025, 4, 3), date(2025, 4, 3)),
        (datetime(2025, 4, 3, 9, 15), date(2025, 4, 3)),
        (pd.Timestamp("2025-04-03"), date(2025, 4, 3)),
        (45750, date(2025, 4, 3)),  # Excel serial date
    ],
)
def test_parse_date_is_day_first(raw, expected):
    assert parse_date(raw) == expected


@pytest.mark.parametrize("raw", [None, "", float("nan"), pd.NaT, "abc", "32.01.2025", "13/13/2025", "04/31/2025", 12])
def test_parse_date_returns_none_for_invalid(raw):
    assert parse_date(raw) is None


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("20 025 600,00", "20025600.00"),
        ("1,234,567.89", "1234567.89"),
        ("12 500,00 so'm*", "12500.00"),
        ("~1 500,5|", "1500.5"),
    ],
)
def test_ocr_extractors_read_noisy_amounts(raw, expected):
    from app.modules.ocr.pdf_table_extractor import PDFTableExtractor
    from app.modules.ocr.tax_audit_extractor import TaxAuditExtractor

    assert PDFTableExtractor.clean_decimal(raw) == Decimal(expected)
    assert TaxAuditExtractor.clean_decimal(raw) == Decimal(expected)
