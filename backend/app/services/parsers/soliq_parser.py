import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import List, Tuple, Dict, Any, Optional
import pandas as pd
from app.services.parsers.base import BaseDocumentParser, ParsedDocumentRecord
from app.services.parsers.normalize import parse_amount, parse_date

class SoliqParser(BaseDocumentParser):
    """
    Parser for Soliq.uz Turnover registries (Hisob-fakturalar reyestri)
    and Soliq / Virtual Kassa Product Realization registries (Mahsulotlar realizatsiyasi).
    """

    SOLIQ_KEYWORDS = [
        "soliq", "reyestr", "реестр", "hisob-faktura reyestri", "tasdiqlangan",
        "yetkazib berish qiymati", "soliq to'lovchi", "qqs summasi",
        "маҳсулот (хизмат) реализацияси", "махсулот реализацияси", "мхик", "штрих (gtin)",
        "сотилган маҳсулот", "қайтарилган маҳсулот", "ўртача маҳсулот"
    ]

    @classmethod
    def detect_format(cls, df_preview: pd.DataFrame, headers: List[str]) -> Tuple[bool, float]:
        from app.services.parsers.smart_excel_mapper import SmartExcelMapper
        clean = " ".join([str(h).lower() for h in headers])
        
        # Check preview cells if title is in row 0
        if df_preview is not None and not df_preview.empty:
            preview_str = " ".join([str(v).lower() for v in df_preview.head(3).values.flatten() if pd.notna(v)])
            clean += " " + preview_str

        matches = sum(1 for kw in cls.SOLIQ_KEYWORDS if kw in clean)
        confidence = min(1.0, matches / 3.0)
        return confidence >= 0.5, round(confidence, 2)

    def parse_file(self, file_path: str) -> List[ParsedDocumentRecord]:
        from app.services.parsers.smart_excel_mapper import SmartExcelMapper
        df, _, headers = SmartExcelMapper.find_header_row_and_df(file_path)
        mapping = SmartExcelMapper._heuristic_mapping(headers)
        
        records: List[ParsedDocumentRecord] = []
        for idx, row in df.iterrows():
            # 1. Total sale amount
            total = (parse_amount(row.get(mapping.total_col)) if mapping.total_col else None) or Decimal("0")

            if total <= 0:
                continue

            # 2. Date
            tx_date = (parse_date(row.get(mapping.date_col)) if mapping.date_col else None) or date.today()

            # 3. Doc number
            doc_num = str(idx + 1)
            if mapping.doc_num_col and pd.notna(row.get(mapping.doc_num_col)):
                raw_num = str(row[mapping.doc_num_col]).strip()
                if raw_num.endswith(".0"):
                    raw_num = raw_num[:-2]
                if raw_num and raw_num != "nan":
                    doc_num = raw_num

            # 4. Item and identifiers
            item_name = str(row.get(mapping.item_name_col, "")).strip() if mapping.item_name_col and pd.notna(row.get(mapping.item_name_col)) else None
            ikpu_code = str(row.get(mapping.ikpu_col, "")).strip() if mapping.ikpu_col and pd.notna(row.get(mapping.ikpu_col)) else None
            if ikpu_code and ikpu_code.endswith(".0"):
                ikpu_code = ikpu_code[:-2]
            
            barcode = str(row.get(mapping.barcode_col, "")).strip() if mapping.barcode_col and pd.notna(row.get(mapping.barcode_col)) else None
            if barcode and barcode.endswith(".0"):
                barcode = barcode[:-2]

            # 5. Quantity & Price
            qty = (parse_amount(row.get(mapping.qty_col)) if mapping.qty_col else None) or Decimal("1")

            price = total / qty if qty > 0 else total
            parsed_price = parse_amount(row.get(mapping.price_col)) if mapping.price_col else None
            if parsed_price is not None:
                price = parsed_price

            # Record sales transaction (Kassa / Bank -> Sotishdan daromad)
            records.append(ParsedDocumentRecord(
                doc_number=f"SLQ-{doc_num}",
                doc_date=tx_date,
                doc_type="SOLIQ_SALES",
                counterparty_name="Aholi (Chakana xaridorlar)",
                item_name=item_name,
                ikpu_code=ikpu_code,
                package_code=barcode,
                quantity=qty,
                price=price,
                total_amount=total,
                debit_account="5000", # Kassa / Tushum
                credit_account="9000", # Asosiy faoliyat daromadi
                description=f"Soliq.uz kassa realizatsiyasi: {item_name or 'Mahsulot'}",
                raw_payload={str(k): str(v) for k, v in row.items() if pd.notna(v)}
            ))

            # Check if there are returns
            ret_sum = (parse_amount(row.get(mapping.return_sum_col)) if mapping.return_sum_col else None) or Decimal("0")

            if ret_sum > 0:
                ret_qty = (parse_amount(row.get(mapping.return_qty_col)) if mapping.return_qty_col else None) or Decimal("1")
                records.append(ParsedDocumentRecord(
                    doc_number=f"RET-{doc_num}",
                    doc_date=tx_date,
                    doc_type="RETURN",
                    counterparty_name="Aholi (Qaytarish)",
                    item_name=item_name,
                    ikpu_code=ikpu_code,
                    package_code=barcode,
                    quantity=ret_qty,
                    price=ret_sum / ret_qty if ret_qty > 0 else ret_sum,
                    total_amount=ret_sum,
                    debit_account="9000",
                    credit_account="5000",
                    description=f"Mahsulot qaytarilishi: {item_name or 'Mahsulot'}",
                    raw_payload={str(k): str(v) for k, v in row.items() if pd.notna(v)}
                ))

        return records
