import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class DetectedFormat(BaseModel):
    format_type: str = Field(..., description="'DIDOX_EHF', 'BANK_STATEMENT', 'SOLIQ_REGISTRY', 'MATERIAL_REPORT', 'GENERIC_EXCEL', 'UNKNOWN'")
    confidence: float = 1.0
    detected_headers: List[str] = []
    total_rows: int = 0
    sample_rows: List[Dict[str, Any]] = []

class UploadResponse(BaseModel):
    file_id: str
    filename: str
    detected_format: DetectedFormat
    message: str

class ColumnMapping(BaseModel):
    date_col: Optional[str] = None
    doc_num_col: Optional[str] = None
    item_name_col: Optional[str] = None
    counterparty_col: Optional[str] = None
    counterparty_inn_col: Optional[str] = None
    ikpu_col: Optional[str] = None
    barcode_col: Optional[str] = None
    unit_col: Optional[str] = None
    qty_col: Optional[str] = None
    price_col: Optional[str] = None
    total_col: Optional[str] = None
    vat_rate_col: Optional[str] = None
    vat_amount_col: Optional[str] = None
    debit_acc_col: Optional[str] = None
    credit_acc_col: Optional[str] = None
    initial_qty_col: Optional[str] = None
    initial_sum_col: Optional[str] = None
    inflow_qty_col: Optional[str] = None
    inflow_sum_col: Optional[str] = None
    outflow_qty_col: Optional[str] = None
    outflow_sum_col: Optional[str] = None
    final_qty_col: Optional[str] = None
    final_sum_col: Optional[str] = None
    return_qty_col: Optional[str] = None
    return_sum_col: Optional[str] = None

class PreviewMappingResponse(BaseModel):
    file_id: str
    detected_format: str
    available_columns: List[str]
    proposed_mapping: ColumnMapping
    sample_preview: List[Dict[str, Any]]

class CommitMappingRequest(BaseModel):
    file_id: str
    organization_id: uuid.UUID
    format_type: str
    mapping: Optional[ColumnMapping] = None
    doc_type: Optional[str] = "EHF"
    operation_type: Optional[str] = "INFLOW"  # 'INITIAL_BALANCE', 'INFLOW', 'OUTFLOW'
    default_debit_account: Optional[str] = None
    default_credit_account: Optional[str] = None
    # Re-import a file this organization already booked (otherwise rejected with 409)
    allow_duplicate: bool = False

class CommitResponse(BaseModel):
    success: bool
    imported_count: int
    errors_count: int
    message: str
    error_details: List[str] = []
