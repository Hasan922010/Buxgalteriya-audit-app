"""Protection against spreadsheet formula injection in generated .xlsx files."""
import re

from openpyxl import Workbook

# The only formulas this application generates itself (see modules/ocr/tax_excel_generator.py).
# Anything else starting with "=" came from user data (item / counterparty names, OCR text ...)
# and must be stored as plain text so Excel never executes it (HYPERLINK, WEBSERVICE, DDE, ...).
_ALLOWED_FORMULA = re.compile(r"=(SUM|AVERAGE)\(\$?[A-Z]{1,3}\$?\d+:\$?[A-Z]{1,3}\$?\d+\)")


def neutralize_formula_injection(wb: Workbook) -> Workbook:
    """Turns every non-allowlisted formula cell into a text cell. Call right before saving."""
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.data_type == "f" and not _ALLOWED_FORMULA.fullmatch(str(cell.value)):
                    cell.data_type = "s"
    return wb
