import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import List, Tuple, Dict, Any, Optional
import pandas as pd
from app.modules.documents.schemas import ParsedRecordItem
from app.services.parsers.normalize import parse_amount, parse_date

class BankParser:
    """
    Parser for Uzbekistan Bank-Client Statements (Agrobank, Kapitalbank, Hamkorbank, etc.).
    Supports .xlsx and .csv files.
    Maps transactions to account 5110 (Hisob-kitob schoti / Bank).
    """

    BANK_KEYWORDS = [
        "ko'chirma", "выписка", "to'lov topshirnoma", "платежное поручение",
        "debet", "kredit", "дебет", "кредит", "mfo", "мфо", "to'lov maqsadi", "назначение"
    ]

    @classmethod
    def detect_format(cls, df_preview: pd.DataFrame, headers: List[str]) -> Tuple[bool, float]:
        clean_headers = [str(h).lower().strip() for h in headers]
        combined = " ".join(clean_headers)

        matches = sum(1 for kw in cls.BANK_KEYWORDS if kw in combined)
        confidence = min(1.0, matches / 3.0)
        is_match = (confidence >= 0.5) or ("debet" in combined and "kredit" in combined)
        return is_match, round(confidence, 2)

    def parse_file(self, file_path: str) -> List[ParsedRecordItem]:
        if file_path.endswith(".csv"):
            df_raw = pd.read_csv(file_path, header=None)
        else:
            df_raw = pd.read_excel(file_path, header=None)

        header_row_idx = 0
        for idx, row in df_raw.iloc[:15].iterrows():
            row_str = " ".join([str(v).lower() for v in row.values if pd.notna(v)])
            if any(k in row_str for k in ["sana", "raqam", "debet", "kredit", "kontragent", "maqsad"]):
                header_row_idx = idx
                break

        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path, skiprows=header_row_idx)
        else:
            df = pd.read_excel(file_path, skiprows=header_row_idx)

        df.columns = [str(c).strip() for c in df.columns]

        records: List[ParsedRecordItem] = []
        for _, row in df.iterrows():
            purpose = self._extract_str(row, ["maqsad", "to'lov maqsadi", "назначение", "детали"]) or "Bank to'lovi"
            if any(k in purpose.lower() for k in ["jami", "итого", "qoldiq", "сальдо"]):
                continue

            doc_number = self._extract_str(row, ["raqam", "№", "номер", "hujjat raqami"]) or "BANK-PP"
            doc_date = self._extract_date(row, ["sana", "o'tkazilgan sana", "дата"]) or date.today()

            debit_amt = self._extract_decimal(row, ["debet", "kirim", "приход", "дебет"])
            credit_amt = self._extract_decimal(row, ["kredit", "chiqim", "расход", "кредит"])

            cp_name = self._extract_str(row, ["kontragent", "nomi", "korxona", "получатель", "плательщик"])
            cp_inn = self._extract_str(row, ["stir", "inn", "инн"])

            # Bank Inflow (Kirim): 5110 Debit / 4000 Kredit
            if debit_amt > Decimal("0"):
                records.append(ParsedRecordItem(
                    doc_number=doc_number,
                    doc_date=doc_date,
                    doc_type="BANK_PAYMENT",
                    supplier_name=cp_name,
                    supplier_inn=cp_inn,
                    item_name="Bank hisobiga to'lov kelib tushishi",
                    total_amount=debit_amt,
                    debit_account="5110",
                    credit_account="4000",
                    description=purpose
                ))
            # Bank Outflow (Chiqim): 6000 Debit / 5110 Kredit
            elif credit_amt > Decimal("0"):
                records.append(ParsedRecordItem(
                    doc_number=doc_number,
                    doc_date=doc_date,
                    doc_type="BANK_PAYMENT",
                    buyer_name=cp_name,
                    buyer_inn=cp_inn,
                    item_name="Bank hisobidan to'lov amalga oshirildi",
                    total_amount=credit_amt,
                    debit_account="6000",
                    credit_account="5110",
                    description=purpose
                ))

        return records

    def _extract_str(self, row: pd.Series, keywords: List[str]) -> Optional[str]:
        for col in row.index:
            c_low = str(col).lower()
            if any(k in c_low for k in keywords):
                val = row[col]
                if pd.notna(val) and str(val).strip():
                    return str(val).strip()
        return None

    def _extract_date(self, row: pd.Series, keywords: List[str]) -> Optional[date]:
        for col in row.index:
            c_low = str(col).lower()
            if any(k in c_low for k in keywords):
                parsed = parse_date(row[col])
                if parsed is not None:
                    return parsed
        return None

    def _extract_decimal(self, row: pd.Series, keywords: List[str]) -> Decimal:
        for col in row.index:
            c_low = str(col).lower()
            if any(k in c_low for k in keywords):
                parsed = parse_amount(row[col])
                if parsed is not None:
                    return parsed
        return Decimal("0")
