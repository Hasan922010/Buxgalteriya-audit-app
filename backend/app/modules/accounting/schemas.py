import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from app.modules.accounting.models import AccountingMode, AccountType

# --- Organization Schemas ---
class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    inn: str = Field(..., min_length=9, max_length=9, pattern=r"^\d{9}$", description="9-digit STIR/INN")
    mode: AccountingMode = AccountingMode.SIMPLE
    vat_payer: bool = False
    locked_until_date: Optional[date] = None

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    mode: Optional[AccountingMode] = None
    vat_payer: Optional[bool] = None
    locked_until_date: Optional[date] = None

class OrganizationOut(OrganizationBase):
    id: uuid.UUID
    created_at: date

    model_config = {"from_attributes": True}


# --- Chart of Accounts Schemas ---
class ChartOfAccountBase(BaseModel):
    code: str = Field(..., min_length=4, max_length=10)
    name: str = Field(..., min_length=2, max_length=255)
    account_type: AccountType
    is_active: bool = True

class ChartOfAccountCreate(ChartOfAccountBase):
    pass

class ChartOfAccountOut(ChartOfAccountBase):
    model_config = {"from_attributes": True}


# --- Counterparty Schemas ---
class CounterpartyBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    inn: Optional[str] = Field(None, pattern=r"^\d{9}$")
    mfo: Optional[str] = Field(None, pattern=r"^\d{5}$")
    bank_account: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=50)
    is_supplier: bool = True
    is_client: bool = True

class CounterpartyCreate(CounterpartyBase):
    organization_id: uuid.UUID

class CounterpartyUpdate(BaseModel):
    name: Optional[str] = None
    inn: Optional[str] = None
    mfo: Optional[str] = None
    bank_account: Optional[str] = None
    phone: Optional[str] = None
    is_supplier: Optional[bool] = None
    is_client: Optional[bool] = None

class CounterpartyOut(CounterpartyBase):
    id: uuid.UUID
    organization_id: uuid.UUID

    model_config = {"from_attributes": True}


# --- Inventory Item Schemas ---
class InventoryItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    ikpu_code: Optional[str] = Field(None, max_length=50, description="17-digit MXIK / IKPU")
    package_code: Optional[str] = None
    unit: str = Field(default="dona", max_length=50)
    min_stock_alert: Decimal = Decimal("0")

class InventoryItemCreate(InventoryItemBase):
    organization_id: uuid.UUID

class InventoryItemUpdate(BaseModel):
    name: Optional[str] = None
    ikpu_code: Optional[str] = None
    package_code: Optional[str] = None
    unit: Optional[str] = None
    min_stock_alert: Optional[Decimal] = None

class InventoryItemOut(InventoryItemBase):
    id: uuid.UUID
    organization_id: uuid.UUID

    model_config = {"from_attributes": True}


# --- Transaction Schemas ---
class TransactionBase(BaseModel):
    doc_number: Optional[str] = None
    doc_date: date
    doc_type: str = Field(default="MANUAL", description="'EHF', 'BANK_PAYMENT', 'CASH', 'STOCK', 'MANUAL'")
    debit_account: Optional[str] = Field(None, max_length=10)
    credit_account: Optional[str] = Field(None, max_length=10)
    counterparty_id: Optional[uuid.UUID] = None
    item_id: Optional[uuid.UUID] = None
    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    vat_rate: Decimal = Decimal("0")
    vat_amount: Decimal = Decimal("0")
    total_amount: Decimal
    description: Optional[str] = None
    raw_payload: Optional[str] = None

    @field_validator("quantity", "price", "vat_rate", "vat_amount", "total_amount", mode="before")
    @classmethod
    def convert_to_decimal(cls, v):
        if v is None:
            return Decimal("0")
        if isinstance(v, (int, float, str)):
            return Decimal(str(v))
        return v

class TransactionCreate(TransactionBase):
    organization_id: uuid.UUID

class TransactionUpdate(BaseModel):
    doc_number: Optional[str] = None
    doc_date: Optional[date] = None
    doc_type: Optional[str] = None
    debit_account: Optional[str] = None
    credit_account: Optional[str] = None
    counterparty_id: Optional[uuid.UUID] = None
    item_id: Optional[uuid.UUID] = None
    quantity: Optional[Decimal] = None
    price: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = None
    vat_amount: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    description: Optional[str] = None

class TransactionOut(TransactionBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    is_reversed: bool = False
    reversal_ref_id: Optional[uuid.UUID] = None
    reversal_reason: Optional[str] = None
    created_at: date
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
