import uuid
from typing import Optional
from pydantic import BaseModel, Field

class CounterpartyBase(BaseModel):
    name: str = Field(..., max_length=255)
    inn: Optional[str] = Field(None, max_length=9)
    mfo: Optional[str] = Field(None, max_length=5)
    bank_account: Optional[str] = Field(None, max_length=20)
    is_supplier: bool = True
    is_client: bool = True

class CounterpartyCreate(CounterpartyBase):
    organization_id: uuid.UUID

class CounterpartyRead(CounterpartyBase):
    id: uuid.UUID
    organization_id: uuid.UUID

    model_config = {"from_attributes": True}

