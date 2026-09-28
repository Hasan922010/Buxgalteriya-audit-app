import re
import json
import logging
from typing import List, Dict, Any, Optional
import pandas as pd
from app.core.config import settings
from app.schemas.document import ColumnMapping

logger = logging.getLogger("smart_mapper")

class SmartExcelMapper:
    """
    LLM-assisted column auto-detection and fallback schema mapper.
    Combines fuzzy heuristic matching with Gemini / OpenAI API.
    Supports Excel (.xlsx, .xls, .csv) and PDF documents.
    """

    @classmethod
    async def auto_detect_mapping(cls, headers: List[str], sample_rows: List[Dict[str, Any]]) -> ColumnMapping:
        """
        Attempts AI mapping if API key is configured; otherwise uses deterministic fuzzy heuristic.
        """
        if settings.GEMINI_API_KEY:
            try:
                ai_mapping = await cls._detect_with_gemini(headers, sample_rows)
                if ai_mapping:
                    return ai_mapping
            except Exception as e:
                logger.warning(f"Gemini column mapping failed, falling back to heuristics: {e}")

        if settings.OPENAI_API_KEY:
            try:
                ai_mapping = await cls._detect_with_openai(headers, sample_rows)
                if ai_mapping:
                    return ai_mapping
            except Exception as e:
                logger.warning(f"OpenAI column mapping failed, falling back to heuristics: {e}")

        return cls._heuristic_mapping(headers)

    @classmethod
    def _extract_df_from_pdf(cls, file_path: str) -> tuple[pd.DataFrame, int, List[str]]:
        """
        Extracts structured tabular data from PDF files using pdfplumber.
        Handles both formal vector tables and semi-structured text lines.
        """
        import pdfplumber

        all_rows: List[List[str]] = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            for row in table:
                                if row and any(cell and str(cell).strip() for cell in row):
                                    clean_row = [str(cell).strip().replace('\n', ' ') if cell is not None else "" for cell in row]
                                    all_rows.append(clean_row)
                    else:
                        text = page.extract_text()
                        if text:
                            for line in text.splitlines():
                                line = line.strip()
                                if not line:
                                    continue
                                if "|" in line:
                                    parts = [p.strip() for p in line.split("|") if p.strip()]
                                else:
                                    parts = [p.strip() for p in re.split(r'\s{2,}|\t', line) if p.strip()]
                                if len(parts) >= 2:
                                    all_rows.append(parts)
        except Exception as e:
            logger.error(f"Error extracting tabular data from PDF {file_path}: {e}")

        if not all_rows:
            default_cols = ["№", "Mahsulot nomi", "MXIK kodi", "O'lchov birligi", "Miqdor", "Narx", "Jami summa"]
            return pd.DataFrame(columns=default_cols), 0, default_cols

        # Normalize column widths
        max_cols = max(len(r) for r in all_rows)
        normalized_rows = [r + [""] * (max_cols - len(r)) for r in all_rows]

        # Detect best header row within first 15 rows
        keywords = [
            "№", "маҳсулот", "махсулот", "nomi", "мхик", "ikpu", "birlik", "сони",
            "миқдор", "микдор", "miqdor", "narx", "сумма", "цена", "qoldiq", "kirim",
            "chiqim", "жами", "итого", "tovar", "ҳужжат", "код", "nomer", "sana", "date"
        ]
        best_row = 0
        max_matches = 0
        for idx in range(min(15, len(normalized_rows))):
            row_str = " ".join([str(v).lower() for v in normalized_rows[idx]])
            matches = sum(1 for kw in keywords if kw in row_str)
            if matches > max_matches:
                max_matches = matches
                best_row = idx

        raw_headers = normalized_rows[best_row]
        clean_columns: List[str] = []
        for i, col in enumerate(raw_headers):
            c_str = str(col).strip()
            if not c_str or c_str.lower() in ["unnamed", "none", "nan"]:
                c_str = f"Ustun_{i+1}"
            base_col = c_str
            suffix = 1
            while c_str in clean_columns:
                c_str = f"{base_col}_{suffix}"
                suffix += 1
            clean_columns.append(c_str)

        data_rows = normalized_rows[best_row + 1:]
        filtered_data = [
            r for r in data_rows
            if any(cell.strip() for cell in r) and " ".join(r) != " ".join(raw_headers)
        ]

        df = pd.DataFrame(filtered_data, columns=clean_columns)
        return df, int(best_row), clean_columns

    @classmethod
    def find_header_row_and_df(cls, file_path: str) -> tuple[pd.DataFrame, int, List[str]]:
        """
        Scans top rows of an Excel/CSV/PDF file to identify the true header row.
        Handles files with title banners (e.g. Soliq.uz reports with title on row 0 and headers on row 1).
        """
        ext = file_path.lower().split(".")[-1]
        
        # 1. Read first 15 rows without header
        if ext in ["xlsx", "xls"]:
            raw_preview = pd.read_excel(file_path, header=None, nrows=15)
        elif ext == "csv":
            raw_preview = pd.read_csv(file_path, header=None, nrows=15, sep=None, engine="python")
        elif ext == "pdf":
            return cls._extract_df_from_pdf(file_path)
        else:
            raise ValueError(f"Fayl formati qo'llab-quvvatlanmaydi: {ext}")

        best_row = 0
        max_matches = 0
        keywords = [
            "№", "маҳсулот", "махсулот", "хизмат", "штрих", "gtin", "мхик", "ikpu",
            "қиймати", "киймати", "вақти", "вакти", "сотилган", "қайтарилган", "кайтарилган",
            "сумма", "сони", "миқдор", "микдор", "нарх", "цена", "sana", "date", "дата",
            "tovar", "nomi", "inn", "stir", "kontragent", "жами", "итого", "total"
        ]

        for idx, row in raw_preview.iterrows():
            row_str = " ".join([str(val).lower() for val in row.dropna() if str(val).strip()])
            matches = sum(1 for kw in keywords if kw in row_str)
            if matches > max_matches:
                max_matches = matches
                best_row = idx

        # 2. Read full DataFrame with detected header
        if ext in ["xlsx", "xls"]:
            df = pd.read_excel(file_path, skiprows=best_row)
        else:
            df = pd.read_csv(file_path, skiprows=best_row, sep=None, engine="python")

        # Clean columns: strip spaces, handle duplicate or Unnamed cols
        clean_columns: List[str] = []
        for i, col in enumerate(df.columns):
            c_str = str(col).strip()
            if c_str.startswith("Unnamed:") or not c_str:
                c_str = f"Ustun_{i+1}"
            clean_columns.append(c_str)
        df.columns = clean_columns

        # Drop rows that are completely empty
        df = df.dropna(how="all")

        return df, int(best_row), clean_columns

    @classmethod
    def _heuristic_mapping(cls, headers: List[str]) -> ColumnMapping:
        mapping = ColumnMapping()
        for h in headers:
            hl = str(h).lower().strip()

            # 1. Tartib / Hujjat raqami
            if not mapping.doc_num_col and (
                hl == "№" or any(k in hl for k in ["тартиб", "raqam", "nomer", "hujjat", "doc", "номер", "ҳужжат", "хужжат", "инвойс", "чек"])
            ):
                mapping.doc_num_col = h

            # 2. Shtrix (GTIN) kod
            elif not mapping.barcode_col and any(k in hl for k in ["штрих", "gtin", "barcode", "barkod", "штрих-код", "штрихкод"]):
                mapping.barcode_col = h

            # 3. MXIK / IKPU
            elif not mapping.ikpu_col and any(k in hl for k in ["мхик", "mxik", "ikpu", "икпу", "идентификацион"]):
                mapping.ikpu_col = h

            # 4. Qaytarilgan mahsulot soni
            elif not mapping.return_qty_col and any(k in hl for k in [
                "қайтарилган маҳсулот (хизмат) сони", "қайтарилган маҳсулот сони", "қайтарилган сони", "қайтарилган миқдор", "кайтарилган сони", "возврат сони", "возврат кол-во"
            ]):
                mapping.return_qty_col = h

            # 5. Qaytarilgan mahsulot summasi
            elif not mapping.return_sum_col and any(k in hl for k in [
                "қайтарилган маҳсулот (хизмат) суммаси", "қайтарилган маҳсулот суммаси", "қайтарилган суммаси", "қайтарилган сумма", "кайтарилган сумма", "возврат сумма", "возврат"
            ]):
                mapping.return_sum_col = h

            # 6. Sotilgan mahsulot soni (Outflow Qty / Qty)
            elif not mapping.outflow_qty_col and any(k in hl for k in [
                "сотилган маҳсулот (хизмат) сони", "сотилган маҳсулот сони", "сотилган сони", "сотилган миқдор", "сотилган микдор", "chiqim miqdor", "rashod soni", "outflow qty"
            ]):
                mapping.outflow_qty_col = h
                if not mapping.qty_col:
                    mapping.qty_col = h

            # 7. Sotilgan mahsulot summasi (Outflow Sum / Total)
            elif not mapping.outflow_sum_col and any(k in hl for k in [
                "сотилган маҳсулот (хизмат) суммаси", "сотилган маҳсулот суммаси", "сотилган суммаси", "сотилган сумма", "chiqim summa", "rashod", "outflow sum"
            ]):
                mapping.outflow_sum_col = h
                if not mapping.total_col:
                    mapping.total_col = h

            # 8. Sana / Oxirgi sotilgan vaqti
            elif not mapping.date_col and any(k in hl for k in [
                "сотилган вақти", "сотилган вакти", "охирги сотилган", "вақти", "вакти", "вақт", "вакт", "сана", "дата", "sana", "date", "kun"
            ]):
                mapping.date_col = h

            # 9. Narx / O'rtacha qiymat
            elif not mapping.price_col and any(k in hl for k in [
                "ўртача маҳсулот", "ўртача қиймати", "ўртача махсулот", "ўртача", "уртача", "қиймати", "киймати", "narx", "cena", "price", "нарх", "цена"
            ]):
                mapping.price_col = h

            # 10. Mahsulot / Tovar / Xizmat nomi
            elif not mapping.item_name_col and any(k in hl for k in [
                "маҳсулот (хизмат) номи", "маҳсулот номи", "махсулот номи", "маҳсулот", "махсулот", "хизмат", "tovar", "mahsulot", "xizmat", "item", "nomi", "material", "товар", "номи", "наименование", "номенклатура"
            ]):
                mapping.item_name_col = h

            # 11. Kontragent nomi
            elif not mapping.counterparty_col and any(k in hl for k in [
                "kontragent", "hamkor", "xaridor", "yetkazib", "tashkilot", "klient", "контрагент", "харидор", "етказиб", "клиент", "покупатель", "поставщик"
            ]):
                mapping.counterparty_col = h

            # 12. Kontragent STIR (INN)
            elif not mapping.counterparty_inn_col and any(k in hl for k in ["inn", "stir", "инн", "стир"]):
                mapping.counterparty_inn_col = h

            # 13. O'lchov birligi (Unit)
            elif not mapping.unit_col and any(k in hl for k in [
                "o'lchov birligi", "olchov birligi", "o'lchov", "olchov", "birlik", "birligi",
                "ўлчов бирлиги", "улчов бирлиги", "бирлик", "ед. изм.", "ед.изм", "единица измерения", "единица", "unit"
            ]):
                mapping.unit_col = h

            # 14. Boshlang'ich qoldiq (Initial Stock) - Miqdor va Summa
            elif not mapping.initial_qty_col and any(k in hl for k in [
                "бошланғич қолдиқ: миқдор", "бошланғич қолдиқ (миқдор)", "бошланғич миқдор", "бошланғич қолдиқ сони",
                "boshlang'ich qoldiq miqdor", "boshlang'ich miqdor", "нач остаток кол-во", "нач. кол-во", "нач. остаток (кол-во)"
            ]):
                mapping.initial_qty_col = h
            elif not mapping.initial_sum_col and any(k in hl for k in [
                "бошланғич қолдиқ: сумма", "бошланғич қолдиқ (сумма)", "бошланғич сумма", "бошланғич қолдиқ қиймати",
                "boshlang'ich qoldiq summa", "boshlang'ich summa", "нач остаток сумма", "нач. сумма", "нач. остаток (сумма)"
            ]):
                mapping.initial_sum_col = h

            # 15. Oxirgi qoldiq (Final Stock) - Miqdor va Summa
            elif not mapping.final_qty_col and any(k in hl for k in [
                "охирги қолдиқ: миқдор", "охирги қолдиқ (миқдор)", "охирги миқдор", "охирги қолдиқ сони",
                "oxirgi qoldiq miqdor", "oxirgi miqdor", "кон остаток кол-во", "кон. кол-во", "кон. остаток (кол-во)"
            ]):
                mapping.final_qty_col = h
            elif not mapping.final_sum_col and any(k in hl for k in [
                "охирги қолдиқ: сумма", "охирги қолдиқ (сумма)", "охирги сумма", "охирги қолдиқ қиймати",
                "oxirgi qoldiq summa", "oxirgi summa", "кон остаток сумма", "кон. сумма", "кон. остаток (сумма)"
            ]):
                mapping.final_sum_col = h

            # 16. Kirim miqdori va summasi
            elif not mapping.inflow_qty_col and any(k in hl for k in [
                "кирим: миқдор", "кирим (миқдор)", "кирим миқдор", "кирим сони", "prihod soni", "inflow qty", "кирим миқдор", "приход (кол-во)", "приход кол-во"
            ]):
                mapping.inflow_qty_col = h
            elif not mapping.inflow_sum_col and any(k in hl for k in [
                "кирим: сумма", "кирим (сумма)", "кирим сумма", "kirim summa", "prihod", "kirim", "кирим сумма", "приход (сумма)", "приход сумма"
            ]):
                mapping.inflow_sum_col = h

            # 14. Umumiy miqdor
            elif not mapping.qty_col and any(k in hl for k in ["miqdor", "soni", "dona", "kol-vo", "qty", "миқдор", "микдор", "сони", "дона"]):
                mapping.qty_col = h

            # 15. Umumiy jami summa
            elif not mapping.total_col and any(k in hl for k in ["jami", "summa", "total", "itogo", "сумма", "жами", "итого"]):
                mapping.total_col = h

            # 16. QQS
            elif not mapping.vat_rate_col and any(k in hl for k in ["stavka", "qqs stavka", "nds %", "ққс ставкаси", "ставка"]):
                mapping.vat_rate_col = h
            elif not mapping.vat_amount_col and any(k in hl for k in ["qqs summa", "nds summa", "ққс суммаси"]):
                mapping.vat_amount_col = h

        # Fallbacks: if total_col not set but outflow_sum_col is set
        if not mapping.total_col and mapping.outflow_sum_col:
            mapping.total_col = mapping.outflow_sum_col
        if not mapping.qty_col and mapping.outflow_qty_col:
            mapping.qty_col = mapping.outflow_qty_col

        return mapping

    @classmethod
    async def _detect_with_gemini(cls, headers: List[str], sample_rows: List[Dict[str, Any]]) -> Optional[ColumnMapping]:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        prompt = f"""You are a specialized financial data architect for Uzbekistan accounting software.
Analyze the following Excel column headers and sample data rows, and map them to our target accounting schema.

Available column headers: {headers}
Sample rows: {json.dumps(sample_rows[:3], ensure_ascii=False)}

Target Schema keys:
- date_col: column containing transaction date
- doc_num_col: column containing invoice or order number
- item_name_col: column containing goods or service name
- counterparty_col: column containing partner or company name
- counterparty_inn_col: column containing STIR (TIN)
- ikpu_col: column containing MXIK / IKPU 17-digit code
- qty_col: column containing item quantity
- price_col: column containing unit price
- total_col: column containing total amount in UZS
- vat_rate_col: column containing VAT rate (0% or 12%)
- vat_amount_col: column containing VAT amount

Return ONLY a valid JSON object matching the target schema keys where the value is the exact column header name from the available columns list (or null if not found)."""

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)
        return ColumnMapping(**data)

    @classmethod
    async def _detect_with_openai(cls, headers: List[str], sample_rows: List[Dict[str, Any]]) -> Optional[ColumnMapping]:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        prompt = f"""You are a financial data architect for Uzbekistan accounting software.
Available column headers: {headers}
Sample rows: {json.dumps(sample_rows[:3], ensure_ascii=False)}

Target Schema keys:
- date_col, doc_num_col, item_name_col, counterparty_col, counterparty_inn_col,
- ikpu_col, qty_col, price_col, total_col, vat_rate_col, vat_amount_col.

Return JSON mapping target keys to exact header names."""

        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You map tabular accounting columns to standard accounting fields. Output JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        data = json.loads(resp.choices[0].message.content)
        return ColumnMapping(**data)
