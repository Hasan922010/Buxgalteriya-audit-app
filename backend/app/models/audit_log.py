import uuid
from datetime import datetime
from sqlalchemy import Column, String, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)  # 'CREATE_TRANSACTION', 'STORNO_TRANSACTION', 'LOCK_PERIOD', 'UNLOCK_PERIOD', 'IMPORT_DOCUMENT', 'MODE_TOGGLE'
    entity_type = Column(String(50), nullable=False)        # 'transaction', 'organization', 'document'
    entity_id = Column(String(100), nullable=True)
    performed_by = Column(String(100), default="Bosh Buxgalter")
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<AuditLog {self.action} on {self.entity_type} at {self.created_at}>"
