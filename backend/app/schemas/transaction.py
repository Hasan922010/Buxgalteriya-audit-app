import uuid
from datetime import date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field

class TransactionBase(BaseModel):
    doc_number: Optional[str] = None
    doc_date: date
    doc_type: str = Field(default="MANUAL", description="'EHF', 'BANK', 'STOCK', 'MANUAL'")
    debit_account: Optional[str] = Field(None, max_length=10)
    credit_account: Optional[str] = Field(None, max_length=10)
    counterparty_id: Optional[uuid.UUID] = None
    item_id: Optional[uuid.UUID] = None
    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    total_amount: Decimal = Field(..., gt=Decimal("-1000000000000"))
    vat_rate: Decimal = Decimal("0")
    vat_amount: Decimal = Decimal("0")
    description: Optional[str] = None
    raw_payload: Optional[str] = None

class TransactionCreate(TransactionBase):
    organization_id: uuid.UUID

class TransactionRead(TransactionBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    counterparty_name: Optional[str] = None
    item_name: Optional[str] = None

    model_config = {"from_attributes": True}


class TransactionFilter(BaseModel):
    organization_id: uuid.UUID
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    account: Optional[str] = None
    counterparty_id: Optional[uuid.UUID] = None
    item_id: Optional[uuid.UUID] = None
    doc_type: Optional[str] = None
