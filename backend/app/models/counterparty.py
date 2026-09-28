import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

class Counterparty(Base):
    __tablename__ = "counterparties"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    inn = Column(String(9), index=True) # STIR (9 digits)
    mfo = Column(String(5))            # MFO (5 digits)
    bank_account = Column(String(20))   # 20-digit bank account
    phone = Column(String(50), nullable=True) # Phone number
    is_supplier = Column(Boolean, default=True) # Mol yetkazib beruvchi
    is_client = Column(Boolean, default=True)   # Xaridor

    # Relationships
    organization = relationship("Organization", back_populates="counterparties")
    transactions = relationship("Transaction", back_populates="counterparty")

    def __repr__(self):
        return f"<Counterparty {self.name} (STIR: {self.inn})>"
