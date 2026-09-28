import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional, Any
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.account import ChartOfAccount, AccountType
from app.models.organization import Organization
from app.models.counterparty import Counterparty
from app.models.inventory import InventoryItem
from app.models.transaction import Transaction
from app.models.audit_log import AuditLog
from app.services.tax_engine import TaxEngine
from app.schemas.report import (
    TrialBalanceReport,
    TrialBalanceItem,
    MaterialReport,
    MaterialReportItem,
    MaterialReportMxikGroup,
    AktSverkaReport,
    AktSverkaItem,
    DashboardKPIs,
)

def round_money(val: Decimal) -> Decimal:
    """Standard financial rounding to 2 decimal places."""
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def round_qty(val: Decimal) -> Decimal:
    """Standard inventory rounding to 3 decimal places."""
    return val.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

class AccountingEngine:
    """
    Deterministic Financial Accounting Engine for Uzbekistan BHMS & Simple Accounting.
    Strictly uses Python Decimal and database aggregations for arithmetic integrity.
    """

    @staticmethod
    async def calculate_oborotka(
        session: AsyncSession,
        organization_id: uuid.UUID,
        from_date: date,
        to_date: date,
        account_filter: Optional[str] = None
    ) -> TrialBalanceReport:
        """
        Calculates Trial Balance (Oborotno-Saldo Vedomost - OSV) for date range [from_date, to_date].
        """
        # 1. Fetch Organization info
        org_res = await session.execute(select(Organization).where(Organization.id == organization_id))
        org = org_res.scalar_one_or_none()
        org_name = org.name if org else "Tashkilot"

        # 2. Fetch Chart of Accounts
        account_query = select(ChartOfAccount).where(ChartOfAccount.is_active == True)
        if account_filter:
            account_query = account_query.where(ChartOfAccount.code.like(f"{account_filter}%"))
        account_query = account_query.order_by(ChartOfAccount.code)
        acc_result = await session.execute(account_query)
        accounts = acc_result.scalars().all()

        # 3. Aggregate transactions prior to from_date (Opening Balances)
        prior_debits_q = select(
            Transaction.debit_account,
            func.coalesce(func.sum(Transaction.total_amount), 0).label("sum_debit")
        ).where(
            Transaction.organization_id == organization_id,
            Transaction.doc_date < from_date,
            Transaction.debit_account != None,
            Transaction.is_reversed == False
        ).group_by(Transaction.debit_account)
        prior_debits = {row[0]: Decimal(str(row[1])) for row in (await session.execute(prior_debits_q)).all()}

        prior_credits_q = select(
            Transaction.credit_account,
            func.coalesce(func.sum(Transaction.total_amount), 0).label("sum_credit")
        ).where(
            Transaction.organization_id == organization_id,
            Transaction.doc_date < from_date,
            Transaction.credit_account != None,
            Transaction.is_reversed == False
        ).group_by(Transaction.credit_account)
        prior_credits = {row[0]: Decimal(str(row[1])) for row in (await session.execute(prior_credits_q)).all()}

        # 4. Aggregate transactions during [from_date, to_date] (Turnovers)
        period_debits_q = select(
            Transaction.debit_account,
            func.coalesce(func.sum(Transaction.total_amount), 0).label("sum_debit")
        ).where(
            Transaction.organization_id == organization_id,
            Transaction.doc_date >= from_date,
            Transaction.doc_date <= to_date,
            Transaction.debit_account != None,
            Transaction.is_reversed == False
        ).group_by(Transaction.debit_account)
        period_debits = {row[0]: Decimal(str(row[1])) for row in (await session.execute(period_debits_q)).all()}

        period_credits_q = select(
            Transaction.credit_account,
            func.coalesce(func.sum(Transaction.total_amount), 0).label("sum_credit")
        ).where(
            Transaction.organization_id == organization_id,
            Transaction.doc_date >= from_date,
            Transaction.doc_date <= to_date,
            Transaction.credit_account != None,
            Transaction.is_reversed == False
        ).group_by(Transaction.credit_account)
        period_credits = {row[0]: Decimal(str(row[1])) for row in (await session.execute(period_credits_q)).all()}

        items: List[TrialBalanceItem] = []
        tot_init_dt = Decimal("0.00")
        tot_init_kt = Decimal("0.00")
        tot_turn_dt = Decimal("0.00")
        tot_turn_kt = Decimal("0.00")
        tot_fin_dt = Decimal("0.00")
        tot_fin_kt = Decimal("0.00")

        # Set of active codes that either have prior balance or turnover
        used_codes = set(prior_debits.keys()) | set(prior_credits.keys()) | set(period_debits.keys()) | set(period_credits.keys())

        for acc in accounts:
            if acc.code not in used_codes and account_filter is None:
                # Include standard root accounts or skip completely inactive ones
                # Include if code ends in 00 or 10 or specifically requested
                if not (acc.code.endswith("00") or acc.code in ["1000", "2900", "4000", "5000", "5110", "6000", "6800", "9000"]):
                    continue

            p_dt = prior_debits.get(acc.code, Decimal("0.00"))
            p_kt = prior_credits.get(acc.code, Decimal("0.00"))
            net_prior = p_dt - p_kt

            is_asset = acc.account_type in [AccountType.ASSET, AccountType.EXPENSE]

            # 1. Opening balance
            if is_asset:
                if net_prior >= 0:
                    init_dt = net_prior
                    init_kt = Decimal("0.00")
                else:
                    init_dt = Decimal("0.00")
                    init_kt = abs(net_prior)
            else:
                if net_prior <= 0:
                    init_kt = abs(net_prior)
                    init_dt = Decimal("0.00")
                else:
                    init_kt = Decimal("0.00")
                    init_dt = net_prior

            # 2. Period turnovers
            turn_dt = period_debits.get(acc.code, Decimal("0.00"))
            turn_kt = period_credits.get(acc.code, Decimal("0.00"))

            # 3. Final balance
            if is_asset:
                net_final = (init_dt - init_kt) + turn_dt - turn_kt
                if net_final >= 0:
                    fin_dt = net_final
                    fin_kt = Decimal("0.00")
                else:
                    fin_dt = Decimal("0.00")
                    fin_kt = abs(net_final)
            else:
                net_final = (init_kt - init_dt) + turn_kt - turn_dt
                if net_final >= 0:
                    fin_kt = net_final
                    fin_dt = Decimal("0.00")
                else:
                    fin_kt = Decimal("0.00")
                    fin_dt = abs(net_final)

            item = TrialBalanceItem(
                account_code=acc.code,
                account_name=acc.name,
                account_type=acc.account_type.value,
                initial_debit=round_money(init_dt),
                initial_credit=round_money(init_kt),
                turnover_debit=round_money(turn_dt),
                turnover_credit=round_money(turn_kt),
                final_debit=round_money(fin_dt),
                final_credit=round_money(fin_kt),
            )
            items.append(item)

            tot_init_dt += item.initial_debit
            tot_init_kt += item.initial_credit
            tot_turn_dt += item.turnover_debit
            tot_turn_kt += item.turnover_credit
            tot_fin_dt += item.final_debit
            tot_fin_kt += item.final_credit

        is_balanced = (abs(tot_turn_dt - tot_turn_kt) < Decimal("0.05"))

        return TrialBalanceReport(
            organization_id=organization_id,
            organization_name=org_name,
            from_date=from_date,
            to_date=to_date,
            items=items,
            total_initial_debit=round_money(tot_init_dt),
            total_initial_credit=round_money(tot_init_kt),
            total_turnover_debit=round_money(tot_turn_dt),
            total_turnover_credit=round_money(tot_turn_kt),
            total_final_debit=round_money(tot_fin_dt),
            total_final_credit=round_money(tot_fin_kt),
            is_balanced=is_balanced
        )

    @staticmethod
    async def calculate_material_report(
        session: AsyncSession,
        organization_id: uuid.UUID,
        from_date: date,
        to_date: date,
        item_id: Optional[uuid.UUID] = None
    ) -> MaterialReport:
        """
        Calculates Material Stock Movement (Moddiy Hisobot) using Weighted Average Cost.
        """
        org_res = await session.execute(select(Organization).where(Organization.id == organization_id))
        org = org_res.scalar_one_or_none()
        org_name = org.name if org else "Tashkilot"

        item_query = select(InventoryItem).where(InventoryItem.organization_id == organization_id)
        if item_id:
            item_query = item_query.where(InventoryItem.id == item_id)
        item_query = item_query.order_by(InventoryItem.name)
        items_db = (await session.execute(item_query)).scalars().all()

        report_items: List[MaterialReportItem] = []
        tot_init_s = Decimal("0.00")
        tot_in_s = Decimal("0.00")
        tot_out_s = Decimal("0.00")
        tot_fin_s = Decimal("0.00")

        for it in items_db:
            # All transactions for this item
            tx_q = select(Transaction).where(
                Transaction.organization_id == organization_id,
                Transaction.item_id == it.id,
                Transaction.is_reversed == False
            ).order_by(Transaction.doc_date, Transaction.id)
            txs = (await session.execute(tx_q)).scalars().all()

            # 1. Opening balance prior to from_date or marked as INITIAL_STOCK
            init_q = Decimal("0.000")
            init_s = Decimal("0.00")
            for t in txs:
                if t.doc_type == "INITIAL_STOCK" or t.doc_date < from_date:
                    qty = Decimal(str(t.quantity or 0))
                    amt = Decimal(str(t.total_amount or 0))
                    # Inflows: debit to stock/materials (1000, 2900) or doc_type in ['INITIAL_STOCK', 'EHF', 'STOCK']
                    if t.doc_type == "INITIAL_STOCK" or t.debit_account in ["1000", "1010", "2900", "2910"] or t.doc_type == "EHF" or amt > 0:
                        init_q += qty
                        init_s += amt
                    else:
                        init_q -= qty
                        init_s -= amt
            if init_q < Decimal("0"):
                init_q = Decimal("0.000")
            if init_s < Decimal("0"):
                init_s = Decimal("0.00")

            # 2. Inflows and Outflows during [from_date, to_date]
            in_q = Decimal("0.000")
            in_s = Decimal("0.00")
            out_q = Decimal("0.000")

            for t in txs:
                if t.doc_type != "INITIAL_STOCK" and from_date <= t.doc_date <= to_date:
                    qty = Decimal(str(t.quantity or 0))
                    amt = Decimal(str(t.total_amount or 0))
                    # Inflows: kirim
                    if t.debit_account in ["1000", "1010", "2900", "2910"] or (t.doc_type == "EHF" and not t.credit_account):
                        in_q += qty
                        in_s += amt
                    # Outflows: chiqim (sotish, ombor chiqimi, kassa realizatsiyasi)
                    elif t.credit_account in ["1000", "1010", "2900", "2910"] or t.doc_type in ["STOCK", "SOLIQ_SALES", "MANUAL"]:
                        out_q += qty

            # 3. Weighted Average Cost calculation: P_bar = (S0 + Sin) / (Q0 + Qin)
            total_avail_q = init_q + in_q
            total_avail_s = init_s + in_s
            if total_avail_q > Decimal("0"):
                avg_price = total_avail_s / total_avail_q
            else:
                avg_price = Decimal("0.00")

            out_s = out_q * avg_price
            fin_q = total_avail_q - out_q
            fin_s = total_avail_s - out_s

            if fin_q < Decimal("0"):
                fin_q = Decimal("0.000")
            if fin_s < Decimal("0"):
                fin_s = Decimal("0.00")

            rep_item = MaterialReportItem(
                item_id=it.id,
                item_name=it.name,
                ikpu_code=it.ikpu_code,
                unit=it.unit or "dona",
                initial_qty=round_qty(init_q),
                initial_sum=round_money(init_s),
                inflow_qty=round_qty(in_q),
                inflow_sum=round_money(in_s),
                outflow_qty=round_qty(out_q),
                outflow_sum=round_money(out_s),
                avg_price=round_money(avg_price),
                final_qty=round_qty(fin_q),
                final_sum=round_money(fin_s)
            )
            report_items.append(rep_item)

            tot_init_s += rep_item.initial_sum
            tot_in_s += rep_item.inflow_sum
            tot_out_s += rep_item.outflow_sum
            tot_fin_s += rep_item.final_sum

        # Group and aggregate strictly by MXIK / IKPU
        mxik_dict: Dict[str, Dict[str, Any]] = {}
        for r_item in report_items:
            code = (r_item.ikpu_code or "").strip()
            display_code = code if code else "NO_IKPU"
            if display_code not in mxik_dict:
                mxik_dict[display_code] = {
                    "ikpu_code": display_code,
                    "ikpu_name": r_item.item_name if display_code != "NO_IKPU" else "MXIK ko'rsatilmagan tovarlar",
                    "items_count": 0,
                    "unit": r_item.unit,
                    "initial_qty": Decimal("0.000"),
                    "initial_sum": Decimal("0.00"),
                    "inflow_qty": Decimal("0.000"),
                    "inflow_sum": Decimal("0.00"),
                    "outflow_qty": Decimal("0.000"),
                    "outflow_sum": Decimal("0.00"),
                    "final_qty": Decimal("0.000"),
                    "final_sum": Decimal("0.00"),
                }
            g = mxik_dict[display_code]
            g["items_count"] += 1
            g["initial_qty"] += r_item.initial_qty
            g["initial_sum"] += r_item.initial_sum
            g["inflow_qty"] += r_item.inflow_qty
            g["inflow_sum"] += r_item.inflow_sum
            g["outflow_qty"] += r_item.outflow_qty
            g["outflow_sum"] += r_item.outflow_sum
            g["final_qty"] += r_item.final_qty
            g["final_sum"] += r_item.final_sum

        mxik_groups: List[MaterialReportMxikGroup] = []
        for g_data in sorted(mxik_dict.values(), key=lambda x: (x["final_sum"], x["inflow_sum"], x["items_count"]), reverse=True):
            mxik_groups.append(MaterialReportMxikGroup(
                ikpu_code=g_data["ikpu_code"],
                ikpu_name=g_data["ikpu_name"],
                items_count=g_data["items_count"],
                unit=g_data["unit"],
                initial_qty=round_qty(g_data["initial_qty"]),
                initial_sum=round_money(g_data["initial_sum"]),
                inflow_qty=round_qty(g_data["inflow_qty"]),
                inflow_sum=round_money(g_data["inflow_sum"]),
                outflow_qty=round_qty(g_data["outflow_qty"]),
                outflow_sum=round_money(g_data["outflow_sum"]),
                final_qty=round_qty(g_data["final_qty"]),
                final_sum=round_money(g_data["final_sum"]),
            ))

        return MaterialReport(
            organization_id=organization_id,
            organization_name=org_name,
            from_date=from_date,
            to_date=to_date,
            items=report_items,
            mxik_groups=mxik_groups,
            total_initial_sum=round_money(tot_init_s),
            total_inflow_sum=round_money(tot_in_s),
            total_outflow_sum=round_money(tot_out_s),
            total_final_sum=round_money(tot_fin_s)
        )

    @staticmethod
    async def calculate_akt_sverka(
        session: AsyncSession,
        organization_id: uuid.UUID,
        counterparty_id: uuid.UUID,
        from_date: date,
        to_date: date
    ) -> AktSverkaReport:
        """
        Calculates side-by-side reconciliation statement (Akt Sverka) with final debt status.
        """
        org_res = await session.execute(select(Organization).where(Organization.id == organization_id))
        org = org_res.scalar_one_or_none()
        org_name = org.name if org else "Tashkilot"

        # Counterparty must belong to the same organization (prevents cross-tenant name/INN disclosure)
        cp_res = await session.execute(select(Counterparty).where(
            Counterparty.id == counterparty_id,
            Counterparty.organization_id == organization_id
        ))
        cp = cp_res.scalar_one_or_none()
        if not cp:
            raise ValueError("Kontragent topilmadi")

        # 1. Calculate opening balance prior to from_date
        prior_q = select(Transaction).where(
            Transaction.organization_id == organization_id,
            Transaction.counterparty_id == counterparty_id,
            Transaction.doc_date < from_date,
            Transaction.is_reversed == False
        )
        prior_txs = (await session.execute(prior_q)).scalars().all()

        initial_debt = Decimal("0.00")
        for t in prior_txs:
            amt = Decimal(str(t.total_amount or 0))
            # Debit: our claims increase (sold goods to client, or prepayments sent to supplier)
            if t.debit_account in ["4000", "4010", "6000", "6010"] or (cp.is_client and t.doc_type == "EHF"):
                initial_debt += amt
            # Credit: cash/bank received or supplier delivered goods
            elif t.credit_account in ["4000", "4010", "6000", "6010"] or (cp.is_supplier and t.doc_type == "EHF"):
                initial_debt -= amt
            else:
                initial_debt += amt

        # 2. Period movements
        period_q = select(Transaction).where(
            Transaction.organization_id == organization_id,
            Transaction.counterparty_id == counterparty_id,
            Transaction.doc_date >= from_date,
            Transaction.doc_date <= to_date,
            Transaction.is_reversed == False
        ).order_by(Transaction.doc_date, Transaction.id)
        period_txs = (await session.execute(period_q)).scalars().all()

        items: List[AktSverkaItem] = []
        tot_debit = Decimal("0.00")
        tot_credit = Decimal("0.00")
        curr_balance = initial_debt

        for t in period_txs:
            amt = Decimal(str(t.total_amount or 0))
            d_val = Decimal("0.00")
            c_val = Decimal("0.00")

            if t.debit_account in ["4000", "4010", "6000", "6010"] or (cp.is_client and t.doc_type == "EHF"):
                d_val = amt
            elif t.credit_account in ["4000", "4010", "6000", "6010"] or (cp.is_supplier and t.doc_type == "EHF"):
                c_val = amt
            else:
                d_val = amt

            curr_balance = curr_balance + d_val - c_val
            tot_debit += d_val
            tot_credit += c_val

            items.append(AktSverkaItem(
                date=t.doc_date,
                doc_number=t.doc_number or "Hujjatsiz",
                doc_type=t.doc_type,
                description=t.description or f"{t.doc_type} bo'yicha operatsiya",
                debit=round_money(d_val),
                credit=round_money(c_val),
                running_balance=round_money(curr_balance)
            ))

        final_debt = initial_debt + tot_debit - tot_credit

        if final_debt > Decimal("0.01"):
            status_uz = f"Korxona foydasiga {final_debt:,.2f} so'm debitorlik qarzi mavjud."
        elif final_debt < Decimal("-0.01"):
            status_uz = f"Korxona yetkazib beruvchidan {abs(final_debt):,.2f} so'm kreditorlik qarziga ega."
        else:
            status_uz = "O'zaro hisob-kitoblar to'liq teng (qarz mavjud emas)."

        return AktSverkaReport(
            organization_id=organization_id,
            organization_name=org_name,
            counterparty_id=cp.id,
            counterparty_name=cp.name,
            counterparty_inn=cp.inn,
            from_date=from_date,
            to_date=to_date,
            initial_debt=round_money(initial_debt),
            total_debit=round_money(tot_debit),
            total_credit=round_money(tot_credit),
            final_debt=round_money(final_debt),
            status_uz=status_uz,
            items=items
        )

    @staticmethod
    async def calculate_kpi_summary(
        session: AsyncSession,
        organization_id: uuid.UUID
    ) -> DashboardKPIs:
        """
        Calculates top-level KPI metrics for the Dashboard.
        """
        org_res = await session.execute(select(Organization).where(Organization.id == organization_id))
        org = org_res.scalar_one_or_none()
        mode_val = org.mode.value if org else "SIMPLE"

        today = date.today()
        first_of_month = date(today.year, today.month, 1)

        # 1. Monthly Kirim (Total receipts / sales in current month)
        inflow_q = select(func.coalesce(func.sum(Transaction.total_amount), 0)).where(
            Transaction.organization_id == organization_id,
            Transaction.doc_date >= first_of_month,
            Transaction.is_reversed == False,
            or_(
                Transaction.debit_account.in_(["5000", "5110", "4000", "1000", "2900"]),
                Transaction.doc_type == "EHF"
            )
        )
        monthly_inflow = Decimal(str((await session.execute(inflow_q)).scalar_one()))

        # 2. Monthly Chiqim (Total expenses / disbursements in current month)
        outflow_q = select(func.coalesce(func.sum(Transaction.total_amount), 0)).where(
            Transaction.organization_id == organization_id,
            Transaction.doc_date >= first_of_month,
            Transaction.is_reversed == False,
            or_(
                Transaction.credit_account.in_(["5000", "5110", "6000"]),
                Transaction.doc_type == "BANK"
            )
        )
        monthly_outflow = Decimal(str((await session.execute(outflow_q)).scalar_one()))

        # 3. Net Cash / Bank Balance (Account 5000 + 5110)
        cash_dt = select(func.coalesce(func.sum(Transaction.total_amount), 0)).where(
            Transaction.organization_id == organization_id,
            Transaction.debit_account.in_(["5000", "5110"]),
            Transaction.is_reversed == False
        )
        cash_kt = select(func.coalesce(func.sum(Transaction.total_amount), 0)).where(
            Transaction.organization_id == organization_id,
            Transaction.credit_account.in_(["5000", "5110"]),
            Transaction.is_reversed == False
        )
        c_dt = Decimal(str((await session.execute(cash_dt)).scalar_one()))
        c_kt = Decimal(str((await session.execute(cash_kt)).scalar_one()))
        net_cash = c_dt - c_kt

        # 4. Inventory Valuation (Account 1000 + 2900)
        inv_dt = select(func.coalesce(func.sum(Transaction.total_amount), 0)).where(
            Transaction.organization_id == organization_id,
            Transaction.debit_account.in_(["1000", "2900", "1010", "2910"]),
            Transaction.is_reversed == False
        )
        inv_kt = select(func.coalesce(func.sum(Transaction.total_amount), 0)).where(
            Transaction.organization_id == organization_id,
            Transaction.credit_account.in_(["1000", "2900", "1010", "2910"]),
            Transaction.is_reversed == False
        )
        i_dt = Decimal(str((await session.execute(inv_dt)).scalar_one()))
        i_kt = Decimal(str((await session.execute(inv_kt)).scalar_one()))
        inventory_val = max(Decimal("0.00"), i_dt - i_kt)

        # 5. Receivables (Account 4000) & Payables (Account 6000)
        rec_dt = select(func.coalesce(func.sum(Transaction.total_amount), 0)).where(
            Transaction.organization_id == organization_id,
            Transaction.debit_account.in_(["4000", "4010"]),
            Transaction.is_reversed == False
        )
        rec_kt = select(func.coalesce(func.sum(Transaction.total_amount), 0)).where(
            Transaction.organization_id == organization_id,
            Transaction.credit_account.in_(["4000", "4010"]),
            Transaction.is_reversed == False
        )
        receivables = max(Decimal("0.00"), Decimal(str((await session.execute(rec_dt)).scalar_one())) - Decimal(str((await session.execute(rec_kt)).scalar_one())))

        pay_kt = select(func.coalesce(func.sum(Transaction.total_amount), 0)).where(
            Transaction.organization_id == organization_id,
            Transaction.credit_account.in_(["6000", "6010"]),
            Transaction.is_reversed == False
        )
        pay_dt = select(func.coalesce(func.sum(Transaction.total_amount), 0)).where(
            Transaction.organization_id == organization_id,
            Transaction.debit_account.in_(["6000", "6010"]),
            Transaction.is_reversed == False
        )
        payables = max(Decimal("0.00"), Decimal(str((await session.execute(pay_kt)).scalar_one())) - Decimal(str((await session.execute(pay_dt)).scalar_one())))

        return DashboardKPIs(
            monthly_inflow=round_money(monthly_inflow),
            monthly_outflow=round_money(monthly_outflow),
            net_cash_balance=round_money(net_cash),
            inventory_valuation=round_money(inventory_val),
            total_receivables=round_money(receivables),
            total_payables=round_money(payables),
            mode=mode_val
        )

    @staticmethod
    async def storno_transaction(
        session: AsyncSession,
        organization_id: uuid.UUID,
        transaction_id: uuid.UUID,
        reason: str,
        performed_by: str = "Bosh Buxgalter"
    ) -> Dict[str, Any]:
        """
        Executes an immutable Red Storno (Reversal) on a financial transaction.
        Strictly checks Period Locking: Cannot reverse transactions within a locked period.
        """
        org_res = await session.execute(select(Organization).where(Organization.id == organization_id))
        org = org_res.scalar_one_or_none()
        if not org:
            raise ValueError("Tashkilot topilmadi")

        tx_res = await session.execute(select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.organization_id == organization_id
        ))
        tx = tx_res.scalar_one_or_none()
        if not tx:
            raise ValueError("Tranzaksiya topilmadi")

        if tx.is_reversed:
            raise ValueError("Ushbu tranzaksiya allaqachon storno qilingan!")

        # Check Period Lock
        if org.locked_until_date and tx.doc_date <= org.locked_until_date:
            raise ValueError(
                f"Davr qulflangan: {tx.doc_date} sanasidagi tranzaksiya yopilgan buxgalteriya davriga "
                f"({org.locked_until_date} gacha) tegishli. Storno qilish taqiqlangan!"
            )

        reversal_id = uuid.uuid4()
        tx.is_reversed = True
        tx.reversal_ref_id = reversal_id
        tx.reversal_reason = reason

        # Create Storno reversal record
        storno_tx = Transaction(
            id=reversal_id,
            organization_id=organization_id,
            doc_number=f"STORNO-{tx.doc_number or 'DOC'}",
            doc_date=date.today(),
            doc_type=tx.doc_type,
            debit_account=tx.debit_account,
            credit_account=tx.credit_account,
            counterparty_id=tx.counterparty_id,
            item_id=tx.item_id,
            quantity=-tx.quantity if tx.quantity else Decimal(0),
            price=tx.price,
            total_amount=-tx.total_amount,
            vat_rate=tx.vat_rate,
            vat_amount=-tx.vat_amount if tx.vat_amount else Decimal(0),
            description=f"STORNO: {reason} (Asl: {tx.doc_number})",
            is_reversed=True,
            reversal_ref_id=tx.id,
            reversal_reason=reason
        )
        session.add(storno_tx)

        # Audit Log
        log = AuditLog(
            organization_id=organization_id,
            action="STORNO_TRANSACTION",
            entity_type="transaction",
            entity_id=str(tx.id),
            performed_by=performed_by,
            details=f"Tranzaksiya {tx.doc_number} ({tx.total_amount} UZS) storno qilindi. Sabab: {reason}"
        )
        session.add(log)
        await session.commit()

        return {
            "status": "success",
            "message": f"Tranzaksiya muvaffaqiyatli storno qilindi. Storno raqami: {storno_tx.doc_number}",
            "original_transaction_id": str(tx.id),
            "storno_transaction_id": str(reversal_id)
        }
