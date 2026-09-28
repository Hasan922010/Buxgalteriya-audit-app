import uuid
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field
from app.models.account import AccountingMode

class OrganizationBase(BaseModel):
    name: str = Field(..., max_length=255)
    inn: str = Field(..., min_length=9, max_length=9, description="STIR (9 raqam)")
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

class OrganizationLockRequest(BaseModel):
    locked_until_date: Optional[date] = None

class OrganizationRead(OrganizationBase):
    id: uuid.UUID
    created_at: Optional[date] = None

    model_config = {"from_attributes": True}

