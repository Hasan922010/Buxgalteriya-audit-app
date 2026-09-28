import re
from datetime import date
from decimal import Decimal
from typing import List, Tuple, Dict, Any, Optional
import pandas as pd
from app.services.parsers.base import BaseDocumentParser, ParsedDocumentRecord
from app.services.parsers.smart_excel_mapper import SmartExcelMapper
from app.services.parsers.normalize import UnparseableValue, parse_amount, require_amount, require_date

class MaterialParser(BaseDocumentParser):
    """
    Parser for Material Reports (Moddiy hisobot / Складской / Материальный отчет).
    Handles opening balances, inflows, outflows, and closing balances for warehouse goods and materials.
    """

    MATERIAL_KEYWORDS = [
        "материальный отчет", "моддий ҳисобот", "моддий хисобот", "ombor hisoboti",
        "бошланғич қолдиқ", "нач остаток", "начальный остаток", "boshlang'ich qoldiq",
        "охирги қолдиқ", "кон остаток", "конечный остаток", "oxirgi qoldiq",
        "кирим", "приход", "чиқим", "расход", "ўртача нарх", "средняя цена"
    ]

    @classmethod
    def detect_format(cls, df_preview: pd.DataFrame, headers: List[str]) -> Tuple[bool, float]:
        clean = " ".join([str(h).lower() for h in headers])
        if df_preview is not None and not df_preview.empty:
            preview_str = " ".join([str(v).lower() for v in df_preview.head(3).values.flatten() if pd.notna(v)])
            clean += " " + preview_str

        matches = sum(1 for kw in cls.MATERIAL_KEYWORDS if kw in clean)
        confidence = min(1.0, matches / 3.0)
        return confidence >= 0.5, round(confidence, 2)

    def parse_file(self, file_path: str) -> List[ParsedDocumentRecord]:
        self.row_errors: List[str] = []
        df, _, headers = SmartExcelMapper.find_header_row_and_df(file_path)
        mapping = SmartExcelMapper._heuristic_mapping(headers)
        
        records: List[ParsedDocumentRecord] = []
        today = date.today()

        for row_idx, row in df.iterrows():
            try:
                idx = row_idx
                if not mapping.item_name_col or pd.isna(row.get(mapping.item_name_col)):
                    continue

                item_name = str(row[mapping.item_name_col]).strip()
                if not item_name or item_name.lower().startswith("жами") or item_name.lower().startswith("итого"):
                    continue

                unit = "dona"
                if mapping.unit_col and pd.notna(row.get(mapping.unit_col)):
                    unit = str(row[mapping.unit_col]).strip()

                barcode = str(row.get(mapping.barcode_col, "")).strip() if mapping.barcode_col and pd.notna(row.get(mapping.barcode_col)) else None
                if barcode and barcode.endswith(".0"):
                    barcode = barcode[:-2]

                ikpu = str(row.get(mapping.ikpu_col, "")).strip() if mapping.ikpu_col and pd.notna(row.get(mapping.ikpu_col)) else None
                if ikpu and ikpu.endswith(".0"):
                    ikpu = ikpu[:-2]

                doc_num = str(idx + 1)
                if mapping.doc_num_col and pd.notna(row.get(mapping.doc_num_col)):
                    raw_num = str(row[mapping.doc_num_col]).strip()
                    if raw_num.endswith(".0"):
                        raw_num = raw_num[:-2]
                    if raw_num and raw_num != "nan":
                        doc_num = raw_num

                # Helper for decimal extraction
                def to_decimal(val) -> Decimal:
                    return require_amount(val, Decimal("0"))

                init_q = to_decimal(row.get(mapping.initial_qty_col)) if mapping.initial_qty_col else Decimal("0")
                init_s = to_decimal(row.get(mapping.initial_sum_col)) if mapping.initial_sum_col else Decimal("0")

                in_q = to_decimal(row.get(mapping.inflow_qty_col)) if mapping.inflow_qty_col else Decimal("0")
                in_s = to_decimal(row.get(mapping.inflow_sum_col)) if mapping.inflow_sum_col else Decimal("0")

                out_q = to_decimal(row.get(mapping.outflow_qty_col)) if mapping.outflow_qty_col else Decimal("0")
                out_s = to_decimal(row.get(mapping.outflow_sum_col)) if mapping.outflow_sum_col else Decimal("0")

                price = to_decimal(row.get(mapping.price_col)) if mapping.price_col else Decimal("0")
                if price == 0 and in_q > 0 and in_s > 0:
                    price = in_s / in_q

                # 1. Opening Balance record
                if init_q > 0 or init_s > 0:
                    calc_s = init_s if init_s > 0 else (init_q * price)
                    records.append(ParsedDocumentRecord(
                        doc_number=f"INIT-{doc_num}",
                        doc_date=today,
                        doc_type="INITIAL_STOCK",
                        item_name=item_name,
                        ikpu_code=ikpu,
                        package_code=barcode,
                        unit=unit,
                        quantity=init_q,
                        price=price,
                        total_amount=calc_s,
                        debit_account="2900",
                        credit_account="0000",
                        description=f"Boshlang'ich qoldiq: {item_name}",
                        raw_payload={str(k): str(v) for k, v in row.items() if pd.notna(v)}
                    ))

                # 2. Inflow record
                if in_q > 0 or in_s > 0:
                    calc_ins = in_s if in_s > 0 else (in_q * price)
                    records.append(ParsedDocumentRecord(
                        doc_number=f"KIRIM-{doc_num}",
                        doc_date=today,
                        doc_type="EHF",
                        item_name=item_name,
                        ikpu_code=ikpu,
                        package_code=barcode,
                        unit=unit,
                        quantity=in_q,
                        price=price,
                        total_amount=calc_ins,
                        debit_account="2900",
                        credit_account="6000",
                        description=f"Moddiy hisobot kirim: {item_name}",
                        raw_payload={str(k): str(v) for k, v in row.items() if pd.notna(v)}
                    ))

                # 3. Outflow record
                if out_q > 0 or out_s > 0:
                    calc_outs = out_s if out_s > 0 else (out_q * price)
                    records.append(ParsedDocumentRecord(
                        doc_number=f"CHIQIM-{doc_num}",
                        doc_date=today,
                        doc_type="STOCK",
                        item_name=item_name,
                        ikpu_code=ikpu,
                        package_code=barcode,
                        unit=unit,
                        quantity=out_q,
                        price=price,
                        total_amount=calc_outs,
                        debit_account="9100",
                        credit_account="2900",
                        description=f"Moddiy hisobot chiqim: {item_name}",
                        raw_payload={str(k): str(v) for k, v in row.items() if pd.notna(v)}
                    ))
            except UnparseableValue as cell_error:
                self.row_errors.append(f"Ma'lumot qatori {row_idx + 1}: {cell_error}")
                continue

        return records
