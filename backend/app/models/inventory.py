import uuid
from sqlalchemy import Column, String, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    ikpu_code = Column(String(50), index=True) # MXIK kodi (17 ta raqam)
    package_code = Column(String(50))           # Qadoq kodi
    unit = Column(String(50), default="dona")   # O'lchov birligi
    min_stock_alert = Column(Numeric(15, 3), default=0)

    # Relationships
    organization = relationship("Organization", back_populates="inventory_items")
    transactions = relationship("Transaction", back_populates="item")

    def __repr__(self):
        return f"<InventoryItem {self.name} ({self.unit})>"
