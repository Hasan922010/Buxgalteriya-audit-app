import enum
import re
from decimal import Decimal
from typing import List, Dict, Any
from app.modules.ocr.ocr_extractor import ExtractedDocument, ExtractedLineItem

class ValidationStatus(str, enum.Enum):
    VALID = "VALID"
    WARNING = "WARNING"
    ERROR = "ERROR"

class LineItemValidationResult:
    def __init__(self, item: ExtractedLineItem, status: ValidationStatus, errors: List[str], warnings: List[str]):
        self.item = item
        self.status = status
        self.errors = errors
        self.warnings = warnings

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_name": self.item.item_name,
            "ikpu_code": self.item.ikpu_code,
            "unit": self.item.unit,
            "quantity": float(self.item.quantity),
            "price": float(self.item.price),
            "vat_rate": float(self.item.vat_rate),
            "vat_amount": float(self.item.vat_amount),
            "total_amount": float(self.item.total_amount),
            "confidence": self.item.confidence,
            "status": self.status.value,
            "errors": self.errors,
            "warnings": self.warnings
        }

class DocumentValidationResult:
    def __init__(
        self,
        document: ExtractedDocument,
        status: ValidationStatus,
        line_results: List[LineItemValidationResult],
        doc_errors: List[str],
        doc_warnings: List[str]
    ):
        self.document = document
        self.status = status
        self.line_results = line_results
        self.doc_errors = doc_errors
        self.doc_warnings = doc_warnings

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_number": self.document.doc_number,
            "doc_date": str(self.document.doc_date) if self.document.doc_date else None,
            "doc_type": self.document.doc_type,
            "supplier_name": self.document.supplier_name,
            "supplier_inn": self.document.supplier_inn,
            "buyer_name": self.document.buyer_name,
            "buyer_inn": self.document.buyer_inn,
            "contract_number": self.document.contract_number,
            "contract_date": str(self.document.contract_date) if self.document.contract_date else None,
            "overall_status": self.status.value,
            "errors": self.doc_errors,
            "warnings": self.doc_warnings,
            "line_items": [lr.to_dict() for lr in self.line_results]
        }


class OCRValidator:
    """
    Validates scanned documents according to Uzbekistan accounting norms:
    1. STIR must be exactly 9 numeric digits.
    2. Mathematical consistency: abs((qty * price + vat) - total) < 0.05.
    3. Confidence threshold: confidence >= 0.85.
    4. MXIK / IKPU length: 17 numeric digits.
    """

    @staticmethod
    def validate_stir(inn: str) -> bool:
        if not inn:
            return False
        clean = re.sub(r"\D", "", str(inn))
        return len(clean) == 9 and clean != "000000000"

    @classmethod
    def validate(cls, doc: ExtractedDocument) -> DocumentValidationResult:
        doc_errors = []
        doc_warnings = []
        overall_status = ValidationStatus.VALID

        # 1. Validate STIR
        if not doc.supplier_inn or not cls.validate_stir(doc.supplier_inn):
            doc_errors.append(f"Yetkazib beruvchi STIR noto'g'ri (9 ta raqam bo'lishi kerak): '{doc.supplier_inn}'")
            overall_status = ValidationStatus.ERROR

        if doc.buyer_inn and not cls.validate_stir(doc.buyer_inn):
            doc_errors.append(f"Xaridor STIR noto'g'ri (9 ta raqam bo'lishi kerak): '{doc.buyer_inn}'")
            overall_status = ValidationStatus.ERROR

        # 2. Line Items validation
        line_results = []
        for idx, item in enumerate(doc.line_items, 1):
            errors = []
            warnings = []
            item_status = ValidationStatus.VALID

            # Check math
            calculated_subtotal = item.quantity * item.price
            expected_total = calculated_subtotal + item.vat_amount
            math_diff = abs(expected_total - item.total_amount)

            # Mathematical check: abs((qty * price + vat) - total) < 0.05
            if math_diff >= Decimal("0.05"):
                errors.append(
                    f"Satr {idx}: Matematik xatolik! Miqdor ({item.quantity}) * Narx ({item.price}) + QQS ({item.vat_amount}) = {expected_total}, lekin Jami = {item.total_amount} ko'rsatilgan (farq: {math_diff})."
                )
                item_status = ValidationStatus.ERROR
            elif math_diff > Decimal("0.00"):
                warnings.append(f"Satr {idx}: Yaxlitlashdagi kichik farq: {math_diff}")

            # Check confidence
            if item.confidence < 0.85:
                warnings.append(
                    f"Satr {idx}: Skanerlash ishonchliligi past ({int(item.confidence * 100)}%). Qo'lda tekshirish tavsiya etiladi."
                )
                if item_status == ValidationStatus.VALID:
                    item_status = ValidationStatus.WARNING

            # Check IKPU
            if item.ikpu_code:
                clean_ikpu = re.sub(r"\D", "", item.ikpu_code)
                if len(clean_ikpu) != 17:
                    warnings.append(f"Satr {idx}: MXIK kodi 17 ta raqamdan iborat bo'lishi lozim: '{item.ikpu_code}'")
                    if item_status == ValidationStatus.VALID:
                        item_status = ValidationStatus.WARNING

            if item_status == ValidationStatus.ERROR:
                overall_status = ValidationStatus.ERROR
            elif item_status == ValidationStatus.WARNING and overall_status != ValidationStatus.ERROR:
                overall_status = ValidationStatus.WARNING

            line_results.append(LineItemValidationResult(item, item_status, errors, warnings))

        return DocumentValidationResult(doc, overall_status, line_results, doc_errors, doc_warnings)
