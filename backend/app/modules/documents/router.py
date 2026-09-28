import os
import uuid
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import ensure_org_access, get_current_user
from app.core.rbac import UserRole, require_roles
from app.models.user import User
from app.core.database import get_db
from app.core.storage import build_upload_filename, ensure_storage_dirs, resolve_upload_path
from app.modules.documents.schemas import ParsePreviewResponse, CommitParsedDocumentsRequest
from app.modules.documents.services import DocumentIngestionService

router = APIRouter(prefix="/documents", tags=["Hujjatlar va ETL Ingestion"])

ensure_storage_dirs()

@router.post("/parse-preview", response_model=ParsePreviewResponse)
async def parse_document_preview(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Interactive Ingestion Pipeline:
    Uploads document (XLSX, XLS, CSV), detects whether it is Didox, Soliq.uz, or Bank-client,
    extracts column mappings, and returns candidate structured records for user confirmation.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Fayl nomi ko'rsatilmadi.")

    file_path = resolve_upload_path(build_upload_filename(file.filename))

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Faylni saqlashda xatolik: {e}")

    service = DocumentIngestionService(db)
    try:
        preview = service.inspect_and_preview(file_path, file.filename)
        return preview
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Hujjatni tahlil qilishda xatolik: {str(e)}")


@router.post("/commit-parsed")
async def commit_parsed_documents(
    payload: CommitParsedDocumentsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_role: UserRole = Depends(require_roles([UserRole.CHIEF_ACCOUNTANT, UserRole.OPERATOR]))
):
    """
    Commits reviewed and approved document records into the double-entry accounting ledger.
    Protected: CHIEF_ACCOUNTANT or OPERATOR with access to the organization.
    """
    await ensure_org_access(db, current_user, payload.organization_id)
    service = DocumentIngestionService(db)
    result = await service.commit_parsed_records(
        org_id=payload.organization_id,
        records=payload.records,
        operation_type=payload.operation_type or "INFLOW",
        default_debit=payload.default_debit_account,
        default_credit=payload.default_credit_account
    )
    return result
