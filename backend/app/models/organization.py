import uuid
from datetime import date
from sqlalchemy import Column, String, Boolean, Date, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.account import AccountingMode

class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    inn = Column(String(9), unique=True, nullable=False, index=True) # STIR (9 digits)
    mode = Column(Enum(AccountingMode), default=AccountingMode.SIMPLE, nullable=False)
    vat_payer = Column(Boolean, default=False) # QQS to'lovchisi (12%)
    created_at = Column(Date, default=date.today)
    locked_until_date = Column(Date, nullable=True) # Davrni yopish/qulflash sanasi (Period Lock)

    # Relationships
    counterparties = relationship("Counterparty", back_populates="organization", cascade="all, delete-orphan")
    inventory_items = relationship("InventoryItem", back_populates="organization", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="organization", cascade="all, delete-orphan")

    @property
    def accounting_mode(self):
        return self.mode

    @accounting_mode.setter
    def accounting_mode(self, value):
        self.mode = value

    def __repr__(self):
        return f"<Organization {self.name} (STIR: {self.inn})>"
