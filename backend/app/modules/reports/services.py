import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.accounting_engine import AccountingEngine
from app.schemas.report import (
    TrialBalanceReport,
    MaterialReport,
    AktSverkaReport
)

class ReportingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_trial_balance(
        self,
        organization_id: uuid.UUID,
        from_date: date,
        to_date: date,
        account_filter: Optional[str] = None
    ) -> TrialBalanceReport:
        """
        Calculates Trial Balance (Oborotno-Saldo Vedomost - OSV)
        Guarantees strict Decimal math and trial balance equality (Sum Debit == Sum Credit).
        """
        return await AccountingEngine.calculate_oborotka(
            session=self.session,
            organization_id=organization_id,
            from_date=from_date,
            to_date=to_date,
            account_filter=account_filter
        )

    async def get_material_report(
        self,
        organization_id: uuid.UUID,
        from_date: date,
        to_date: date,
        item_id: Optional[uuid.UUID] = None
    ) -> MaterialReport:
        """
        Calculates Material Stock Report (Moddiy Hisobot) grouped by item and MXIK/IKPU.
        Calculates Opening balance, Kirim (purchases), Chiqim (sales/usage), and Closing balance.
        """
        return await AccountingEngine.calculate_material_report(
            session=self.session,
            organization_id=organization_id,
            from_date=from_date,
            to_date=to_date,
            item_id=item_id
        )

    async def get_akt_sverka(
        self,
        organization_id: uuid.UUID,
        counterparty_id: uuid.UUID,
        from_date: date,
        to_date: date
    ) -> AktSverkaReport:
        """
        Calculates Mutual Settlement Reconciliation Act (Akt Sverka)
        with running debitor/kreditor balance and chronological transaction journal.
        """
        return await AccountingEngine.calculate_akt_sverka(
            session=self.session,
            organization_id=organization_id,
            counterparty_id=counterparty_id,
            from_date=from_date,
            to_date=to_date
        )
