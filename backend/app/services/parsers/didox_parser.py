import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import List, Tuple, Dict, Any, Optional
import pandas as pd
from app.services.parsers.base import BaseDocumentParser, ParsedDocumentRecord
from app.services.parsers.normalize import parse_amount, parse_date

class DidoxParser(BaseDocumentParser):
    """
    Parser for Didox.uz electronic invoices (EHF) in Excel / XLSX format.
    Handles Uzbek and Russian column naming variations.
    """

    DIDOX_KEYWORDS = [
        "hujjat", "faktura", "ehf", "ikpu", "mxik", "yetkazib beruvchi",
        "xaridor", "qqs", "nds", "stir", "inn", "tovarlar"
    ]

    @classmethod
    def detect_format(cls, df_preview: pd.DataFrame, headers: List[str]) -> Tuple[bool, float]:
        clean_headers = [str(h).lower().strip() for h in headers]
        combined_text = " ".join(clean_headers)
        
        matches = sum(1 for kw in cls.DIDOX_KEYWORDS if kw in combined_text)
        confidence = min(1.0, matches / 5.0)
        is_match = (confidence >= 0.5) or any("ikpu" in h or "mxik" in h for h in clean_headers)
        return is_match, round(confidence, 2)

    def parse_file(self, file_path: str) -> List[ParsedDocumentRecord]:
        # Read excel file - find header row
        df_raw = pd.read_excel(file_path, header=None)
        
        header_row_idx = 0
        for idx, row in df_raw.iloc[:15].iterrows():
            row_str = " ".join([str(v).lower() for v in row.values if pd.notna(v)])
            if any(k in row_str for k in ["ikpu", "mxik", "tovar", "mahsulot", "narxi", "jami"]):
                header_row_idx = idx
                break

        df = pd.read_excel(file_path, skiprows=header_row_idx)
        df.columns = [str(c).strip() for c in df.columns]

        records: List[ParsedDocumentRecord] = []

        col_map = self._map_columns(list(df.columns))

        for _, row in df.iterrows():
            # Skip empty or total rows
            item_name = self._get_str(row, col_map.get("item_name"))
            if not item_name or "jami" in item_name.lower() or "итого" in item_name.lower():
                continue

            doc_number = self._get_str(row, col_map.get("doc_number")) or "EHF"
            doc_date = self._get_date(row, col_map.get("doc_date"))

            qty = self._get_decimal(row, col_map.get("quantity"))
            price = self._get_decimal(row, col_map.get("price"))
            total_amt = self._get_decimal(row, col_map.get("total_amount"))
            if total_amt == Decimal("0") and qty > Decimal("0") and price > Decimal("0"):
                total_amt = qty * price

            vat_rate = self._get_decimal(row, col_map.get("vat_rate"))
            vat_amount = self._get_decimal(row, col_map.get("vat_amount"))
            if vat_rate > Decimal("0") and vat_amount == Decimal("0"):
                # 12% VAT in UZ
                vat_amount = (total_amt * vat_rate / (Decimal("100") + vat_rate)).quantize(Decimal("0.01"))

            cp_name = self._get_str(row, col_map.get("counterparty_name"))
            cp_inn = self._extract_inn(self._get_str(row, col_map.get("counterparty_inn")) or cp_name)

            ikpu = self._get_str(row, col_map.get("ikpu"))
            if ikpu and ikpu.isdigit() and len(ikpu) < 17:
                ikpu = ikpu.zfill(17)
            unit = self._get_str(row, col_map.get("unit")) or "dona"


            rec = ParsedDocumentRecord(
                doc_number=doc_number,
                doc_date=doc_date,
                doc_type="EHF",
                counterparty_name=cp_name,
                counterparty_inn=cp_inn,
                item_name=item_name,
                ikpu_code=ikpu,
                unit=unit,
                quantity=qty,
                price=price,
                total_amount=total_amt,
                vat_rate=vat_rate,
                vat_amount=vat_amount,
                debit_account="2900",  # Default incoming goods/merchandise
                credit_account="6000", # Default supplier payable
                description=f"EHF: {item_name} ({qty} {unit})",
                raw_payload={k: str(v) for k, v in row.items() if pd.notna(v)}
            )
            records.append(rec)

        return records

    def _map_columns(self, columns: List[str]) -> Dict[str, str]:
        mapping = {}
        for col in columns:
            c = col.lower().strip()
            # Doc number
            if any(k in c for k in ["hujjat raqami", "номер документа", "doc_no", "faktura raqami"]):
                mapping["doc_number"] = col
            elif "doc_number" not in mapping and any(k in c for k in ["raqam", "номер"]):
                mapping["doc_number"] = col

            # Doc date
            if any(k in c for k in ["sana", "date", "дата"]):
                mapping.setdefault("doc_date", col)

            # Item description (avoid matching counterparty nomi)
            if any(k in c for k in ["tovarlar (xizmatlar) nomi", "tovar nomi", "mahsulot", "наименование товаров"]):
                mapping["item_name"] = col
            elif "item_name" not in mapping and ("tovar" in c or "mahsulot" in c or "xizmat" in c):
                mapping["item_name"] = col

            # Counterparty
            if any(k in c for k in ["yetkazib beruvchi nomi", "yetkazib beruvchi", "поставщик"]):
                mapping.setdefault("counterparty_name", col)
            elif "counterparty_name" not in mapping and any(k in c for k in ["xaridor", "kontragent", "покупатель"]):
                mapping.setdefault("counterparty_name", col)

            # INN / STIR
            if any(k in c for k in ["yetkazib beruvchi stir", "yetkazib beruvchi inn", "stir", "inn", "инн"]):
                mapping.setdefault("counterparty_inn", col)

            # IKPU
            if any(k in c for k in ["ikpu", "mxik", "икпу", "мхик"]):
                mapping.setdefault("ikpu", col)

            # Unit
            if any(k in c for k in ["birlik", "o'lchov", "ед. изм", "unit"]):
                mapping.setdefault("unit", col)

            # Quantity & Price
            if any(k in c for k in ["miqdori", "miqdor", "soni", "кол-во", "количество", "qty"]):
                mapping.setdefault("quantity", col)
            if any(k in c for k in ["narxi", "narx", "цена", "price"]):
                mapping.setdefault("price", col)

            # Total amount with VAT (prioritize Jami qiymat)
            if any(k in c for k in ["jami qiymat", "jami summa", "всего с ндс", "total amount", "jami"]):
                mapping["total_amount"] = col
            elif "total_amount" not in mapping and any(k in c for k in ["qiymat", "summa"]):
                mapping["total_amount"] = col

            # VAT Rate & Amount
            if any(k in c for k in ["qqs stavkasi", "ставка qqs", "ндс %", "stavka"]):
                mapping.setdefault("vat_rate", col)
            if any(k in c for k in ["qqs summasi", "сумма ндс", "vat amount"]):
                mapping.setdefault("vat_amount", col)

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
