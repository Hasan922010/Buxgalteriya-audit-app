# MODULE SPECIFICATION: Tax Audit Scanned Table Extraction & Formatted Excel Converter
# Target: "Yordamchi Buxgalter AI" - OCR Workspace Upgrade
# Execution: Autonomous (Antigravity Agent)

## 1. PURPOSE & BUSINESS NEED
Tax inspection documents such as "Киримсиз сотилган товарлар таҳлили" (Tax Turnover & Stock Discrepancy Audits) arrive as complex, scanned, multi-page PDFs with merged hierarchical table headers, dense numerical grids, and punitive tax penalty calculations.
The system must:
1. Recognize multi-column inventory tables where columns represent Opening Balance, Inflows (Kirim), Outflows (Sotilgan), Closing Balance, and Discrepancies (Kirimsiz sotuv).
2. Clean noisy numbers, normalize whitespace separators (`20 025 600,00` -> `20025600.00`).
3. Validate row-level inventory balance math:
   `Calculated_Discrepancy_Qty = MAX(0, Outflow_Qty - (Opening_Qty + Inflow_Qty))`
   `Discrepancy_Amount = Calculated_Discrepancy_Qty * Avg_Selling_Price`
4. Provide a single-click "Excelga eksport qilish" button in the OCR Workspace that generates an executive-level, fully formatted `.xlsx` workbook complete with active Excel formulas (`=SUM()`), formatted numbers, frozen header panes, and tax penalty summary blocks (VAT 12%, Profit Tax 15%, Financial Penalty 20%).

---

## 2. BACKEND ARCHITECTURE & IMPLEMENTATION

### File 1: Data Model (`backend/app/modules/ocr/tax_audit_schemas.py`)
```python
from pydantic import BaseModel, Field
from typing import List, Optional
from decimal import Decimal

class TaxAuditItemRow(BaseModel):
    item_no: int
    item_name: str
    # 1-yanvar holatiga qoldiq
    opening_qty: Decimal = Decimal("0.0")
    opening_amount: Decimal = Decimal("0.0")
    # Davr kirimi
    inflow_qty: Decimal = Decimal("0.0")
    inflow_amount: Decimal = Decimal("0.0")
    # Sotilgan (Chiqim)
    sold_qty: Decimal = Decimal("0.0")
    avg_price: Decimal = Decimal("0.0")
    sold_amount: Decimal = Decimal("0.0")
    # Davr oxiriga qoldiq
    closing_qty: Decimal = Decimal("0.0")
    closing_amount: Decimal = Decimal("0.0")
    # Kirimsiz sotilgan farq
    diff_qty: Decimal = Decimal("0.0")
    diff_amount: Decimal = Decimal("0.0")
    # Tekshiruv bayroqlari
    math_verified: bool = True
    confidence: float = 1.0

class TaxPenaltySummary(BaseModel):
    total_discrepancy_amount: Decimal  # Jami kirimsiz sotuv summasi
    vat_amount: Decimal                # QQS (12%)
    net_tax_base: Decimal              # QQSsiz baza
    profit_tax_addition: Decimal       # Foyda solig'iga qo'shimcha (15%)
    financial_penalty: Decimal         # Moliyaviy jarima (20%)
    total_budget_liability: Decimal    # Davlat byudjetiga jami to'lov

class TaxAuditDocument(BaseModel):
    company_name: str
    company_inn: str
    audit_year: int = 2023
    title: str
    items: List[TaxAuditItemRow]
    summary: Optional[TaxPenaltySummary] = None
```

### File 2: Excel Converter Engine (`backend/app/modules/ocr/tax_excel_generator.py`)
```python
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from io import BytesIO
from .tax_audit_schemas import TaxAuditDocument

class TaxAuditExcelGenerator:
    @staticmethod
    def generate_workbook(doc: TaxAuditDocument) -> bytes:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Киримсиз товарлар таҳлили"
        ws.views.sheetView[0].showGridLines = True

        NAVY = "1B365D"
        BLUE = "4A90E2"
        LIGHT_BG = "E8F1F5"
        ZEBRA = "F9FBFC"
        ALERT_RED = "FFF0F0"
        BORDER_CLR = "D3D3D3"

        font_title = Font(name="Calibri", size=13, bold=True, color="FFFFFF")
        font_header = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        font_sub = Font(name="Calibri", size=9, bold=True, color="1B365D")
        font_data = Font(name="Calibri", size=10)
        font_bold = Font(name="Calibri", size=10, bold=True)

        thin = Border(left=Side(style='thin', color=BORDER_CLR),
                      right=Side(style='thin', color=BORDER_CLR),
                      top=Side(style='thin', color=BORDER_CLR),
                      bottom=Side(style='thin', color=BORDER_CLR))

        # Title
        ws.merge_cells("A1:M1")
        ws["A1"] = f'"{doc.company_name}" (СТИР: {doc.company_inn}) томонидан {doc.audit_year} йил давомида киримсиз сотилган товарлар таҳлили'
        ws["A1"].font = font_title
        ws["A1"].fill = PatternFill(start_color=NAVY, end_color=NAVY, fill_type="solid")
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 36

        # Subtitle
        ws.merge_cells("A2:M2")
        ws["A2"] = "Манба: Камерал солиқ текшируви ҳисоботидан автоматик рақамлаштирилган"
        ws["A2"].font = Font(name="Calibri", size=9, italic=True, color="666666")
        ws["A2"].alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[2].height = 18

        # Hierarchical Headers
        headers = [
            ("A3:A4", "№", BLUE),
            ("B3:B4", "Товар номи", BLUE),
            ("C3:D3", f"{doc.audit_year} йил 1 январ қолдиқ", NAVY),
            ("E3:F3", f"{doc.audit_year} йил давомида кирим", NAVY),
            ("G3:I3", f"{doc.audit_year} йил сотилган (чиқим)", NAVY),
            ("J3:K3", f"{doc.audit_year} йил охирига қолдиқ", NAVY),
            ("L3:M3", "Фарқи (Киримсиз сотув)", "B22222"),
        ]
        for rng, txt, clr in headers:
            ws.merge_cells(rng)
            ws[rng.split(":")[0]].value = txt
            ws[rng.split(":")[0]].font = font_header
            ws[rng.split(":")[0]].fill = PatternFill(start_color=clr, end_color=clr, fill_type="solid")
            ws[rng.split(":")[0]].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        subs = [
            ("C4", "Сони"), ("D4", "Суммаси"),
            ("E4", "Сони"), ("F4", "Суммаси"),
            ("G4", "Сони"), ("H4", "Ўртача нархи"), ("I4", "Суммаси"),
            ("J4", "Сони"), ("K4", "Суммаси"),
            ("L4", "Сони"), ("M4", "Киримсиз сумма")
        ]
        for col, txt in subs:
            ws[col].value = txt
            ws[col].font = font_sub
            ws[col].fill = PatternFill(start_color=LIGHT_BG, end_color=LIGHT_BG, fill_type="solid")
            ws[col].alignment = Alignment(horizontal="center", vertical="center")

        for r in range(3, 5):
            ws.row_dimensions[r].height = 24
            for c in range(1, 14):
                ws.cell(row=r, column=c).border = thin

        # Data Injection
        start_row = 5
        for idx, item in enumerate(doc.items, 1):
            curr_row = start_row + idx - 1
            ws.row_dimensions[curr_row].height = 20
            is_zebra = (idx % 2 == 0)
            z_fill = PatternFill(start_color=ZEBRA, end_color=ZEBRA, fill_type="solid") if is_zebra else None

            row_data = [
                (1, idx, "@", Alignment(horizontal="center")),
                (2, item.item_name, "@", Alignment(horizontal="left")),
                (3, float(item.opening_qty), "#,##0.00", Alignment(horizontal="right")),
                (4, float(item.opening_amount), "#,##0.00", Alignment(horizontal="right")),
                (5, float(item.inflow_qty), "#,##0.00", Alignment(horizontal="right")),
                (6, float(item.inflow_amount), "#,##0.00", Alignment(horizontal="right")),
                (7, float(item.sold_qty), "#,##0.00", Alignment(horizontal="right")),
                (8, float(item.avg_price), "#,##0.00", Alignment(horizontal="right")),
                (9, float(item.sold_amount), "#,##0.00", Alignment(horizontal="right")),
                (10, float(item.closing_qty), "#,##0.00", Alignment(horizontal="right")),
                (11, float(item.closing_amount), "#,##0.00", Alignment(horizontal="right")),
                (12, float(item.diff_qty), "#,##0.00", Alignment(horizontal="right")),
                (13, float(item.diff_amount), "#,##0.00", Alignment(horizontal="right")),
            ]

            for c_idx, val, fmt, align in row_data:
                c = ws.cell(row=curr_row, column=c_idx, value=val)
                c.font = font_data
                c.number_format = fmt
                c.alignment = align
                c.border = thin
                if c_idx in [12, 13] and val > 0:
                    c.fill = PatternFill(start_color=ALERT_RED, end_color=ALERT_RED, fill_type="solid")
                    c.font = font_bold
                elif z_fill:
                    c.fill = z_fill

        last_row = start_row + len(doc.items) - 1
        tot_row = last_row + 1

        # Totals
        ws.merge_cells(f"A{tot_row}:B{tot_row}")
        ws[f"A{tot_row}"] = "ЖАМИ ҲИСОБОТ БЎЙИЧА:"
        ws[f"A{tot_row}"].font = font_header
        ws[f"A{tot_row}"].fill = PatternFill(start_color=NAVY, end_color=NAVY, fill_type="solid")
        ws[f"A{tot_row}"].alignment = Alignment(horizontal="right", vertical="center")

        for c_idx in range(3, 14):
            col_letter = get_column_letter(c_idx)
            c = ws.cell(row=tot_row, column=c_idx)
            if c_idx == 8:
                c.value = f"=AVERAGE({col_letter}{start_row}:{col_letter}{last_row})"
            else:
                c.value = f"=SUM({col_letter}{start_row}:{col_letter}{last_row})"
            c.font = font_header
            c.fill = PatternFill(start_color=NAVY, end_color=NAVY, fill_type="solid")
            c.number_format = "#,##0.00"
            c.border = thin
            c.alignment = Alignment(horizontal="right", vertical="center")

        # Auto column widths
        widths = {1: 6, 2: 46, 3: 12, 4: 16, 5: 12, 6: 18, 7: 12, 8: 15, 9: 18, 10: 12, 11: 18, 12: 12, 13: 20}
        for col_i, w in widths.items():
            ws.column_dimensions[get_column_letter(col_i)].width = w

        out = BytesIO()
        wb.save(out)
        return out.getvalue()
```

### File 3: FastAPI Endpoints (`backend/app/modules/ocr/router.py`)
Add endpoints:
1. `POST /api/v1/ocr/tax-audit/parse` - Accepts `.pdf` scan, invokes OpenCV cleaning + Vision table extractor -> returns `TaxAuditDocument` JSON.
2. `POST /api/v1/ocr/tax-audit/export-excel` - Takes `TaxAuditDocument` JSON payload and streams formatted `.xlsx` file download.

---

## 3. FRONTEND ENHANCEMENT (OCR WORKSPACE)

In `frontend/src/components/ocr/VerificationWorkspace.tsx`:
1. **Document Classification Badge**: Detect if document is a standard EHF or a `Tax Audit Report` ("Киримсиз сотилган товарлар таҳлили").
2. **Action Toolbar Addition**:
   - Add a prominent **"Excelga yuklab olish (.xlsx)"** button with an Excel icon (`lucide-react: FileSpreadsheet`).
   - Add **"Soliq xatarlarini tahlil qilish"** modal displaying calculated VAT (12%), Profit Tax addition (15%), and Financial Penalty (20%).
3. **Discrepancy Highlighting**: Color rows where `diff_qty > 0` with a warning tint (`bg-red-50 text-red-700`) so accountants can spot problematic inventory lines in seconds.