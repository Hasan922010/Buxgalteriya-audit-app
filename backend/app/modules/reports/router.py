import uuid
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.reports.services import ReportingService
from app.modules.reports.excel_export import ExcelExportEngine
from app.modules.reports.pdf_export import PDFExportEngine
from app.schemas.report import TrialBalanceReport, MaterialReport, AktSverkaReport

router = APIRouter(prefix="/reports", tags=["Buxgalteriya Hisobotlari"])

# --- Oborotka (OSV) ---
@router.get("/oborotka", response_model=TrialBalanceReport)
async def get_oborotka(
    organization_id: uuid.UUID = Query(...),
    from_date: date = Query(default=date(2025, 1, 1)),
    to_date: date = Query(default=date.today()),
    account: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    service = ReportingService(db)
    return await service.get_trial_balance(organization_id, from_date, to_date, account)

@router.get("/oborotka/export/excel")
async def export_oborotka_excel(
    organization_id: uuid.UUID = Query(...),
    from_date: date = Query(default=date(2025, 1, 1)),
    to_date: date = Query(default=date.today()),
    account: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    service = ReportingService(db)
    report = await service.get_trial_balance(organization_id, from_date, to_date, account)
    stream = ExcelExportEngine.export_trial_balance(report)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=OSV_{report.organization_name}_{from_date}_{to_date}.xlsx"}
    )

@router.get("/oborotka/export/pdf")
async def export_oborotka_pdf(
    organization_id: uuid.UUID = Query(...),
    from_date: date = Query(default=date(2025, 1, 1)),
    to_date: date = Query(default=date.today()),
    account: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    service = ReportingService(db)
    report = await service.get_trial_balance(organization_id, from_date, to_date, account)
    stream = PDFExportEngine.export_trial_balance(report)
    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=OSV_{report.organization_name}_{from_date}_{to_date}.pdf"}
    )


# --- Material Stock Report (Moddiy Hisobot) ---
@router.get("/materials", response_model=MaterialReport)
async def get_materials(
    organization_id: uuid.UUID = Query(...),
    from_date: date = Query(default=date(2025, 1, 1)),
    to_date: date = Query(default=date.today()),
    item_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    service = ReportingService(db)
    return await service.get_material_report(organization_id, from_date, to_date, item_id)

@router.get("/materials/export/excel")
async def export_materials_excel(
    organization_id: uuid.UUID = Query(...),
    from_date: date = Query(default=date(2025, 1, 1)),
    to_date: date = Query(default=date.today()),
    item_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    service = ReportingService(db)
    report = await service.get_material_report(organization_id, from_date, to_date, item_id)
    stream = ExcelExportEngine.export_material_report(report)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Moddiy_Hisobot_{from_date}_{to_date}.xlsx"}
    )

@router.get("/materials/export/pdf")
async def export_materials_pdf(
    organization_id: uuid.UUID = Query(...),
    from_date: date = Query(default=date(2025, 1, 1)),
    to_date: date = Query(default=date.today()),
    item_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    service = ReportingService(db)
    report = await service.get_material_report(organization_id, from_date, to_date, item_id)
    stream = PDFExportEngine.export_material_report(report)
    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Moddiy_Hisobot_{from_date}_{to_date}.pdf"}
    )


# --- Akt Sverka (Reconciliation Act) ---
@router.get("/akt-sverka", response_model=AktSverkaReport)
async def get_akt_sverka(
    organization_id: uuid.UUID = Query(...),
    counterparty_id: uuid.UUID = Query(...),
    from_date: date = Query(default=date(2025, 1, 1)),
    to_date: date = Query(default=date.today()),
    db: AsyncSession = Depends(get_db)
):
    service = ReportingService(db)
    return await service.get_akt_sverka(organization_id, counterparty_id, from_date, to_date)

@router.get("/akt-sverka/export/excel")
async def export_akt_sverka_excel(
    organization_id: uuid.UUID = Query(...),
    counterparty_id: uuid.UUID = Query(...),
    from_date: date = Query(default=date(2025, 1, 1)),
    to_date: date = Query(default=date.today()),
    db: AsyncSession = Depends(get_db)
):
    service = ReportingService(db)
    report = await service.get_akt_sverka(organization_id, counterparty_id, from_date, to_date)
    stream = ExcelExportEngine.export_akt_sverka(report)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Akt_Sverka_{from_date}_{to_date}.xlsx"}
    )

@router.get("/akt-sverka/export/pdf")
async def export_akt_sverka_pdf(
    organization_id: uuid.UUID = Query(...),
    counterparty_id: uuid.UUID = Query(...),
    from_date: date = Query(default=date(2025, 1, 1)),
    to_date: date = Query(default=date.today()),
    db: AsyncSession = Depends(get_db)
):
    service = ReportingService(db)
    report = await service.get_akt_sverka(organization_id, counterparty_id, from_date, to_date)
    stream = PDFExportEngine.export_akt_sverka(report)
    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Akt_Sverka_{from_date}_{to_date}.pdf"}
    )
