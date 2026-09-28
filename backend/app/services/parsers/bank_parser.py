import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import List, Tuple, Dict, Any, Optional
import pandas as pd
from app.services.parsers.base import BaseDocumentParser, ParsedDocumentRecord
from app.services.parsers.normalize import parse_amount, parse_date

class BankParser(BaseDocumentParser):
    """
    Parser for Uzbekistan Bank-Client Statements (Agrobank, Kapitalbank, Hamkorbank, Ipak Yo'li, etc.).
    Supports Excel (.xlsx, .xls) and 1C Client-Bank TXT format.
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
        confidence = min(1.0, matches / 4.0)
        is_match = (confidence >= 0.5) or ("debet" in combined and "kredit" in combined)
        return is_match, round(confidence, 2)

    def parse_file(self, file_path: str) -> List[ParsedDocumentRecord]:
        if file_path.endswith(".txt"):
            return self._parse_1c_txt(file_path)
        return self._parse_excel(file_path)

    def _parse_excel(self, file_path: str) -> List[ParsedDocumentRecord]:
        df_raw = pd.read_excel(file_path, header=None)
        
        header_row_idx = 0
        for idx, row in df_raw.iloc[:15].iterrows():
            row_str = " ".join([str(v).lower() for v in row.values if pd.notna(v)])
            if any(k in row_str for k in ["sana", "raqam", "debet", "kredit", "kontragent", "maqsad"]):
                header_row_idx = idx
                break

        df = pd.read_excel(file_path, skiprows=header_row_idx)
        df.columns = [str(c).strip() for c in df.columns]

        records: List[ParsedDocumentRecord] = []
        col_map = self._map_bank_columns(list(df.columns))

        for _, row in df.iterrows():
            purpose = self._get_str(row, col_map.get("purpose")) or "Bank operatsiyasi"
            if "jami" in purpose.lower() or "итого" in purpose.lower() or "qoldiq" in purpose.lower():
                continue

            doc_number = self._get_str(row, col_map.get("doc_number")) or "BANK"
            doc_date = self._get_date(row, col_map.get("doc_date"))

            inflow = self._get_decimal(row, col_map.get("debit_inflow"))
            outflow = self._get_decimal(row, col_map.get("credit_outflow"))

            if inflow == Decimal("0") and outflow == Decimal("0"):
                amt = self._get_decimal(row, col_map.get("amount"))
                if amt > 0:
                    inflow = amt
                else:
                    outflow = abs(amt)

            is_inflow = inflow > Decimal("0")
            total_amt = inflow if is_inflow else outflow

            if total_amt <= Decimal("0"):
                continue

            cp_name = self._get_str(row, col_map.get("counterparty")) or "Noma'lum kontragent"
            cp_inn = self._extract_inn(self._get_str(row, col_map.get("inn")) or purpose or cp_name)
            cp_mfo = self._extract_mfo(self._get_str(row, col_map.get("mfo")))
            cp_acc = self._get_str(row, col_map.get("account"))

            # Uzbekistan Chart of Accounts:
            # Kirim (Inflow to bank): Dt 5110 (Bank), Kt 4000 (Xaridor) or 6000 (Qaytarish)
            # Chiqim (Outflow from bank): Dt 6000 (Ta'minotchi) or 6800 (Soliq), Kt 5110 (Bank)
            if is_inflow:
                debit_acc = "5110"
                credit_acc = "4000"
            else:
                if any(k in purpose.lower() for k in ["soliq", "byudjet", "qqs", "ndfl", "daromad"]):
                    debit_acc = "6800"
                else:
                    debit_acc = "6000"
                credit_acc = "5110"

            rec = ParsedDocumentRecord(
                doc_number=doc_number,
                doc_date=doc_date,
                doc_type="BANK",
                counterparty_name=cp_name,
                counterparty_inn=cp_inn,
                counterparty_mfo=cp_mfo,
                counterparty_account=cp_acc,
                quantity=Decimal("1"),
                price=total_amt,
                total_amount=total_amt,
                vat_rate=Decimal("0"),
                vat_amount=Decimal("0"),
                debit_account=debit_acc,
                credit_account=credit_acc,
                description=purpose,
                raw_payload={k: str(v) for k, v in row.items() if pd.notna(v)}
            )
            records.append(rec)

        return records

    def _parse_1c_txt(self, file_path: str) -> List[ParsedDocumentRecord]:
        """Parses standard 1C ClientBankExchange format (.txt)."""
        records: List[ParsedDocumentRecord] = []
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        curr_doc: Dict[str, str] = {}
        in_doc = False

        for line in lines:
            line_s = line.strip()
            if line_s.startswith("СекцияДокумент=") or line_s.startswith("SektsiyaHujjat="):
                in_doc = True
                curr_doc = {}
            elif (line_s == "КонецДокумента" or line_s == "HujjatOxiri") and in_doc:
                # Process document
                doc_num = curr_doc.get("Номер", "1")
                doc_date_str = curr_doc.get("Дата", "")
                try:
                    doc_date = datetime.strptime(doc_date_str, "%d.%m.%Y").date()
                except Exception:
                    doc_date = date.today()

                summa_str = curr_doc.get("Сумма", "0")
                try:
                    total_amt = Decimal(summa_str)
                except Exception:
                    total_amt = Decimal("0")

                payer_inn = curr_doc.get("ПлательщикИНН", "")
                payer_name = curr_doc.get("Плательщик1", curr_doc.get("Плательщик", ""))
                receiver_inn = curr_doc.get("ПолучательИНН", "")
                receiver_name = curr_doc.get("Получатель1", curr_doc.get("Получатель", ""))
                purpose = curr_doc.get("НазначениеПлатежа", "")

                rec = ParsedDocumentRecord(
                    doc_number=doc_num,
                    doc_date=doc_date,
                    doc_type="BANK",
                    counterparty_name=receiver_name or payer_name,
                    counterparty_inn=receiver_inn or payer_inn,
                    quantity=Decimal("1"),
                    price=total_amt,
                    total_amount=total_amt,
                    debit_account="6000",
                    credit_account="5110",
                    description=purpose,
                    raw_payload=curr_doc
                )
                records.append(rec)
                in_doc = False
            elif in_doc and "=" in line_s:
                parts = line_s.split("=", 1)
                curr_doc[parts[0].strip()] = parts[1].strip()

        return records

    def _map_bank_columns(self, columns: List[str]) -> Dict[str, str]:
        mapping = {}
        for col in columns:
            c = col.lower()
            if any(k in c for k in ["hujjat raqami", "to'lov topshirnoma", "номер пп", "doc_no", "nomer"]):
                mapping["doc_number"] = col
            elif "doc_number" not in mapping and any(k in c for k in ["raqam", "номер"]):
                mapping["doc_number"] = col
            if any(k in c for k in ["sana", "date", "дата"]):
                mapping.setdefault("doc_date", col)
            if any(k in c for k in ["kirim", "приход", "debet", "дебет", "inflow"]):
                mapping.setdefault("debit_inflow", col)
            if any(k in c for k in ["chiqim", "расход", "kredit", "кредит", "outflow"]):
                mapping.setdefault("credit_outflow", col)
            if any(k in c for k in ["summa", "сумма", "amount"]):
                mapping.setdefault("amount", col)
            if any(k in c for k in ["kontragent", "hamkor", "korxona", "получатель", "плательщик"]):
                mapping.setdefault("counterparty", col)
            if any(k in c for k in ["inn", "stir", "инн"]):
                mapping.setdefault("inn", col)
            if any(k in c for k in ["mfo", "мфо"]):
                mapping.setdefault("mfo", col)
            if any(k in c for k in ["hisob", "счет", "account"]):
                mapping.setdefault("account", col)
            if any(k in c for k in ["maqsad", "mazmun", "назначение", "детали"]):
                mapping.setdefault("purpose", col)
        return mapping


    @staticmethod
    def _get_str(row: pd.Series, col: Optional[str]) -> Optional[str]:
        if not col or col not in row or pd.isna(row[col]):
            return None
        val = str(row[col]).strip()
        return val if val else None

    @staticmethod
    def _get_decimal(row: pd.Series, col: Optional[str]) -> Decimal:
        if not col or col not in row:
            return Decimal("0")
        return parse_amount(row[col]) or Decimal("0")

    @staticmethod
    def _get_date(row: pd.Series, col: Optional[str]) -> date:
        if not col or col not in row:
            return date.today()
        return parse_date(row[col]) or date.today()

    @staticmethod
    def _extract_inn(text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        matches = re.findall(r"\b\d{9}\b", str(text))
        return matches[0] if matches else None

    @staticmethod
    def _extract_mfo(text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        matches = re.findall(r"\b\d{5}\b", str(text))
        return matches[0] if matches else None
