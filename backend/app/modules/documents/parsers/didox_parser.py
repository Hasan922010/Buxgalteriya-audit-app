import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import List, Tuple, Dict, Any, Optional
import pandas as pd
from app.modules.documents.schemas import ParsedRecordItem
from app.services.parsers.normalize import parse_amount, parse_date

class DidoxParser:
    """
    Parser for Didox.uz electronic invoices (EHF) in Excel / XLSX format.
    Extracts: Invoice ID, Date, Contract Number, Supplier INN, Buyer INN,
    IKPU, Item Name, Units, Quantity, Price, VAT amount, and Total sum.
    """

    DIDOX_KEYWORDS = [
        "hujjat", "faktura", "ehf", "ikpu", "mxik", "yetkazib beruvchi",
        "xaridor", "qqs", "nds", "stir", "inn", "tovarlar", "счет-фактура"
    ]

    @classmethod
    def detect_format(cls, df_preview: pd.DataFrame, headers: List[str]) -> Tuple[bool, float]:
        clean_headers = [str(h).lower().strip() for h in headers]
        combined_text = " ".join(clean_headers)
        
        matches = sum(1 for kw in cls.DIDOX_KEYWORDS if kw in combined_text)
        confidence = min(1.0, matches / 4.0)
        is_match = (confidence >= 0.5) or any("ikpu" in h or "mxik" in h for h in clean_headers)
        return is_match, round(confidence, 2)

    def parse_file(self, file_path: str) -> List[ParsedRecordItem]:
        # Step 1: Detect header row
        df_raw = pd.read_excel(file_path, header=None)
        
        header_row_idx = 0
        metadata = {}
        for idx, row in df_raw.iloc[:15].iterrows():
            row_str = " ".join([str(v).lower() for v in row.values if pd.notna(v)])
            # Try to grab contract or header info from top rows
            if "shartnoma" in row_str or "договор" in row_str:
                m = re.search(r"(?:shartnoma|договор)\s*(?:№|raqam|номер)?\s*([A-Za-z0-9\-_/]+)", row_str, re.IGNORECASE)
                if m:
                    metadata["contract_number"] = m.group(1)
            if any(k in row_str for k in ["ikpu", "mxik", "tovar", "mahsulot", "narxi", "jami", "наименование"]):
                header_row_idx = idx
                break

        df = pd.read_excel(file_path, skiprows=header_row_idx)
        df.columns = [str(c).strip() for c in df.columns]

        col_map = self._map_columns(list(df.columns))
        records: List[ParsedRecordItem] = []

        for _, row in df.iterrows():
            item_name = self._get_str(row, col_map.get("item_name"))
            if not item_name or any(k in item_name.lower() for k in ["jami", "итого", "всего", "rahbar", "руководитель", "buxgalter", "бухгалтер", "imzo"]):
                continue

            doc_number = self._get_str(row, col_map.get("doc_number")) or "EHF"
            doc_date = self._get_date(row, col_map.get("doc_date"))

            qty = self._get_decimal(row, col_map.get("quantity"), default="1.0")
            price = self._get_decimal(row, col_map.get("price"))
            vat_rate = self._get_decimal(row, col_map.get("vat_rate"), default="12.0")
            vat_amount = self._get_decimal(row, col_map.get("vat_amount"))
            total_amt = self._get_decimal(row, col_map.get("total_amount"))

            if total_amt == Decimal("0") and qty > Decimal("0") and price > Decimal("0"):
                total_amt = qty * price + vat_amount

            rec = ParsedRecordItem(
                doc_number=doc_number,
                doc_date=doc_date or date.today(),
                doc_type="EHF",
                supplier_name=self._get_str(row, col_map.get("supplier_name")),
                supplier_inn=self._get_clean_inn(row, col_map.get("supplier_inn")),
                buyer_name=self._get_str(row, col_map.get("buyer_name")),
                buyer_inn=self._get_clean_inn(row, col_map.get("buyer_inn")),
                contract_number=self._get_str(row, col_map.get("contract_number")) or metadata.get("contract_number"),
                item_name=item_name,
                ikpu_code=self._get_clean_ikpu(row, col_map.get("ikpu_code")),
                unit=self._get_str(row, col_map.get("unit")) or "dona",
                quantity=qty,
                price=price,
                vat_rate=vat_rate,
                vat_amount=vat_amount,
                total_amount=total_amt,
                debit_account="2900",
                credit_account="6000",
                description=f"Didox EHF: {item_name}"
            )
            records.append(rec)

        return records

    def _map_columns(self, columns: List[str]) -> Dict[str, str]:
        mapping = {}
        for col in columns:
            c_low = col.lower().strip()
            if any(k in c_low for k in ["hujjat raqam", "faktura raqam", "номер счет", "номер с/ф", "№ с/ф"]) and "doc_number" not in mapping:
                mapping["doc_number"] = col
            elif any(k in c_low for k in ["hujjat sana", "faktura sana", "sana", "дата"]) and "doc_date" not in mapping:
                mapping["doc_date"] = col
            elif any(k in c_low for k in ["yetkazib beruvchi", "поставщик"]):
                if any(k in c_low for k in ["inn", "stir"]) and "supplier_inn" not in mapping:
                    mapping["supplier_inn"] = col
                elif "supplier_name" not in mapping:
                    mapping["supplier_name"] = col
            elif any(k in c_low for k in ["xaridor", "покупатель"]):
                if any(k in c_low for k in ["inn", "stir"]) and "buyer_inn" not in mapping:
                    mapping["buyer_inn"] = col
                elif "buyer_name" not in mapping:
                    mapping["buyer_name"] = col
            elif any(k in c_low for k in ["shartnoma", "договор"]) and "contract_number" not in mapping:
                mapping["contract_number"] = col
            elif any(k in c_low for k in ["ikpu", "mxik", "икпу", "мхик"]) and "ikpu_code" not in mapping:
                mapping["ikpu_code"] = col
            elif any(k in c_low for k in ["tovar", "mahsulot", "xizmat", "tovar nomi", "наименование"]) and "item_name" not in mapping:
                mapping["item_name"] = col
            elif any(k in c_low for k in ["birlik", "o'lchov", "ед. изм", "ед."]) and "unit" not in mapping:
                mapping["unit"] = col
            elif any(k in c_low for k in ["miqdor", "soni", "кол-во", "количество"]) and "quantity" not in mapping:
                mapping["quantity"] = col
            elif any(k in c_low for k in ["narx", "qiymat", "цена"]) and "price" not in mapping:
                mapping["price"] = col
            elif any(k in c_low for k in ["stavka", "foiz", "ставка"]) and any(k in c_low for k in ["qqs", "nds"]) and "vat_rate" not in mapping:
                mapping["vat_rate"] = col
            elif any(k in c_low for k in ["summa qqs", "qqs summasi", "сумма ндс", "ндс"]) and "vat_amount" not in mapping:
                mapping["vat_amount"] = col
            elif any(k in c_low for k in ["jami", "summa", "всего", "итого"]) and "total_amount" not in mapping:
                mapping["total_amount"] = col

        # Fallbacks
        if "item_name" not in mapping and len(columns) > 1:
            mapping["item_name"] = columns[1]
        if "total_amount" not in mapping and len(columns) > 2:
            mapping["total_amount"] = columns[-1]
        return mapping

    def _get_str(self, row: pd.Series, col: Optional[str]) -> Optional[str]:
        if not col or col not in row:
            return None
        val = row[col]
        if pd.isna(val):
            return None
        s = str(val).strip()
        return s if s else None

    def _get_clean_inn(self, row: pd.Series, col: Optional[str]) -> Optional[str]:
        s = self._get_str(row, col)
        if not s:
            return None
        if s.endswith(".0"):
            s = s[:-2]
        clean = re.sub(r"\D", "", s)
        return clean if len(clean) == 9 else s

    def _get_clean_ikpu(self, row: pd.Series, col: Optional[str]) -> Optional[str]:
        s = self._get_str(row, col)
        if not s:
            return None
        if s.endswith(".0"):
            s = s[:-2]
        clean = re.sub(r"\D", "", s)
        if len(clean) == 16:
            clean = "0" + clean
        return clean if clean else s

    def _get_date(self, row: pd.Series, col: Optional[str]) -> Optional[date]:
        if not col or col not in row:
            return None
        return parse_date(row[col])

    def _get_decimal(self, row: pd.Series, col: Optional[str], default: str = "0") -> Decimal:
        if not col or col not in row:
            return Decimal(default)
        parsed = parse_amount(row[col])
        return parsed if parsed is not None else Decimal(default)
