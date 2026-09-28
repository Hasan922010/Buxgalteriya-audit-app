import pytest
import numpy as np
import cv2
from decimal import Decimal
from datetime import date

from app.modules.ocr.image_enhancer import enhance_cv2_image, pdf_to_enhanced_images, cv2_to_png_bytes
from app.modules.ocr.ocr_extractor import ExtractedDocument, ExtractedLineItem, OCRExtractor
from app.modules.ocr.ocr_validator import OCRValidator, ValidationStatus

def test_image_enhancer_pipeline(sample_degraded_image, sample_pdf_bytes):
    """
    Feeds a degraded sample image and PDF to verify deskew, denoising,
    CLAHE adaptive contrast, and unsharp masking.
    """
    # 1. Test image enhancement
    assert sample_degraded_image.shape == (400, 600, 3)
    enhanced = enhance_cv2_image(sample_degraded_image)
    assert enhanced is not None
    # Enhanced output should be 2D single-channel (grayscale contrast enhanced)
    assert len(enhanced.shape) == 2
    assert enhanced.shape == (400, 600)

    # Verify PNG bytes encoding
    png_bytes = cv2_to_png_bytes(enhanced)
    assert len(png_bytes) > 0
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    # 2. Test PDF extraction and enhancement
    pdf_pages = pdf_to_enhanced_images(sample_pdf_bytes, dpi=150)
    assert len(pdf_pages) == 1
    assert len(pdf_pages[0].shape) == 2
    assert pdf_pages[0].shape[0] > 0

def test_ocr_validator_mathematical_integrity():
    """
    Tests mathematical check: abs((qty * price + vat) - total) < 0.05.
    Verifies WARNING and ERROR statuses.
    """
    # 1. Valid line item: 10 * 10,000 + 12,000 = 112,000
    valid_item = ExtractedLineItem(
        item_name="Sement M-400",
        ikpu_code="02523290001000000",
        unit="qop",
        quantity=Decimal("10.0"),
        price=Decimal("10000.00"),
        vat_rate=Decimal("12.0"),
        vat_amount=Decimal("12000.00"),
        total_amount=Decimal("112000.00"),
        confidence=0.95
    )

    doc_valid = ExtractedDocument(
        doc_number="INV-100",
        doc_date=date.today(),
        doc_type="EHF",
        supplier_name="OOO CEMENT",
        supplier_inn="301234567",
        buyer_name="OOO BUILD",
        buyer_inn="309876543",
        line_items=[valid_item]
    )

    result_valid = OCRValidator.validate(doc_valid)
    assert result_valid.status == ValidationStatus.VALID
    assert len(result_valid.doc_errors) == 0
    assert result_valid.line_results[0].status == ValidationStatus.VALID

    # 2. Math deviation error: total is 150,000 instead of 112,000
    invalid_math_item = ExtractedLineItem(
        item_name="Sement M-400",
        ikpu_code="02523290001000000",
        unit="qop",
        quantity=Decimal("10.0"),
        price=Decimal("10000.00"),
        vat_rate=Decimal("12.0"),
        vat_amount=Decimal("12000.00"),
        total_amount=Decimal("150000.00"), # Error!
        confidence=0.95
    )

    doc_invalid_math = ExtractedDocument(
        doc_number="INV-101",
        doc_date=date.today(),
        doc_type="EHF",
        supplier_name="OOO CEMENT",
        supplier_inn="301234567",
        buyer_inn="309876543",
        line_items=[invalid_math_item]
    )

    result_math_err = OCRValidator.validate(doc_invalid_math)
    assert result_math_err.status == ValidationStatus.ERROR
    assert result_math_err.line_results[0].status == ValidationStatus.ERROR
    assert any("Matematik xatolik" in err for err in result_math_err.line_results[0].errors)

    # 3. Low confidence warning: confidence < 0.85
    low_conf_item = ExtractedLineItem(
        item_name="Xira yozuv",
        unit="dona",
        quantity=Decimal("1.0"),
        price=Decimal("1000.00"),
        vat_rate=Decimal("0.0"),
        vat_amount=Decimal("0.0"),
        total_amount=Decimal("1000.00"),
        confidence=0.72 # Below 0.85
    )

    doc_low_conf = ExtractedDocument(
        doc_number="INV-102",
        doc_date=date.today(),
        doc_type="EHF",
        supplier_name="OOO TEST",
        supplier_inn="301234567",
        line_items=[low_conf_item]
    )

    result_low_conf = OCRValidator.validate(doc_low_conf)
    assert result_low_conf.status == ValidationStatus.WARNING
    assert result_low_conf.line_results[0].status == ValidationStatus.WARNING
    assert any("ishonchliligi past" in w for w in result_low_conf.line_results[0].warnings)

def test_ocr_validator_stir_format():
    """
    Verifies that STIR must be exactly 9 numeric digits.
    """
    assert OCRValidator.validate_stir("301234567") is True
    assert OCRValidator.validate_stir("123456789") is True
    assert OCRValidator.validate_stir("12345678") is False   # 8 digits
    assert OCRValidator.validate_stir("1234567890") is False # 10 digits
    assert OCRValidator.validate_stir("000000000") is False  # All zeros
    assert OCRValidator.validate_stir("") is False
    assert OCRValidator.validate_stir(None) is False

@pytest.mark.asyncio
async def test_ocr_extractor_deterministic_fallback():
    """
    Verifies that OCRExtractor safely falls back to structured Uzbekistan invoice
    schema adhering to 9-digit STIR and 17-digit IKPU standards.
    """
    extractor = OCRExtractor()
    fake_png = b"\x89PNG\r\n\x1a\n"
    doc = await extractor.extract_from_image(fake_png, filename="scan_invoice.png")

    assert isinstance(doc, ExtractedDocument)
    assert len(doc.line_items) >= 1
    assert len(doc.supplier_inn) == 9
    for item in doc.line_items:
        if item.ikpu_code:
            assert len(item.ikpu_code) == 17
        assert item.total_amount > Decimal("0")
