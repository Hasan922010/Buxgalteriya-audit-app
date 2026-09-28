from pydantic import BaseModel, Field
from typing import List, Optional
from decimal import Decimal

class TaxAuditItemRow(BaseModel):
    item_no: int
    item_name: str
    # 1-yanvar holatiga qoldiq
    opening_qty: Decimal = Decimal("0.0")
    opening_amount: Decimal = Decimal("0.0")
    # Davr kirimi
    inflow_qty: Decimal = Decimal("0.0")
    inflow_amount: Decimal = Decimal("0.0")
    # Sotilgan (Chiqim)
    sold_qty: Decimal = Decimal("0.0")
    avg_price: Decimal = Decimal("0.0")
    sold_amount: Decimal = Decimal("0.0")
    # Davr oxiriga qoldiq
    closing_qty: Decimal = Decimal("0.0")
    closing_amount: Decimal = Decimal("0.0")
    # Kirimsiz sotilgan farq
    diff_qty: Decimal = Decimal("0.0")
    diff_amount: Decimal = Decimal("0.0")
    # Tekshiruv bayroqlari
    math_verified: bool = True
    confidence: float = 1.0

class TaxPenaltySummary(BaseModel):
    total_discrepancy_amount: Decimal  # Jami kirimsiz sotuv summasi
    vat_amount: Decimal                # QQS (12%)
    net_tax_base: Decimal              # QQSsiz baza
    profit_tax_addition: Decimal       # Foyda solig'iga qo'shimcha (15%)
    financial_penalty: Decimal         # Moliyaviy jarima (20%)
    total_budget_liability: Decimal    # Davlat byudjetiga jami to'lov

class TaxAuditDocument(BaseModel):
    company_name: str
    company_inn: str
    audit_year: int = 2023
    title: str = "Киримсиз сотилган товарлар таҳлили"
    items: List[TaxAuditItemRow]
    summary: Optional[TaxPenaltySummary] = None
    preview_image_base64: Optional[str] = None

