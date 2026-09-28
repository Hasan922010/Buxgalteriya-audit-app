import uuid
from sqlalchemy import Column, String, ForeignKey, Numeric, Date, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import date

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    doc_number = Column(String(100), index=True)
    doc_date = Column(Date, nullable=False, index=True)
    doc_type = Column(String(50), nullable=False) # 'EHF', 'BANK', 'STOCK', 'MANUAL'
    
    # Dual-mode support: Accounts are optional in SIMPLE mode, required in BHMS
    debit_account = Column(String(10), ForeignKey("chart_of_accounts.code"), nullable=True, index=True)
    credit_account = Column(String(10), ForeignKey("chart_of_accounts.code"), nullable=True, index=True)
    
    counterparty_id = Column(UUID(as_uuid=True), ForeignKey("counterparties.id"), nullable=True, index=True)
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=True, index=True)
    
    # Financial metrics (always stored with precise decimals)
    quantity = Column(Numeric(15, 3), default=0)
    price = Column(Numeric(18, 2), default=0)
    total_amount = Column(Numeric(18, 2), nullable=False) # Jami summa (UZS)
    vat_rate = Column(Numeric(5, 2), default=0)           # 0%, 12%, or 15%
    vat_amount = Column(Numeric(18, 2), default=0)         # QQS summasi (UZS)
    
    description = Column(Text, nullable=True)
    raw_payload = Column(Text, nullable=True) # Store JSON of original row if ingested

    # Audit Trail & Storno (Immutability)
    is_reversed = Column(Boolean, default=False, nullable=False, index=True) # Storno qilinganmi?
    reversal_ref_id = Column(UUID(as_uuid=True), nullable=True)             # Asl yoki storno tranzaksiya ID
    reversal_reason = Column(String(255), nullable=True)                    # Storno sababi
    created_at = Column(Date, default=date.today)                           # Tizimga yozilgan sana

    # Relationships
    organization = relationship("Organization", back_populates="transactions")
    counterparty = relationship("Counterparty", back_populates="transactions")
    item = relationship("InventoryItem", back_populates="transactions")
    debit_rel = relationship("ChartOfAccount", foreign_keys=[debit_account])
    credit_rel = relationship("ChartOfAccount", foreign_keys=[credit_account])

    def __repr__(self):
        return f"<Transaction {self.doc_number} ({self.doc_date}): {self.total_amount} UZS>"
