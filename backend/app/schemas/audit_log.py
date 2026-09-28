import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class AuditLogRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    performed_by: str
    details: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class StornoRequest(BaseModel):
    reason: str
    performed_by: Optional[str] = "Bosh Buxgalter"
