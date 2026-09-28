import uuid
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field

class InventoryItemBase(BaseModel):
    name: str = Field(..., max_length=255)
    ikpu_code: Optional[str] = Field(None, max_length=50, description="17 xonali MXIK kodi")
    package_code: Optional[str] = Field(None, max_length=50)
    unit: str = Field(default="dona", max_length=50)
    min_stock_alert: Decimal = Decimal("0")

class InventoryItemCreate(InventoryItemBase):
    organization_id: uuid.UUID

class InventoryItemRead(InventoryItemBase):
    id: uuid.UUID
    organization_id: uuid.UUID

    model_config = {"from_attributes": True}

