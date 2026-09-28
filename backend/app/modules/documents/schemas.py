import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ParsedRecordItem(BaseModel):
    doc_number: Optional[str] = None
    doc_date: Optional[date] = None
    doc_type: str = "EHF"
    supplier_name: Optional[str] = None
    supplier_inn: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_inn: Optional[str] = None
    contract_number: Optional[str] = None
    item_name: Optional[str] = None
    ikpu_code: Optional[str] = None
    unit: str = "dona"
    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    vat_rate: Decimal = Decimal("0")
    vat_amount: Decimal = Decimal("0")
    total_amount: Decimal = Decimal("0")
    debit_account: Optional[str] = None
    credit_account: Optional[str] = None
    operation_type: Optional[str] = "INFLOW"
    description: Optional[str] = None

class ParsePreviewResponse(BaseModel):
    detected_type: str
    confidence: float
    filename: str
    total_rows: int
    headers: List[str]
    column_mapping: Dict[str, Optional[str]]
    preview_rows: List[Dict[str, Any]]
    parsed_records: List[ParsedRecordItem]

class CommitParsedDocumentsRequest(BaseModel):
    organization_id: uuid.UUID
    records: List[ParsedRecordItem]
    operation_type: Optional[str] = "INFLOW"
    default_debit_account: Optional[str] = None
    default_credit_account: Optional[str] = None
