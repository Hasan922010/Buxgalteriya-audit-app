from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any

def round_money(val: Decimal) -> Decimal:
    """Standard financial rounding to 2 decimal places."""
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

class TaxRateRule:
    def __init__(self, rate: Decimal, start_date: date, end_date: Optional[date], name: str, legal_basis: str):
        self.rate = rate
        self.start_date = start_date
        self.end_date = end_date
        self.name = name
        self.legal_basis = legal_basis

    def is_active(self, target_date: date) -> bool:
        if target_date < self.start_date:
            return False
        if self.end_date and target_date > self.end_date:
            return False
        return True

# Historical and current Uzbekistan VAT (Qo'shilgan qiymat solig'i - QQS) matrix
UZBEKISTAN_VAT_RULES: List[TaxRateRule] = [
    TaxRateRule(
        rate=Decimal("0.15"),
        start_date=date(2019, 10, 1),
        end_date=date(2022, 12, 31),
        name="QQS 15% (Eski stavka)",
        legal_basis="O'zbekiston Respublikasi Soliq Kodeksi (2019-2022)"
    ),
    TaxRateRule(
        rate=Decimal("0.12"),
        start_date=date(2023, 1, 1),
        end_date=None,
        name="QQS 12% (Amaldagi stavka)",
        legal_basis="O'zbekiston Respublikasi Soliq Kodeksi 258-moddasi (2023-yildan)"
    ),
]

class TaxEngine:
    """
    Versioned Tax Policy Engine for Uzbekistan.
    Determines correct tax rates and VAT calculations dynamically based on transaction effective dates.
    """

    @staticmethod
    def get_vat_rate(for_date: date) -> Decimal:
        """
        Retrieves the exact legal VAT rate applicable on the specified date.
        Defaults to 0.12 if outside historical bounds.
        """
        for rule in UZBEKISTAN_VAT_RULES:
            if rule.is_active(for_date):
                return rule.rate
        return Decimal("0.12")

    @staticmethod
    def get_rule_info(for_date: date) -> Dict[str, Any]:
        """Returns details of the active tax rule for the date."""
        for rule in UZBEKISTAN_VAT_RULES:
            if rule.is_active(for_date):
                return {
                    "rate": float(rule.rate),
                    "percentage": f"{int(rule.rate * 100)}%",
                    "name": rule.name,
                    "legal_basis": rule.legal_basis,
                    "start_date": rule.start_date.isoformat(),
                    "end_date": rule.end_date.isoformat() if rule.end_date else None,
                }
        return {
            "rate": 0.12,
            "percentage": "12%",
            "name": "QQS 12% (Standart)",
            "legal_basis": "Soliq Kodeksi",
            "start_date": "2023-01-01",
            "end_date": None,
        }

    @staticmethod
    def calculate_vat_from_total(
        total_amount: Decimal,
        for_date: date,
        is_vat_payer: bool = True
    ) -> Dict[str, Decimal]:
        """
        Given the total amount inclusive of VAT, extracts the exact VAT amount and net taxable base.
        Formula:
            VAT Amount = Total - (Total / (1 + Rate))
            Base Amount = Total - VAT Amount
        """
        if not is_vat_payer:
            return {
                "vat_rate": Decimal("0.00"),
                "vat_amount": Decimal("0.00"),
                "base_amount": round_money(total_amount),
                "total_amount": round_money(total_amount),
            }

        rate = TaxEngine.get_vat_rate(for_date)
        divider = Decimal("1.00") + rate
        base = round_money(total_amount / divider)
        vat = round_money(total_amount - base)

        return {
            "vat_rate": rate,
            "vat_amount": vat,
            "base_amount": base,
            "total_amount": round_money(total_amount),
        }

    @staticmethod
    def calculate_vat_from_base(
        base_amount: Decimal,
        for_date: date,
        is_vat_payer: bool = True
    ) -> Dict[str, Decimal]:
        """
        Given base taxable amount, adds VAT.
        """
        if not is_vat_payer:
            return {
                "vat_rate": Decimal("0.00"),
                "vat_amount": Decimal("0.00"),
                "base_amount": round_money(base_amount),
                "total_amount": round_money(base_amount),
            }

        rate = TaxEngine.get_vat_rate(for_date)
        vat = round_money(base_amount * rate)
        total = round_money(base_amount + vat)

        return {
            "vat_rate": rate,
            "vat_amount": vat,
            "base_amount": round_money(base_amount),
            "total_amount": total,
        }

    @staticmethod
    def get_all_rules() -> List[Dict[str, Any]]:
        """Returns all configured historical and active tax rules."""
        return [
            {
                "rate": float(r.rate),
                "percentage": f"{int(r.rate * 100)}%",
                "name": r.name,
                "legal_basis": r.legal_basis,
                "start_date": r.start_date.isoformat(),
                "end_date": r.end_date.isoformat() if r.end_date else None,
            }
            for r in UZBEKISTAN_VAT_RULES
        ]
