import os
import re
import uuid
import shutil
from datetime import date
from decimal import Decimal
from typing import List, Dict, Any, Optional
import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db, AsyncSessionLocal
from app.core.auth import ensure_org_access, get_current_user
from app.core.rbac import UserRole, require_roles, ROLE_LABELS
from app.models.user import User
from app.core.storage import InvalidStoragePath, build_upload_filename, ensure_storage_dirs, resolve_upload_path
from app.modules.accounting.item_disambiguator import ItemDisambiguator
from app.modules.ocr.pdf_table_extractor import PDFTableExtractor
from app.modules.ocr.excel_exporter import OCRExcelExporter
from app.services.task_manager import task_manager, TaskInfo
from app.models.organization import Organization
from app.models.counterparty import Counterparty
from app.models.inventory import InventoryItem
from app.models.transaction import Transaction
from app.models.audit_log import AuditLog
from app.services.tax_engine import TaxEngine
from app.schemas.document import (
    UploadResponse,
    DetectedFormat,
    PreviewMappingResponse,
    ColumnMapping,
    CommitMappingRequest,
    CommitResponse
)
from app.services.parsers.didox_parser import DidoxParser
from app.services.parsers.bank_parser import BankParser
from app.services.parsers.soliq_parser import SoliqParser
from app.services.parsers.material_parser import MaterialParser
from app.services.parsers.smart_excel_mapper import SmartExcelMapper
from app.services.parsers.base import ParsedDocumentRecord
from app.services.parsers.normalize import UnparseableValue, parse_amount, parse_date, require_amount, require_date
from app.services.import_guard import commit_or_conflict, ensure_not_duplicate, file_sha256, record_import

router = APIRouter()

ensure_storage_dirs()


def _existing_upload_path(file_id: str) -> str:
    """Resolves a client-supplied upload id; 400 on traversal, 404 if missing."""
    try:
        file_path = resolve_upload_path(file_id)
    except InvalidStoragePath as e:
        raise HTTPException(status_code=400, detail=f"Noto'g'ri fayl identifikatori: {e}")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Yuklangan fayl topilmadi yoki muddati o'tgan")
    return file_path

@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
):
    """
    Accepts .xlsx, .xls, .pdf, .csv, .txt files.
    Saves file temporarily, auto-detects source type (Didox, Bank, Soliq, Material Report, Generic).
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in [".xlsx", ".xls", ".csv", ".txt", ".pdf"]:
        raise HTTPException(status_code=400, detail="Faqat .xlsx, .xls, .csv, .txt yoki .pdf fayllar qabul qilinadi")

    dest_path = resolve_upload_path(build_upload_filename(file.filename))
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    detected_format_str = "GENERIC_EXCEL"
    confidence = 0.5
    headers: List[str] = []
    sample_rows: List[Dict[str, Any]] = []
    total_rows = 0

    try:
        if ext in [".xlsx", ".xls", ".csv", ".pdf"]:
            df, header_row, headers = SmartExcelMapper.find_header_row_and_df(dest_path)
            total_rows = len(df)
            sample_rows = df.head(5).fillna("").astype(str).to_dict(orient="records")

            # Detect format
            is_didox, d_conf = DidoxParser.detect_format(df, headers)
            if is_didox:
                detected_format_str = "DIDOX_EHF"
                confidence = d_conf
            else:
                is_bank, b_conf = BankParser.detect_format(df, headers)
                if is_bank:
                    detected_format_str = "BANK_STATEMENT"
                    confidence = b_conf
                else:
                    is_material, m_conf = MaterialParser.detect_format(df, headers)
                    if is_material:
                        detected_format_str = "MATERIAL_REPORT"
                        confidence = m_conf
                    else:
                        is_soliq, s_conf = SoliqParser.detect_format(df, headers)
                        if is_soliq:
                            detected_format_str = "SOLIQ_REGISTRY"
                            confidence = s_conf
                        else:
                            detected_format_str = "GENERIC_EXCEL"
                            confidence = 0.8 if ext == ".pdf" else 0.7
        elif ext == ".txt":
            detected_format_str = "BANK_STATEMENT"
            confidence = 0.95
    except Exception as e:
        detected_format_str = "UNKNOWN"

    return UploadResponse(
        file_id=os.path.basename(dest_path),
        filename=file.filename,
        detected_format=DetectedFormat(
            format_type=detected_format_str,
            confidence=confidence,
            detected_headers=headers,
            total_rows=total_rows,
            sample_rows=sample_rows
        ),
        message="Hujjat muvaffaqiyatli yuklandi va formati aniqlandi."
    )

@router.post("/preview-mapping", response_model=PreviewMappingResponse)
async def preview_mapping(
    file_id: str = Form(...),
):
    """
    Returns parsed headers, proposed column mappings (AI or heuristic), and first sample rows.
    """
    file_path = _existing_upload_path(file_id)

    df, _, headers = SmartExcelMapper.find_header_row_and_df(file_path)
    sample_rows = df.head(5).fillna("").astype(str).to_dict(orient="records")

    # Smart auto-detection mapping
    mapping = await SmartExcelMapper.auto_detect_mapping(headers, sample_rows)

    return PreviewMappingResponse(
        file_id=file_id,
        detected_format="GENERIC_EXCEL",
        available_columns=headers,
        proposed_mapping=mapping,
        sample_preview=sample_rows
    )

async def execute_document_import(
    db: AsyncSession,
    request: CommitMappingRequest,
    performed_by: str = "Bosh Buxgalter",
    task_info: Optional[TaskInfo] = None
) -> CommitResponse:
    file_path = _existing_upload_path(request.file_id)

    # Verify organization
    org_res = await db.execute(select(Organization).where(Organization.id == request.organization_id))
    org = org_res.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Tashkilot topilmadi")

    digest = file_sha256(file_path)
    await ensure_not_duplicate(db, org.id, digest, request.allow_duplicate)

    if task_info:
        task_info.update_progress(10, "Fayl o'qilmoqda va format tahlil qilinmoqda...")

    records: List[ParsedDocumentRecord] = []
    parse_errors: List[str] = []

    try:
        op_type = getattr(request, "operation_type", None) or "INFLOW"

        if request.format_type == "DIDOX_EHF":
            parser = DidoxParser()
            records = parser.parse_file(file_path)
            parse_errors.extend(parser.row_errors)
            if op_type == "INITIAL_BALANCE":
                for r in records:
                    r.doc_type = "INITIAL_BALANCE"
                    r.debit_account = request.default_debit_account or "2900"
                    r.credit_account = request.default_credit_account or "8300"
                    r.vat_rate = Decimal("0")
                    r.vat_amount = Decimal("0")
            elif op_type == "OUTFLOW":
                for r in records:
                    r.doc_type = "OUTFLOW"
                    r.debit_account = request.default_debit_account or ("4000" if org.mode == "BHMS" else "5000")
                    r.credit_account = request.default_credit_account or "9000"
        elif request.format_type == "BANK_STATEMENT":
            parser = BankParser()
            records = parser.parse_file(file_path)
            parse_errors.extend(parser.row_errors)
        elif request.format_type == "SOLIQ_REGISTRY" and not request.mapping:
            parser = SoliqParser()
            records = parser.parse_file(file_path)
            parse_errors.extend(parser.row_errors)
            if op_type == "INITIAL_BALANCE":
                for r in records:
                    r.doc_type = "INITIAL_BALANCE"
                    r.debit_account = request.default_debit_account or "2900"
                    r.credit_account = request.default_credit_account or "8300"
                    r.vat_rate = Decimal("0")
                    r.vat_amount = Decimal("0")
        else:
            # Custom or user-adjusted mapping commit
            df, _, headers = SmartExcelMapper.find_header_row_and_df(file_path)
            m = request.mapping or SmartExcelMapper._heuristic_mapping(headers)
            
            # Default debit/credit logic based on operation_type / doc_type
            if op_type == "INITIAL_BALANCE":
                default_deb = request.default_debit_account or "2900"
                default_crd = request.default_credit_account or "8300"
            elif op_type == "OUTFLOW":
                default_deb = request.default_debit_account or ("4000" if org.mode == "BHMS" else "5000")
                default_crd = request.default_credit_account or "9000"
            else:
                is_sales = request.doc_type in ["SOLIQ_SALES", "KASSA", "REALIZATION"]
                default_deb = request.default_debit_account or ("5000" if is_sales else ("2900" if request.doc_type == "EHF" else "5110"))
                default_crd = request.default_credit_account or ("9000" if is_sales else ("6000" if request.doc_type == "EHF" else "4000"))

            for idx, row in df.iterrows():
                try:
                    doc_num = str(idx + 1)
                    if m.doc_num_col and pd.notna(row.get(m.doc_num_col)):
                        raw_num = str(row[m.doc_num_col]).strip()
                        if raw_num.endswith(".0"):
                            raw_num = raw_num[:-2]
                        if raw_num and raw_num != "nan":
                            doc_num = raw_num

                    doc_d = (require_date(row.get(m.date_col), date.today()) if m.date_col else date.today())

                    tot = Decimal("0")
                    for sum_col in (m.total_col, m.inflow_sum_col, m.initial_sum_col, m.outflow_sum_col):
                        if sum_col and pd.notna(row.get(sum_col)):
                            tot = require_amount(row.get(sum_col), Decimal("0"))
                            break

                    # Barcode / GTIN
                    barcode = str(row.get(m.barcode_col, "")).strip() if m.barcode_col and pd.notna(row.get(m.barcode_col)) else None
                    if barcode and barcode.endswith(".0"):
                        barcode = barcode[:-2]

                    # IKPU / MXIK
                    ikpu = str(row.get(m.ikpu_col, "")).strip() if m.ikpu_col and pd.notna(row.get(m.ikpu_col)) else None
                    if ikpu and ikpu.endswith(".0"):
                        ikpu = ikpu[:-2]

                    # Unit (O'lchov birligi)
                    unit_val = "dona"
                    if m.unit_col and pd.notna(row.get(m.unit_col)):
                        u_clean = str(row.get(m.unit_col)).strip()
                        if u_clean and u_clean.lower() != "nan":
                            unit_val = u_clean

                    # Quantity & Price
                    qty = Decimal("1")
                    qty_src = m.qty_col or m.inflow_qty_col or m.initial_qty_col or m.outflow_qty_col
                    if qty_src:
                        qty = require_amount(row.get(qty_src), Decimal("1"))

                    price = (require_amount(row.get(m.price_col), Decimal("0")) if m.price_col else Decimal("0"))

                    # Calculate missing total or price
                    if tot <= Decimal("0") and price > Decimal("0") and qty > Decimal("0"):
                        tot = qty * price
                    elif price <= Decimal("0") and tot > Decimal("0") and qty > Decimal("0"):
                        price = tot / qty

                    if tot <= 0 and qty <= 0:
                        continue

                    # Determine doc_type and counterparty
                    if op_type == "INITIAL_BALANCE":
                        final_doc_type = "INITIAL_BALANCE"
                        cp_name = str(row.get(m.counterparty_col, "")).strip() if m.counterparty_col and pd.notna(row.get(m.counterparty_col)) else "Ta'sischi (Boshlang'ich qoldiq)"
                    elif op_type == "OUTFLOW":
                        final_doc_type = request.doc_type or "OUTFLOW"
                        cp_name = str(row.get(m.counterparty_col, "")).strip() if m.counterparty_col and pd.notna(row.get(m.counterparty_col)) else "Xaridor / Aholi"
                    else:
                        final_doc_type = request.doc_type or ("SOLIQ_SALES" if is_sales else ("INITIAL_STOCK" if m.initial_qty_col else "EHF"))
                        cp_name = str(row.get(m.counterparty_col, "")).strip() if m.counterparty_col and pd.notna(row.get(m.counterparty_col)) else ("Aholi" if is_sales else "Yetkazib beruvchi")

                    # Main Transaction
                    records.append(ParsedDocumentRecord(
                        doc_number=doc_num,
                        doc_date=doc_d,
                        doc_type=final_doc_type,
                        counterparty_name=cp_name,
                        counterparty_inn=str(row.get(m.counterparty_inn_col, "")) if m.counterparty_inn_col and pd.notna(row.get(m.counterparty_inn_col)) else None,
                        item_name=str(row.get(m.item_name_col, "")).strip() if m.item_name_col and pd.notna(row.get(m.item_name_col)) else None,
                        ikpu_code=ikpu,
                        package_code=barcode,
                        unit=unit_val,
                        quantity=qty,
                        price=price,
                        total_amount=tot,
                        debit_account=default_deb,
                        credit_account=default_crd,
                        description=f"{final_doc_type}: {str(row.get(m.item_name_col, ''))[:40]}",
                        raw_payload={str(k): str(v) for k, v in row.items() if pd.notna(v)}
                    ))

                    # If there is a return amount
                    if m.return_sum_col:
                        ret_sum = require_amount(row.get(m.return_sum_col), Decimal("0"))
                        if ret_sum > 0:
                            ret_qty = (require_amount(row.get(m.return_qty_col), Decimal("1")) if m.return_qty_col else Decimal("1"))
                            records.append(ParsedDocumentRecord(
                                doc_number=f"RET-{doc_num}",
                                doc_date=doc_d,
                                doc_type="RETURN",
                                counterparty_name="Aholi (Qaytarish)",
                                item_name=str(row.get(m.item_name_col, "")).strip() if m.item_name_col and pd.notna(row.get(m.item_name_col)) else None,
                                ikpu_code=ikpu,
                                package_code=barcode,
                                quantity=ret_qty,
                                price=ret_sum / ret_qty if ret_qty > 0 else ret_sum,
                                total_amount=ret_sum,
                                debit_account="9000",
                                credit_account="5000",
                                description=f"Mahsulot qaytarilishi: {str(row.get(m.item_name_col, ''))[:40]}",
                                raw_payload={str(k): str(v) for k, v in row.items() if pd.notna(v)}
                            ))
                except UnparseableValue as cell_error:
                    parse_errors.append(f"Ma'lumot qatori {idx + 1}: {cell_error}")
                    continue
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Faylni o'qishda xatolik yuz berdi: {str(e)}")

    # Check Period Lock
    if org.locked_until_date:
        for rec in records:
            r_date = rec.doc_date or date.today()
            if r_date <= org.locked_until_date:
                raise HTTPException(
                    status_code=400,
                    detail=f"Davr qulflangan: Hujjatdagi sana ({r_date}) yopilgan hisobot davriga "
                           f"({org.locked_until_date} gacha) tegishli. Ushbu davrga yangi amallarni kiritish taqiqlangan!"
                )

    total_records = len(records)
    if task_info:
        task_info.update_progress(25, f"{total_records} ta amal aniqlandi. Kontragentlar va tovarlar solishtirilmoqda...", total_items=total_records)

    imported_count = 0
    errors: List[str] = list(parse_errors)

    # In-memory caches to avoid N roundtrips for large batches (e.g. 1000+ rows)
    cps_res = await db.execute(select(Counterparty).where(Counterparty.organization_id == org.id))
    cp_cache = {c.name: c.id for c in cps_res.scalars().all()}

    items_res = await db.execute(select(InventoryItem).where(InventoryItem.organization_id == org.id))
    existing_items: List[InventoryItem] = list(items_res.scalars().all())

    step_interval = max(1, total_records // 10) if total_records > 0 else 1

    for idx, rec in enumerate(records, start=1):
        try:
            # 1. Resolve or create counterparty
            cp_id = None
            if rec.counterparty_name:
                if rec.counterparty_name in cp_cache:
                    cp_id = cp_cache[rec.counterparty_name]
                else:
                    is_sup = (op_type == "INFLOW" or rec.doc_type == "EHF")
                    is_cli = (op_type == "OUTFLOW" or rec.doc_type in ["BANK", "SOLIQ_SALES"])
                    cp = Counterparty(
                        organization_id=org.id,
                        name=rec.counterparty_name,
                        inn=rec.counterparty_inn,
                        mfo=rec.counterparty_mfo,
                        bank_account=rec.counterparty_account,
                        is_supplier=is_sup,
                        is_client=is_cli
                    )
                    db.add(cp)
                    await db.flush()
                    cp_id = cp.id
                    cp_cache[rec.counterparty_name] = cp_id

            # 2. Resolve or create inventory item using Ultra-Sensitive AI Disambiguator
            it_id = None
            if rec.item_name:
                matched_item = ItemDisambiguator.find_best_match(rec.item_name, existing_items, rec.ikpu_code)
                if matched_item:
                    it_id = matched_item.id
                else:
                    it = InventoryItem(
                        organization_id=org.id,
                        name=rec.item_name,
                        ikpu_code=rec.ikpu_code,
                        package_code=rec.package_code,
                        unit=rec.unit or "dona",
                        min_stock_alert=Decimal("0")
                    )
                    db.add(it)
                    await db.flush()
                    it_id = it.id
                    existing_items.append(it)

            # 3. Dynamic Versioned VAT Calculation
            tx_date = rec.doc_date or date.today()
            if op_type == "INITIAL_BALANCE":
                # Initial inventory balance carries 0% VAT
                v_rate = Decimal("0")
                v_amt = Decimal("0")
            elif rec.vat_rate and rec.vat_rate > 0:
                v_rate = rec.vat_rate
                v_amt = rec.vat_amount or Decimal("0")
            elif org.vat_payer:
                tax_res = TaxEngine.calculate_vat_from_total(rec.total_amount, tx_date, is_vat_payer=True)
                v_rate = tax_res["vat_rate"]
                v_amt = tax_res["vat_amount"]
            else:
                v_rate = Decimal("0")
                v_amt = Decimal("0")

            # 4. Create Transaction
            tx = Transaction(
                organization_id=org.id,
                doc_number=rec.doc_number,
                doc_date=tx_date,
                doc_type=rec.doc_type,
                debit_account=rec.debit_account,
                credit_account=rec.credit_account,
                counterparty_id=cp_id,
                item_id=it_id,
                quantity=rec.quantity,
                price=rec.price,
                total_amount=rec.total_amount,
                vat_rate=v_rate,
                vat_amount=v_amt,
                description=rec.description,
                raw_payload=str(rec.raw_payload) if rec.raw_payload else None
            )
            db.add(tx)
            imported_count += 1

            if task_info and (idx % step_interval == 0 or idx == total_records):
                calc_progress = 25 + int((idx / total_records) * 65)
                task_info.update_progress(
                    progress=calc_progress,
                    step_message=f"Buxgalteriya amallari bazaga yozilmoqda ({idx}/{total_records})...",
                    processed_items=idx,
                    total_items=total_records
                )
        except Exception as ex:
            errors.append(f"Qator xatosi: {str(ex)}")

    if task_info:
        task_info.update_progress(95, "Audit jurnali qayd etilmoqda va tranzaksiya tasdiqlanmoqda...")

    # Audit log
    audit_entry = AuditLog(
        organization_id=org.id,
        action="IMPORT_DOCUMENT",
        entity_type="document",
        entity_id=request.file_id,
        performed_by=performed_by,
        details=f"{imported_count} ta buxgalteriya amali ({request.format_type}) bazaga kiritildi."
    )
    db.add(audit_entry)
    await record_import(
        db, org.id, filename=request.file_id, document_type=request.format_type, digest=digest,
        rows_committed=imported_count, metadata={"errors": len(errors), "performed_by": performed_by},
        allow_duplicate=request.allow_duplicate,
    )
    await commit_or_conflict(db)

    response_payload = CommitResponse(
        success=True,
        imported_count=imported_count,
        errors_count=len(errors),
        message=f"{imported_count} ta buxgalteriya amali bazaga muvaffaqiyatli yozildi.",
        error_details=errors[:10]
    )

    if task_info:
        task_info.complete(
            result=response_payload.model_dump(),
            message=f"{imported_count} ta buxgalteriya amali muvaffaqiyatli yakunlandi."
        )

    return response_payload

@router.post("/commit", response_model=CommitResponse)
async def commit_document(
    request: CommitMappingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_role: UserRole = Depends(require_roles([UserRole.CHIEF_ACCOUNTANT, UserRole.OPERATOR]))
):
    """
    Saves parsed and verified records into PostgreSQL as transactions (synchronous).
    Protected: CHIEF_ACCOUNTANT or OPERATOR with access to the organization.
    """
    await ensure_org_access(db, current_user, request.organization_id)
    return await execute_document_import(
        db=db,
        request=request,
        performed_by=ROLE_LABELS.get(current_role, "Bosh Buxgalter")
    )

@router.post("/commit-async")
async def commit_document_async(
    request: CommitMappingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_role: UserRole = Depends(require_roles([UserRole.CHIEF_ACCOUNTANT, UserRole.OPERATOR]))
):
    """
    Initiates asynchronous background import with real-time progress reporting.
    Protected: CHIEF_ACCOUNTANT or OPERATOR with access to the organization.
    """
    await ensure_org_access(db, current_user, request.organization_id)
    file_path = _existing_upload_path(request.file_id)
    await ensure_not_duplicate(db, request.organization_id, file_sha256(file_path), request.allow_duplicate)

    task_info = task_manager.create_task(
        f"Hujjat importi ({request.format_type}): {request.file_id}", owner_id=str(current_user.id)
    )

    async def _bg_worker(task: TaskInfo):
        async with AsyncSessionLocal() as session:
            try:
                await execute_document_import(
                    db=session,
                    request=request,
                    performed_by=ROLE_LABELS.get(current_role, "Bosh Buxgalter"),
                    task_info=task
                )
            except Exception as e:
                await session.rollback()
                err_msg = e.detail if hasattr(e, 'detail') else str(e)
                task.fail(str(err_msg))

    task_manager.run_coroutine(task_info.id, _bg_worker)

    return {
        "task_id": task_info.id,
        "status": task_info.status.value,
        "step_message": task_info.step_message,
        "message": "Fayl importi fon rejimida boshlandi. Jarayonni /tasks/{task_id} orqali kuzatishingiz mumkin."
    }

@router.post("/pdf-preview")
async def preview_pdf_extraction(
    file: UploadFile = File(...),
):
    """
    Extracts tabular line items and metadata from an uploaded PDF invoice/document
    for instant UI verification before converting or posting.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Faqat PDF formatdagi fayllar qabul qilinadi.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Fayl bo'sh.")

    try:
        extracted = PDFTableExtractor.extract_document_from_pdf(content)
        return {
            "success": True,
            "filename": file.filename,
            "doc_number": extracted.doc_number,
            "doc_date": str(extracted.doc_date) if extracted.doc_date else str(date.today()),
            "supplier_name": extracted.supplier_name,
            "supplier_inn": extracted.supplier_inn,
            "buyer_name": extracted.buyer_name,
            "buyer_inn": extracted.buyer_inn,
            "total_items": len(extracted.line_items),
            "total_amount": sum(item.total_amount for item in extracted.line_items),
            "overall_confidence": extracted.overall_confidence,
            "line_items": [item.model_dump() for item in extracted.line_items]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF tahlilida xatolik: {str(e)}")

@router.post("/pdf-to-excel")
async def export_pdf_to_excel(
    file: UploadFile = File(...),
):
    """
    Extracts line items from an uploaded PDF and generates an authentic, publication-grade
    Didox-compatible .xlsx spreadsheet for download.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Faqat PDF formatdagi fayllar qabul qilinadi.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Fayl bo'sh.")

    try:
        extracted = PDFTableExtractor.extract_document_from_pdf(content)
        excel_buf = OCRExcelExporter.export_document_to_excel(extracted)
        excel_buf.seek(0)

        clean_doc_num = re.sub(r"[^\w\-]", "_", extracted.doc_number or "Hujjat")
        download_name = f"EHF_{clean_doc_num}.xlsx"

        return Response(
            content=excel_buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=\"{download_name}\"",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF dan Excel generatsiya qilishda xatolik: {str(e)}")
