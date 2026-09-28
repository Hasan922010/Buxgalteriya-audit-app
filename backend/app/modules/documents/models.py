import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON, Index, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class DocumentIngestionLog(Base):
    __tablename__ = "document_ingestion_logs"
    __table_args__ = (
        # Closes the check-then-insert race of concurrent duplicate imports
        Index(
            "uq_ingestion_org_file_completed", "organization_id", "file_sha256", unique=True,
            postgresql_where=text("status = 'COMPLETED'"), sqlite_where=text("status = 'COMPLETED'"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    document_type = Column(String(50), nullable=False) # 'DIDOX', 'SOLIQ', 'BANK', 'OCR'
    rows_parsed = Column(Integer, default=0)
    rows_committed = Column(Integer, default=0)
    status = Column(String(50), default="COMPLETED")
    # SHA256 of the imported file (or a document fingerprint) for duplicate detection
    file_sha256 = Column(String(64), nullable=True, index=True)
    metadata_info = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
