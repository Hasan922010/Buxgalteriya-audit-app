from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
import pandas as pd

@dataclass
class ParsedDocumentRecord:
    doc_number: Optional[str] = None
    doc_date: Optional[date] = None
    doc_type: str = "MANUAL" # 'EHF', 'BANK', 'STOCK', 'MANUAL'
    counterparty_name: Optional[str] = None
    counterparty_inn: Optional[str] = None
    counterparty_mfo: Optional[str] = None
    counterparty_account: Optional[str] = None
    item_name: Optional[str] = None
    ikpu_code: Optional[str] = None
    package_code: Optional[str] = None
    unit: str = "dona"
    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    total_amount: Decimal = Decimal("0")
    vat_rate: Decimal = Decimal("0")
    vat_amount: Decimal = Decimal("0")
    debit_account: Optional[str] = None
    credit_account: Optional[str] = None
    description: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None

class BaseDocumentParser(ABC):
    @classmethod
    @abstractmethod
    def detect_format(cls, df_preview: pd.DataFrame, headers: List[str]) -> Tuple[bool, float]:
        """Returns (is_match, confidence_score)."""
        pass

    @abstractmethod
    def parse_file(self, file_path: str) -> List[ParsedDocumentRecord]:
        """Extracts standardized records from document file."""
        pass
