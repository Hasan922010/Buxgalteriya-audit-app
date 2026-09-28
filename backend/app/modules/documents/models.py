import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class DocumentIngestionLog(Base):
    __tablename__ = "document_ingestion_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    document_type = Column(String(50), nullable=False) # 'DIDOX', 'SOLIQ', 'BANK', 'OCR'
    rows_parsed = Column(Integer, default=0)
    rows_committed = Column(Integer, default=0)
    status = Column(String(50), default="COMPLETED")
    metadata_info = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
