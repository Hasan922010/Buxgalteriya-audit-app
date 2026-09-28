import base64
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.auth import ensure_org_access, get_current_user
from app.core.rbac import UserRole, require_roles
from app.models.user import User
from app.core.database import get_db
from app.modules.accounting.services import AccountingService
from app.modules.accounting.schemas import TransactionCreate
from app.modules.ocr.image_enhancer import pdf_to_enhanced_images, image_bytes_to_enhanced, cv2_to_png_bytes
from app.modules.ocr.ocr_extractor import OCRExtractor, ExtractedDocument, ExtractedLineItem
from app.modules.ocr.ocr_validator import OCRValidator
from app.modules.ocr.tax_audit_schemas import TaxAuditDocument

router = APIRouter(prefix="/ocr", tags=["Xira Hujjatlar OCR (Degraded Scan Engine)"])

class CommitOCRRequest(BaseModel):
    organization_id: uuid.UUID
    document: ExtractedDocument
    debit_account: Optional[str] = "2900"
    credit_account: Optional[str] = "6000"

@router.post("/upload-and-parse")
async def upload_and_parse_scanned_document(
    file: UploadFile = File(...),
):
    """
    Upload a degraded / blurry scanned PDF or image.
    Applies deskewing, denoising, CLAHE contrast enhancement, and unsharp masking.
    Extracts structured document items and performs mathematical & STIR validation.
    """
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Bo'sh fayl yuklandi.")

    filename = file.filename.lower() if file.filename else "file.png"
    preview_base64 = ""

    # Process PDF or Image
    if filename.endswith(".pdf"):
        enhanced_pages = pdf_to_enhanced_images(contents, dpi=200)
        if not enhanced_pages:
            raise HTTPException(status_code=400, detail="PDF faylidan rasmlarni ajratib bo'lmadi.")
        primary_page = enhanced_pages[0]
        png_bytes = cv2_to_png_bytes(primary_page)
        preview_base64 = base64.b64encode(png_bytes).decode("utf-8")
    else:
        try:
            png_bytes = image_bytes_to_enhanced(contents)
            preview_base64 = base64.b64encode(png_bytes).decode("utf-8")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Rasm faylini qayta ishlashda xatolik: {e}")

    # Extract via OCR Extractor
    extractor = OCRExtractor()
    extracted_doc = await extractor.extract_from_image(png_bytes, filename=file.filename or "doc.png")

    # Validate math, confidence, and STIR
    validation_res = OCRValidator.validate(extracted_doc)

    return {
        "success": True,
        "filename": file.filename,
        "preview_image_base64": f"data:image/png;base64,{preview_base64}",
        "validation": validation_res.to_dict()
    }


@router.post("/commit")
async def commit_ocr_document(
    payload: CommitOCRRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_role: UserRole = Depends(require_roles([UserRole.CHIEF_ACCOUNTANT, UserRole.OPERATOR]))
):
    """
    Commits approved OCR line items into double-entry accounting transactions.
    Creates Counterparty and InventoryItems if they do not exist.
    Protected: CHIEF_ACCOUNTANT or OPERATOR with access to the organization.
    """
    await ensure_org_access(db, current_user, payload.organization_id)
    accounting_service = AccountingService(db)
    doc = payload.document

    # 1. Resolve or create counterparty
    counterparty = None
    if doc.supplier_name:
        counterparty = await accounting_service.get_or_create_counterparty(
            org_id=payload.organization_id,
            name=doc.supplier_name,
            inn=doc.supplier_inn,
            is_supplier=True,
            is_client=False
        )

    # 2. Persist each line item as a transaction
    created_txs = []
    for item in doc.line_items:
        # Resolve item
        inv_item = await accounting_service.get_or_create_inventory_item(
            org_id=payload.organization_id,
            name=item.item_name,
            ikpu_code=item.ikpu_code,
            unit=item.unit
        )

        tx_create = TransactionCreate(
            organization_id=payload.organization_id,
            doc_number=doc.doc_number or "OCR-SCAN",
            doc_date=doc.doc_date,
            doc_type=doc.doc_type or "EHF",
            debit_account=payload.debit_account or "2900",
            credit_account=payload.credit_account or "6000",
            counterparty_id=counterparty.id if counterparty else None,
            item_id=inv_item.id if inv_item else None,
            quantity=item.quantity,
            price=item.price,
            vat_rate=item.vat_rate,
            vat_amount=item.vat_amount,
            total_amount=item.total_amount,
            description=f"OCR orqali kiritildi: {item.item_name} (STIR: {doc.supplier_inn or 'N/A'})"
        )
        tx = await accounting_service.record_transaction(tx_create)
        created_txs.append(str(tx.id))

    return {
        "success": True,
        "committed_count": len(created_txs),
        "transaction_ids": created_txs,
        "message": f"{len(created_txs)} ta tranzaksiya buxgalteriya balansiga muvaffaqiyatli kiritildi."
    }


@router.post("/export-excel")
async def export_ocr_document_to_excel(
    payload: ExtractedDocument
):
    """
    Exports the verified or edited OCR document into an authentic, publication-grade
    Uzbekistan Electronic Invoice (Didox EHF / Hisobvaraq-faktura) in .xlsx Excel format.
    Allows accountants to inspect or verify the document in Excel before committing to the ledger.
    """
    import urllib.parse
    from fastapi.responses import StreamingResponse
    from app.modules.ocr.excel_exporter import OCRExcelExporter

    excel_buffer = OCRExcelExporter.export_document_to_excel(payload)
    safe_doc_num = (payload.doc_number or "tiklangan").replace("/", "_").replace("\\", "_")
    filename = f"faktura_{safe_doc_num}_aslidek.xlsx"
    encoded_filename = urllib.parse.quote(filename)

    return StreamingResponse(
        excel_buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=\"{encoded_filename}\"; filename*=utf-8''{encoded_filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )


@router.post("/tax-audit/parse", response_model=TaxAuditDocument)
async def parse_tax_audit_document(
    file: UploadFile = File(...),
):
    """
    Parses scanned or multi-page tax audit PDF/image document
    ('Киримсиз сотилган товарлар таҳлили'), cleans noise, normalizes numbers,
    verifies mathematical inventory formulas, and calculates punitive tax liabilities.
    """
    from app.modules.ocr.tax_audit_extractor import TaxAuditExtractor
    from app.modules.ocr.image_enhancer import pdf_to_enhanced_images, image_bytes_to_enhanced, cv2_to_png_bytes

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Bo'sh fayl yuklandi.")

    filename = file.filename or "audit.pdf"
    preview_base64 = None
    try:
        if filename.lower().endswith(".pdf") or contents[:4] == b"%PDF":
            enhanced_pages = pdf_to_enhanced_images(contents, dpi=150)
            if enhanced_pages:
                png_bytes = cv2_to_png_bytes(enhanced_pages[0])
                preview_base64 = f"data:image/png;base64,{base64.b64encode(png_bytes).decode('utf-8')}"
        else:
            png_bytes = image_bytes_to_enhanced(contents)
            preview_base64 = f"data:image/png;base64,{base64.b64encode(png_bytes).decode('utf-8')}"
    except Exception:
        pass

    try:
        doc = TaxAuditExtractor.extract_from_pdf_or_image(contents, filename)
        if preview_base64:
            doc.preview_image_base64 = preview_base64
        return doc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Soliq tahlili hujjatini o'qishda xatolik: {e}")


@router.post("/tax-audit/export-excel")
async def export_tax_audit_to_excel(
    payload: TaxAuditDocument
):
    """
    Exports the verified Tax Audit document into a publication-grade, fully styled
    .xlsx Excel workbook with active SUM/AVERAGE formulas, zebra striping,
    red alert discrepancy cells, and punitive tax liability summary.
    """
    import urllib.parse
    import io
    from fastapi.responses import StreamingResponse
    from app.modules.ocr.tax_excel_generator import TaxAuditExcelGenerator

    excel_bytes = TaxAuditExcelGenerator.generate_workbook(payload)
    safe_name = payload.company_name.replace("/", "_").replace("\\", "_")
    filename = f"Soliq_tahlili_{safe_name}_{payload.audit_year}.xlsx"
    encoded_filename = urllib.parse.quote(filename)

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=\"{encoded_filename}\"; filename*=utf-8''{encoded_filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )

