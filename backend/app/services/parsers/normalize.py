"""
Locale-aware parsing of amounts and dates found in Uzbek accounting files
(Didox, Soliq.uz, bank-client, 1C exports).

Rules:
- Amounts: spaces / NBSP / apostrophes are thousands separators. When both ',' and '.'
  appear, the last one is the decimal separator. A single ',' or '.' is a decimal
  separator (Uzbek/Russian locale); repeated ones are thousands separators.
- Dates are always day-first (DD.MM.YYYY); month-first is never guessed.
- Unparseable input returns None instead of silently becoming 0 or today's date.
"""
import math
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import numpy as np
import pandas as pd

_EMPTY_TOKENS = {"", "-", "—", "nan", "none", "null", "nat"}
_CURRENCY_RE = re.compile(r"so['’`ʻ]?m|сўм|сум|uzs|sum", re.IGNORECASE)
_GROUPING_CHARS_RE = re.compile(r"[\s   '’ʼ`]")
_NUMBER_RE = re.compile(r"^\d+(\.\d+)?$")

_DATE_FORMATS = (
    "%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y",
    "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d",
)
_EXCEL_EPOCH = date(1899, 12, 30)
_EXCEL_SERIAL_MIN = 20000  # 1954-10-03
_EXCEL_SERIAL_MAX = 80000  # 2119-01-10


def _is_missing(value: Any) -> bool:
    if value is None or value is pd.NaT:
        return True
    if pd.api.types.is_scalar(value):
        try:
            return bool(pd.isna(value))
        except (TypeError, ValueError):
            return False
    return False


def _strip_thousands(number: str, separator: str) -> Optional[str]:
    """Removes a thousands separator after checking the 3-digit grouping."""
    groups = number.split(separator)
    if not groups[0] or len(groups[0]) > 3 or any(len(g) != 3 for g in groups[1:]):
        return None
    return "".join(groups)


def _normalize_separators(text: str) -> Optional[str]:
    has_comma, has_dot = "," in text, "." in text
    if has_comma and has_dot:
        dec_pos = max(text.rfind(","), text.rfind("."))
        dec_sep = text[dec_pos]
        thou_sep = "." if dec_sep == "," else ","
        int_part = _strip_thousands(text[:dec_pos], thou_sep) if thou_sep in text[:dec_pos] else text[:dec_pos]
        if int_part is None or dec_sep in int_part:
            return None
        return f"{int_part}.{text[dec_pos + 1:]}"
    for sep in (",", "."):
        count = text.count(sep)
        if count > 1:
            return _strip_thousands(text, sep)
        if count == 1:
            return text.replace(sep, ".")
    return text


def parse_amount(value: Any) -> Optional[Decimal]:
    """Parses a money / quantity value; returns None for empty or unparseable input."""
    if isinstance(value, bool) or _is_missing(value):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    if isinstance(value, (int, np.integer)):
        return Decimal(int(value))
    if isinstance(value, (float, np.floating)):
        as_float = float(value)
        return None if math.isinf(as_float) else Decimal(repr(as_float))

    text = str(value).strip()
    if text.lower() in _EMPTY_TOKENS:
        return None

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1]
    text = _CURRENCY_RE.sub("", text.replace("−", "-"))
    text = _GROUPING_CHARS_RE.sub("", text)
    if text.startswith("-"):
        negative, text = not negative, text[1:]

    if not text or re.search(r"[^\d.,]", text):
        return None
    normalized = _normalize_separators(text)
    if normalized is None or not _NUMBER_RE.match(normalized):
        return None
    try:
        amount = Decimal(normalized)
    except InvalidOperation:
        return None
    return -amount if negative else amount


class UnparseableValue(ValueError):
    """A cell has content that cannot be read as an amount / date (never silently replaced)."""


def _is_blank(value: Any) -> bool:
    return _is_missing(value) or (isinstance(value, str) and value.strip().lower() in _EMPTY_TOKENS)


def require_amount(value: Any, default: Optional[Decimal]) -> Optional[Decimal]:
    """Empty cell -> default; unreadable content -> UnparseableValue (the row must be reported)."""
    if _is_blank(value):
        return default
    parsed = parse_amount(value)
    if parsed is None:
        raise UnparseableValue(f"summa o'qilmadi: '{value}'")
    return parsed


def require_date(value: Any, default: Optional[date]) -> Optional[date]:
    """Empty cell -> default; unreadable content -> UnparseableValue (the row must be reported)."""
    if _is_blank(value):
        return default
    parsed = parse_date(value)
    if parsed is None:
        raise UnparseableValue(f"sana o'qilmadi: '{value}'")
    return parsed


def parse_ocr_amount(value: Any) -> Optional[Decimal]:
    """Like parse_amount, but first drops OCR noise characters (letters, stray symbols)."""
    strict = parse_amount(value)
    if strict is not None or value is None or not isinstance(value, str):
        return strict
    return parse_amount(re.sub(r"[^\d.,\s ()\-−]", "", value))


def parse_date(value: Any) -> Optional[date]:
    """Parses a day-first date; returns None for empty or unparseable input."""
    if isinstance(value, bool) or _is_missing(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float, np.integer, np.floating)):
        serial = float(value)
        if _EXCEL_SERIAL_MIN <= serial <= _EXCEL_SERIAL_MAX:
            return _EXCEL_EPOCH + timedelta(days=int(serial))
        return None

    text = str(value).strip()
    if text.lower() in _EMPTY_TOKENS:
        return None
    token = re.split(r"[ T]", text, maxsplit=1)[0]
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue
    return None
