import enum
from sqlalchemy import Column, String, Boolean, Enum
from app.core.database import Base

class AccountingMode(str, enum.Enum):
    SIMPLE = "SIMPLE"  # Oddiy / Soddalashtirilgan rejim
    BHMS = "BHMS"      # Professional BHMS / Buxgalteriya schotlari rejasi

class AccountType(str, enum.Enum):
    ASSET = "ASSET"          # Aktiv (1000, 2900, 5000, 5110)
    LIABILITY = "LIABILITY"  # Passiv (6000, 6800)
    EQUITY = "EQUITY"        # Kapital (8300, 8500)
    REVENUE = "REVENUE"      # Daromad (9000, 9300)
    EXPENSE = "EXPENSE"      # Xarajat (2000, 9400)

class ChartOfAccount(Base):
    __tablename__ = "chart_of_accounts"
    
    code = Column(String(10), primary_key=True) # e.g., '1000', '2900', '4000', '5110'
    name = Column(String(255), nullable=False)  # Materiallar, Tovarlar, etc.
    account_type = Column(Enum(AccountType), nullable=False)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<ChartOfAccount {self.code} - {self.name}>"
