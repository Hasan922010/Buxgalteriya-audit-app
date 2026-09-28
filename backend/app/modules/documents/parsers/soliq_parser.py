import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import List, Tuple, Dict, Any, Optional
import pandas as pd
from app.modules.documents.schemas import ParsedRecordItem
from app.services.parsers.normalize import parse_amount, parse_date

class SoliqParser:
    """
    Parser for Soliq.uz Turnover statements (Hisob-fakturalar reyestri)
    and Fiscal receipts / aggregates.
    """

    SOLIQ_KEYWORDS = [
        "soliq", "reyestr", "реестр", "hisob-faktura reyestri", "tasdiqlangan",
        "yetkazib berish qiymati", "soliq to'lovchi", "qqs summasi", "realizatsiya"
    ]

    @classmethod
    def detect_format(cls, df_preview: pd.DataFrame, headers: List[str]) -> Tuple[bool, float]:
        clean = " ".join([str(h).lower() for h in headers])
        if df_preview is not None and not df_preview.empty:
            preview_str = " ".join([str(v).lower() for v in df_preview.head(3).values.flatten() if pd.notna(v)])
            clean += " " + preview_str

        matches = sum(1 for kw in cls.SOLIQ_KEYWORDS if kw in clean)
        confidence = min(1.0, matches / 3.0)
        return confidence >= 0.5, round(confidence, 2)

    def parse_file(self, file_path: str) -> List[ParsedRecordItem]:
        df_raw = pd.read_excel(file_path, header=None)

        header_row_idx = 0
        for idx, row in df_raw.iloc[:15].iterrows():
            row_str = " ".join([str(v).lower() for v in row.values if pd.notna(v)])
            if any(k in row_str for k in ["hujjat", "faktura", "yetkazib", "tushum", "qiymat", "summa"]):
                header_row_idx = idx
                break

        df = pd.read_excel(file_path, skiprows=header_row_idx)
        df.columns = [str(c).strip() for c in df.columns]

        records: List[ParsedRecordItem] = []
        for _, row in df.iterrows():
            total = self._extract_decimal(row, ["jami", "summa", "yetkazib berish qiymati", "qiymati", "всего"])
            if total <= Decimal("0"):
                continue

            doc_number = self._extract_str(row, ["raqam", "hujjat raqami", "faktura", "номер"]) or "SOLIQ-REYESTR"
            doc_date = self._extract_date(row, ["sana", "hujjat sanasi", "tasdiqlangan sana", "дата"]) or date.today()
            buyer_name = self._extract_str(row, ["xaridor", "kontragent", "qabul qiluvchi", "покупатель"])
            buyer_inn = self._extract_str(row, ["stir", "inn", "xaridor stir"])

            vat_amount = self._extract_decimal(row, ["qqs", "qqs summasi", "nds"])

            rec = ParsedRecordItem(
                doc_number=doc_number,
                doc_date=doc_date,
                doc_type="EHF",
                buyer_name=buyer_name,
                buyer_inn=buyer_inn,
                item_name=self._extract_str(row, ["nomi", "tovar", "mahsulot", "xizmat"]) or "Mahsulotlar realizatsiyasi",
                total_amount=total,
                vat_amount=vat_amount,
                vat_rate=Decimal("12.0") if vat_amount > Decimal("0") else Decimal("0.0"),
                debit_account="4000",
                credit_account="9000",
                description=f"Soliq.uz reyestri bo'yicha tushum ({buyer_name or 'Aholi'})"
            )
            records.append(rec)

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
