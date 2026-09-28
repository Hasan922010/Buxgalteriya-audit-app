import re
import io
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Tuple, Dict, Any
import pymupdf  # PyMuPDF
import pandas as pd

from app.modules.ocr.ocr_extractor import ExtractedDocument, ExtractedLineItem, OCRExtractor
from app.modules.ocr.image_enhancer import pdf_to_enhanced_images, cv2_to_png_bytes
from app.services.parsers.normalize import parse_ocr_amount

logger = logging.getLogger("pdf_table_extractor")

class PDFTableExtractor:
    """
    Intelligent PDF Document and Table Aggregator.
    Extracts tabular items, header metadata (INN, doc number, date, parties)
    from both digital and scanned PDFs, aggregating them into a structured ExtractedDocument.
    """

    @classmethod
    def clean_decimal(cls, val: Any) -> Decimal:
        return parse_ocr_amount(val) or Decimal("0")

    @classmethod
    def extract_metadata_from_text(cls, text: str) -> Dict[str, Any]:
        """Extracts INN, document number, date, and contract from raw text."""
        meta = {
            "doc_number": None,
            "doc_date": date.today(),
            "supplier_name": None,
            "supplier_inn": None,
            "buyer_name": None,
            "buyer_inn": None,
            "contract_number": None,
        }

        # 1. Document number (avoid matching INN)
        doc_num_match = re.search(r"(?:hisobvaraq[- ]faktura|faktura|hujjat|chek)\s*(?:№|no[.:]?|raqam[i:]?|#|номер|\?)?\s*[:#]?\s*([A-Za-z0-9\-_/]+)", text, re.IGNORECASE)
        if not doc_num_match:
            doc_num_match = re.search(r"(?:№|no[.:]\s*|raqam[i:]?\s*|#\s*|номер\s*|\?\s*)([A-Za-z0-9\-_/]+)", text, re.IGNORECASE)
        if doc_num_match:
            cand = doc_num_match.group(1).strip()
            # Ensure it's not a 9-digit INN
            if not (len(cand) == 9 and cand.isdigit() and cand.startswith(("2", "3"))):
                meta["doc_number"] = cand

        # 2. Document Date
        date_match = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", text)
        if date_match:
            try:
                day, month, year = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                meta["doc_date"] = date(year, month, day)
            except Exception:
                pass

        # 3. 9-digit INN/STIR matches
        inn_matches = re.findall(r"\b([23]\d{8})\b", text)
        if len(inn_matches) >= 1:
            meta["supplier_inn"] = inn_matches[0]
        if len(inn_matches) >= 2:
            meta["buyer_inn"] = inn_matches[1]

        # 4. Supplier & Buyer names heuristics
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for idx, line in enumerate(lines):
            l_lower = line.lower()
            if any(k in l_lower for k in ["yetkazib beruvchi", "поставщик", "sotuvchi"]) and idx + 1 < len(lines):
                if not meta["supplier_name"]:
                    meta["supplier_name"] = lines[idx + 1][:80]
            elif any(k in l_lower for k in ["xaridor", "покупатель", "buyurtmachi"]) and idx + 1 < len(lines):
                if not meta["buyer_name"]:
                    meta["buyer_name"] = lines[idx + 1][:80]

        return meta

    @classmethod
    def extract_document_from_pdf(cls, pdf_bytes: bytes) -> ExtractedDocument:
        """
        Processes PDF bytes:
        1. Attempts vector table extraction via PyMuPDF.
        2. If tables are found, extracts line items and text metadata.
        3. If vector extraction yields no items (e.g. pure scanned pages),
           runs OCR pipeline with image enhancement.
        """
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        all_line_items: List[ExtractedLineItem] = []
        combined_text = ""

        # Phase 1: Try PyMuPDF find_tables on each page
        for page_idx in range(len(doc)):
            page = doc.load_page(page_idx)
            page_text = page.get_text()
            combined_text += f"\n{page_text}"

            try:
                tables = page.find_tables()
                for table in tables:
                    df = table.extract()
                    if not df or len(df) < 2:
                        continue
                    
                    # Convert to header + rows
                    header_row_idx = 0
                    headers = [str(c or "").strip().lower() for c in df[0]]
                    
                    # Look for characteristic table columns
                    name_col_idx = None
                    qty_col_idx = None
                    price_col_idx = None
                    total_col_idx = None
                    unit_col_idx = None
                    ikpu_col_idx = None
                    vat_rate_col_idx = None
                    vat_amount_col_idx = None

                    for col_idx, h in enumerate(headers):
                        if any(k in h for k in ["nomi", "tovar", "mahsulot", "xizmat", "наименование"]):
                            name_col_idx = col_idx
                        elif any(k in h for k in ["miqdor", "soni", "hajm", "кол-во", "количество"]):
                            qty_col_idx = col_idx
                        elif any(k in h for k in ["narx", "baho", "цена", "tarif"]):
                            price_col_idx = col_idx
                        elif any(k in h for k in ["jami", "summa", "всего", "стоимость"]):
                            total_col_idx = col_idx
                        elif any(k in h for k in ["birlik", "o'lchov", "ед.", "ед"]):
                            unit_col_idx = col_idx
                        elif any(k in h for k in ["mxik", "ikpu", "мхик", "икпу"]):
                            ikpu_col_idx = col_idx
                        elif any(k in h for k in ["stavka", "qqs stavka", "ндс"]):
                            vat_rate_col_idx = col_idx

                    # If name_col_idx found, parse rows
                    if name_col_idx is not None:
                        for row in df[header_row_idx + 1:]:
                            if len(row) <= name_col_idx:
                                continue
                            raw_name = str(row[name_col_idx] or "").strip()
                            # Skip summary/total footer rows
                            if not raw_name or any(k in raw_name.lower() for k in ["jami", "итого", "всего", "t/r"]):
                                continue

                            qty = cls.clean_decimal(row[qty_col_idx]) if qty_col_idx is not None and len(row) > qty_col_idx else Decimal("1")
                            price = cls.clean_decimal(row[price_col_idx]) if price_col_idx is not None and len(row) > price_col_idx else Decimal("0")
                            tot = cls.clean_decimal(row[total_col_idx]) if total_col_idx is not None and len(row) > total_col_idx else Decimal("0")
                            unit_str = str(row[unit_col_idx] or "").strip() if unit_col_idx is not None and len(row) > unit_col_idx else "dona"
                            ikpu_str = str(row[ikpu_col_idx] or "").strip() if ikpu_col_idx is not None and len(row) > ikpu_col_idx else None
                            
                            # Clean IKPU
                            if ikpu_str:
                                clean_ikpu = re.sub(r"\D", "", ikpu_str)
                                ikpu_str = clean_ikpu if len(clean_ikpu) == 17 else None

                            if tot <= 0 and price > 0 and qty > 0:
                                tot = qty * price
                            elif price <= 0 and tot > 0 and qty > 0:
                                price = tot / qty

                            if tot > 0 or qty > 0:
                                all_line_items.append(ExtractedLineItem(
                                    item_name=raw_name,
                                    ikpu_code=ikpu_str,
                                    unit=unit_str or "dona",
                                    quantity=qty if qty > 0 else Decimal("1"),
                                    price=price,
                                    vat_rate=Decimal("12"),
                                    vat_amount=(tot * Decimal("0.12") / Decimal("1.12")).quantize(Decimal("0.01")),
                                    total_amount=tot,
                                    confidence=0.98
                                ))
            except Exception as e:
                logger.warning(f"Error parsing table from page {page_idx}: {e}")

        meta = cls.extract_metadata_from_text(combined_text)

        # Text lines fallback if find_tables didn't find vector tables
        if not all_line_items and combined_text:
            lines = [ln.strip() for ln in combined_text.split("\n") if ln.strip()]
            for line in lines:
                num_matches = re.findall(r"\b\d+(?:[.,]\d+)?\b", line)
                if len(num_matches) >= 2 and not any(k in line.lower() for k in ["inn", "sana", "№", "faktura", "yetkazib", "xaridor", "t/r"]):
                    name_part = re.sub(r"\b\d+(?:[.,]\d+)?\b", "", line).strip()
                    if len(name_part) >= 3:
                        q = cls.clean_decimal(num_matches[-2] if len(num_matches) >= 2 else "1")
                        tot = cls.clean_decimal(num_matches[-1])
                        p = tot / q if q > 0 else tot
                        all_line_items.append(ExtractedLineItem(
                            item_name=name_part,
                            ikpu_code=None,
                            unit="dona",
                            quantity=q if q > 0 else Decimal("1"),
                            price=p,
                            vat_rate=Decimal("12"),
                            vat_amount=(tot * Decimal("0.12") / Decimal("1.12")).quantize(Decimal("0.01")),
                            total_amount=tot,
                            confidence=0.92
                        ))

        # Phase 2: If no line items extracted via vector tables or text (e.g. Scanned PDF)
        if not all_line_items:
            try:
                enhanced_images = pdf_to_enhanced_images(pdf_bytes, dpi=200)
                extractor = OCRExtractor()
                for img_array in enhanced_images:
                    png_bytes = cv2_to_png_bytes(img_array)
                    extracted_page = extractor._heuristic_fallback_extraction(png_bytes, "page.png")
                    if extracted_page.line_items:
                        all_line_items.extend(extracted_page.line_items)
                    if not meta["doc_number"] and extracted_page.doc_number:
                        meta["doc_number"] = extracted_page.doc_number
                    if not meta["supplier_name"] and extracted_page.supplier_name:
                        meta["supplier_name"] = extracted_page.supplier_name
                    if not meta["supplier_inn"] and extracted_page.supplier_inn:
                        meta["supplier_inn"] = extracted_page.supplier_inn
                    if not meta["buyer_name"] and extracted_page.buyer_name:
                        meta["buyer_name"] = extracted_page.buyer_name
                    if not meta["buyer_inn"] and extracted_page.buyer_inn:
                        meta["buyer_inn"] = extracted_page.buyer_inn
            except Exception as ex:
                logger.error(f"Fallback OCR extraction failed: {ex}")

        # Default fallback line item if completely empty
        if not all_line_items:
            all_line_items.append(ExtractedLineItem(
                item_name="PDF Hujjat Tahlili (Tovar aniqlanmadi)",
                ikpu_code=None,
                unit="dona",
                quantity=Decimal("1"),
                price=Decimal("0"),
                vat_rate=Decimal("12"),
                vat_amount=Decimal("0"),
                total_amount=Decimal("0"),
                confidence=0.5
            ))

        return ExtractedDocument(
            doc_number=meta["doc_number"] or "PDF-001",
            doc_date=meta["doc_date"] or date.today(),
            doc_type="EHF",
            supplier_name=meta["supplier_name"] or "Yetkazib Beruvchi MCHJ",
            supplier_inn=meta["supplier_inn"],
            buyer_name=meta["buyer_name"] or "Xaridor Korxona",
            buyer_inn=meta["buyer_inn"],
            line_items=all_line_items,
            overall_confidence=0.95
        )
