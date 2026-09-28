import uuid
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import require_org_query_access
from app.core.database import get_db
from app.models.organization import Organization
from app.models.counterparty import Counterparty
from app.schemas.report import (
    TrialBalanceReport,
    MaterialReport,
    AktSverkaReport,
    DashboardKPIs
)
from app.services.accounting_engine import AccountingEngine
from app.services.export_engine import ExportEngine

# Every report takes ?organization_id=; the caller must have access to that organization
router = APIRouter(dependencies=[Depends(require_org_query_access)])

@router.get("/oborotka", response_model=TrialBalanceReport)
async def get_oborotka(
    organization_id: uuid.UUID = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    account_filter: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns complete Trial Balance (Oborotno-Saldo Vedomost - OSV) structure.
    """
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="Boshlanish sanasi tugash sanasidan katta bo'lishi mumkin emas")

    report = await AccountingEngine.calculate_oborotka(
        session=db,
        organization_id=organization_id,
        from_date=from_date,
        to_date=to_date,
        account_filter=account_filter
    )
    return report

@router.get("/material-report", response_model=MaterialReport)
async def get_material_report(
    organization_id: uuid.UUID = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    item_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns Opening Stock, Inflow, Outflow, Closing Stock by item and total.
    """
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="Boshlanish sanasi tugash sanasidan katta bo'lishi mumkin emas")

    report = await AccountingEngine.calculate_material_report(
        session=db,
        organization_id=organization_id,
        from_date=from_date,
        to_date=to_date,
        item_id=item_id
    )
    return report

@router.get("/akt-sverka", response_model=AktSverkaReport)
async def get_akt_sverka(
    organization_id: uuid.UUID = Query(...),
    counterparty_id: uuid.UUID = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns side-by-side reconciliation statement with final debt status.
    """
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="Boshlanish sanasi tugash sanasidan katta bo'lishi mumkin emas")

    try:
        report = await AccountingEngine.calculate_akt_sverka(
            session=db,
            organization_id=organization_id,
            counterparty_id=counterparty_id,
            from_date=from_date,
            to_date=to_date
        )
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/dashboard", response_model=DashboardKPIs)
async def get_dashboard_kpis(
    organization_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns top-level KPIs for dashboard metrics cards.
    """
    return await AccountingEngine.calculate_kpi_summary(session=db, organization_id=organization_id)

@router.api_route("/export/{format}", methods=["GET", "POST"])
async def export_report(
    format: str,
    report_type: str = Query(..., description="'oborotka' or 'material' or 'sverka'"),
    organization_id: uuid.UUID = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    counterparty_id: Optional[uuid.UUID] = Query(None),
    mode: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Streams styled Excel (.xlsx) or PDF report.
    """
    fmt = format.lower()
    if fmt not in ["xlsx", "excel", "pdf"]:
        raise HTTPException(status_code=400, detail="Faqat 'xlsx' yoki 'pdf' format qo'llab-quvvatlanadi")

    if report_type == "oborotka":
        rep = await AccountingEngine.calculate_oborotka(db, organization_id, from_date, to_date)
        if fmt in ["xlsx", "excel"]:
            stream = ExportEngine.export_oborotka_excel(rep)
            return StreamingResponse(
                stream,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=OSV_{from_date}_{to_date}.xlsx"}
            )
        else:
            headers = ["Schot", "Schot nomi", "Bosh Dt", "Bosh Kt", "Oborot Dt", "Oborot Kt", "Oxirgi Dt", "Oxirgi Kt"]
            rows = [
                [it.account_code, it.account_name, str(it.initial_debit), str(it.initial_credit), str(it.turnover_debit), str(it.turnover_credit), str(it.final_debit), str(it.final_credit)]
                for it in rep.items
            ]
            stream = ExportEngine.export_pdf(f"Aylanma Qoldiq Vedomosti ({from_date} - {to_date})", headers, rows)
            return StreamingResponse(stream, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=OSV.pdf"})

    elif report_type == "material":
        rep = await AccountingEngine.calculate_material_report(db, organization_id, from_date, to_date)
        if fmt in ["xlsx", "excel"]:
            stream = ExportEngine.export_material_excel(rep)
            return StreamingResponse(
                stream,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=Moddiy_Hisobot_{from_date}_{to_date}.xlsx"}
            )
        else:
            if mode == "mxik":
                headers = [
                    "MXIK Kodi", "Mahsulotlar Toifasi", "Birlik", "Turlar soni",
                    "Bosh Qoldiq (soni / so'm)", "Kirim (soni / so'm)", "Chiqim (soni / so'm)", "Yakuniy Qoldiq (soni / so'm)"
                ]
                rows = [
                    [
                        g.ikpu_code,
                        (g.ikpu_name or "")[:30],
                        g.unit or "dona",
                        str(g.items_count),
                        f"{float(g.initial_qty):,.1f} ({float(g.initial_sum):,.0f})",
                        f"{float(g.inflow_qty):,.1f} ({float(g.inflow_sum):,.0f})",
                        f"{float(g.outflow_qty):,.1f} ({float(g.outflow_sum):,.0f})",
                        f"{float(g.final_qty):,.1f} ({float(g.final_sum):,.0f})"
                    ]
                    for g in rep.mxik_groups
                ]
                stream = ExportEngine.export_pdf(f"MXIK bo'yicha Tovar Jamlamasi ({from_date} - {to_date})", headers, rows)
                return StreamingResponse(stream, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=MXIK_Jamlama.pdf"})

            headers = ["Mahsulot nomi", "Birlik", "Bosh Qoldiq", "Kirim", "Chiqim", "O'rtacha narx", "Oxirgi Qoldiq"]
            rows = [
                [it.item_name, it.unit, f"{it.initial_qty} ({it.initial_sum})", f"{it.inflow_qty} ({it.inflow_sum})", f"{it.outflow_qty} ({it.outflow_sum})", str(it.avg_price), f"{it.final_qty} ({it.final_sum})"]
                for it in rep.items
            ]
            stream = ExportEngine.export_pdf(f"Moddiy Hisobot ({from_date} - {to_date})", headers, rows)
            return StreamingResponse(stream, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=Moddiy_Hisobot.pdf"})

    elif report_type == "sverka":
        if not counterparty_id:
            raise HTTPException(status_code=400, detail="Akt sverka uchun counterparty_id zarur")
        rep = await AccountingEngine.calculate_akt_sverka(db, organization_id, counterparty_id, from_date, to_date)
        headers = ["Sana", "Hujjat #", "Amal turi", "Debet", "Kredit", "Qoldiq"]
        rows = [
            [str(it.date), it.doc_number, it.description, str(it.debit), str(it.credit), str(it.running_balance)]
            for it in rep.items
        ]
        stream = ExportEngine.export_pdf(f"Akt Sverka: {rep.counterparty_name} ({from_date} - {to_date})", headers, rows)
        return StreamingResponse(stream, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=Akt_Sverka.pdf"})

    raise HTTPException(status_code=400, detail="Noma'lum hisobot turi")
