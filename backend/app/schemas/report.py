import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel

# --- 1. Aylanma Qoldiq Vedomosti (OSV - Trial Balance) ---
class TrialBalanceItem(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    initial_debit: Decimal = Decimal("0.00")
    initial_credit: Decimal = Decimal("0.00")
    turnover_debit: Decimal = Decimal("0.00")
    turnover_credit: Decimal = Decimal("0.00")
    final_debit: Decimal = Decimal("0.00")
    final_credit: Decimal = Decimal("0.00")

class TrialBalanceReport(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    from_date: date
    to_date: date
    items: List[TrialBalanceItem]
    total_initial_debit: Decimal = Decimal("0.00")
    total_initial_credit: Decimal = Decimal("0.00")
    total_turnover_debit: Decimal = Decimal("0.00")
    total_turnover_credit: Decimal = Decimal("0.00")
    total_final_debit: Decimal = Decimal("0.00")
    total_final_credit: Decimal = Decimal("0.00")
    is_balanced: bool = True

# --- 2. Moddiy Hisobot (Material Stock Movement) ---
class MaterialReportItem(BaseModel):
    item_id: uuid.UUID
    item_name: str
    ikpu_code: Optional[str] = None
    unit: str = "dona"
    initial_qty: Decimal = Decimal("0.000")
    initial_sum: Decimal = Decimal("0.00")
    inflow_qty: Decimal = Decimal("0.000")
    inflow_sum: Decimal = Decimal("0.00")
    outflow_qty: Decimal = Decimal("0.000")
    outflow_sum: Decimal = Decimal("0.00")
    avg_price: Decimal = Decimal("0.00")
    final_qty: Decimal = Decimal("0.000")
    final_sum: Decimal = Decimal("0.00")
    # True when issues exceed receipts at some point (missing inflow documents)
    has_negative_stock: bool = False

class MaterialReportMxikGroup(BaseModel):
    ikpu_code: str
    ikpu_name: Optional[str] = None
    items_count: int = 0
    unit: Optional[str] = "dona"
    initial_qty: Decimal = Decimal("0.000")
    initial_sum: Decimal = Decimal("0.00")
    inflow_qty: Decimal = Decimal("0.000")
    inflow_sum: Decimal = Decimal("0.00")
    outflow_qty: Decimal = Decimal("0.000")
    outflow_sum: Decimal = Decimal("0.00")
    final_qty: Decimal = Decimal("0.000")
    final_sum: Decimal = Decimal("0.00")

class MaterialReport(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    from_date: date
    to_date: date
    items: List[MaterialReportItem]
    mxik_groups: List[MaterialReportMxikGroup] = []
    total_initial_sum: Decimal = Decimal("0.00")
    total_inflow_sum: Decimal = Decimal("0.00")
    total_outflow_sum: Decimal = Decimal("0.00")
    total_final_sum: Decimal = Decimal("0.00")

# --- 3. Akt Sverka (Counterparty Reconciliation) ---
class AktSverkaItem(BaseModel):
    date: date
    doc_number: str
    doc_type: str
    description: Optional[str] = None
    debit: Decimal = Decimal("0.00")   # Tovarlar yetkazib berish (Bizning haqimiz oshishi)
    credit: Decimal = Decimal("0.00")  # To'lov qabul qilish / qarz kamayishi
    running_balance: Decimal = Decimal("0.00")

class AktSverkaReport(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    counterparty_id: uuid.UUID
    counterparty_name: str
    counterparty_inn: Optional[str] = None
    from_date: date
    to_date: date
    initial_debt: Decimal = Decimal("0.00")
    total_debit: Decimal = Decimal("0.00")
    total_credit: Decimal = Decimal("0.00")
    final_debt: Decimal = Decimal("0.00")
    status_uz: str
    items: List[AktSverkaItem]

# --- 4. Dashboard KPIs ---
class DashboardKPIs(BaseModel):
    monthly_inflow: Decimal = Decimal("0.00")
    monthly_outflow: Decimal = Decimal("0.00")
    net_cash_balance: Decimal = Decimal("0.00")
    inventory_valuation: Decimal = Decimal("0.00")
    total_receivables: Decimal = Decimal("0.00")
    total_payables: Decimal = Decimal("0.00")
    mode: str = "SIMPLE"
