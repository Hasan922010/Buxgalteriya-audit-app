import os
import uuid
from decimal import Decimal
import pandas as pd
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.modules.accounting.services import AccountingService
from app.modules.accounting.schemas import TransactionCreate
from app.modules.documents.parsers.didox_parser import DidoxParser
from app.modules.documents.parsers.soliq_parser import SoliqParser
from app.modules.documents.parsers.bank_parser import BankParser
from app.modules.documents.schemas import ParsedRecordItem, ParsePreviewResponse

class DocumentIngestionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.accounting_service = AccountingService(session)

    def inspect_and_preview(self, file_path: str, filename: str) -> ParsePreviewResponse:
        """
        Inspects an uploaded file (XLSX, XLS, CSV), identifies document format,
        extracts headers, sample rows, and generates candidate parsed records.
        """
        if not os.path.exists(file_path):
            raise HTTPException(status_code=400, detail="Fayl topilmadi.")

        # Read preview
        if filename.endswith(".csv"):
            df_preview = pd.read_csv(file_path, nrows=10)
        else:
            df_preview = pd.read_excel(file_path, nrows=10)

        headers = [str(c).strip() for c in df_preview.columns]

        # 1. Format Detection
        didox_match, didox_conf = DidoxParser.detect_format(df_preview, headers)
        soliq_match, soliq_conf = SoliqParser.detect_format(df_preview, headers)
        bank_match, bank_conf = BankParser.detect_format(df_preview, headers)

        detected_type = "DIDOX"
        confidence = didox_conf

        if bank_match and bank_conf > confidence:
            detected_type = "BANK"
            confidence = bank_conf
        elif soliq_match and soliq_conf > confidence:
            detected_type = "SOLIQ"
            confidence = soliq_conf

        # 2. Parse records using selected parser
        if detected_type == "BANK":
            parser = BankParser()
        elif detected_type == "SOLIQ":
            parser = SoliqParser()
        else:
            parser = DidoxParser()

        parsed_records = parser.parse_file(file_path)

        # 3. Build sample rows
        preview_rows = []
        for _, row in df_preview.head(5).iterrows():
            clean_row = {}
            for k, v in row.items():
                clean_row[str(k)] = str(v) if pd.notna(v) else ""
            preview_rows.append(clean_row)

        column_mapping = {
            "hujjat_raqami": next((h for h in headers if "raqam" in h.lower() or "номер" in h.lower()), None),
            "sana": next((h for h in headers if "sana" in h.lower() or "дата" in h.lower()), None),
            "kontragent": next((h for h in headers if any(k in h.lower() for k in ["xaridor", "yetkazib", "kontragent"])), None),
            "tovar_nomi": next((h for h in headers if any(k in h.lower() for k in ["nomi", "tovar", "mahsulot"])), None),
            "jami_summa": next((h for h in headers if any(k in h.lower() for k in ["jami", "summa", "всего", "итого"])), None),
        }

        return ParsePreviewResponse(
            detected_type=detected_type,
            confidence=confidence,
            filename=filename,
            total_rows=len(parsed_records),
            headers=headers,
            column_mapping=column_mapping,
            preview_rows=preview_rows,
            parsed_records=parsed_records[:100]  # return top 100 for interactive preview
        )

    async def commit_parsed_records(
        self,
        org_id: uuid.UUID,
        records: List[ParsedRecordItem],
        operation_type: str = "INFLOW",
        default_debit: str = None,
        default_credit: str = None
    ) -> Dict[str, Any]:
        """
        Commits parsed records into the accounting database.
        Automatically links or creates counterparties and inventory items.
        """
        created_tx_ids = []
        for rec in records:
            # 1. Resolve counterparty (supplier or buyer)
            cp_name = rec.supplier_name or rec.buyer_name
            cp_inn = rec.supplier_inn or rec.buyer_inn
            cp = None
            if cp_name:
                is_sup = (operation_type == "INFLOW" or bool(rec.supplier_name))
                is_cli = (operation_type == "OUTFLOW" or bool(rec.buyer_name))
                cp = await self.accounting_service.get_or_create_counterparty(
                    org_id=org_id,
                    name=cp_name,
                    inn=cp_inn,
                    is_supplier=is_sup,
                    is_client=is_cli
                )

            # 2. Resolve inventory item using ultra-sensitive disambiguator
            item = None
            if rec.item_name:
                item = await self.accounting_service.get_or_create_inventory_item(
                    org_id=org_id,
                    name=rec.item_name,
                    ikpu_code=rec.ikpu_code,
                    unit=rec.unit
                )

            # 3. Create transaction based on operation_type
            if operation_type == "INITIAL_BALANCE":
                debit = default_debit or rec.debit_account or "2900"
                credit = default_credit or rec.credit_account or "8300"
                d_type = "INITIAL_BALANCE"
                vat_r = Decimal("0")
                vat_a = Decimal("0")
            elif operation_type == "OUTFLOW":
                debit = default_debit or rec.debit_account or "4000"
                credit = default_credit or rec.credit_account or "9000"
                d_type = rec.doc_type if rec.doc_type != "EHF" else "OUTFLOW"
                vat_r = rec.vat_rate
                vat_a = rec.vat_amount
            else:
                debit = default_debit or rec.debit_account or "2900"
                credit = default_credit or rec.credit_account or "6000"
                d_type = rec.doc_type
                vat_r = rec.vat_rate
                vat_a = rec.vat_amount

            tx_data = TransactionCreate(
                organization_id=org_id,
                doc_number=rec.doc_number or "INGEST",
                doc_date=rec.doc_date,
                doc_type=d_type,
                debit_account=debit,
                credit_account=credit,
                counterparty_id=cp.id if cp else None,
                item_id=item.id if item else None,
                quantity=rec.quantity,
                price=rec.price,
                vat_rate=vat_r,
                vat_amount=vat_a,
                total_amount=rec.total_amount,
                description=rec.description or f"{d_type}: {rec.item_name or cp_name or ''}"
            )
            tx = await self.accounting_service.record_transaction(tx_data)
            created_tx_ids.append(str(tx.id))

        return {
            "success": True,
            "committed_count": len(created_tx_ids),
            "transaction_ids": created_tx_ids,
            "message": f"{len(created_tx_ids)} ta qator buxgalteriya balansiga muvaffaqiyatli kiritildi."
        }
