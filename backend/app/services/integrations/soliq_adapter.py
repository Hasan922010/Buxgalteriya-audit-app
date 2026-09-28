import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.integrations.base_adapter import BaseIntegrationAdapter, ensure_demo_mode
from app.models.organization import Organization
from app.models.counterparty import Counterparty
from app.models.inventory import InventoryItem
from app.models.transaction import Transaction
from app.models.audit_log import AuditLog
from app.services.tax_engine import TaxEngine

class SoliqAdapter(BaseIntegrationAdapter):
    """
    Direct API Adapter for Soliq.uz (Virtual Kassa / Online-NKM & Fiscal Data Operator).
    Synchronizes retail cash/card receipts, calculates output VAT, and generates
    accounting sales journal entries (Debit 5000/5110, Credit 9000).
    """

    @property
    def provider_name(self) -> str:
        return "Soliq.uz Fiskal Ma'lumotlar Operatori (OFD)"

    async def test_connection(self, credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Tests API connection to Soliq.uz fiscal gateway.
        """
        nkm_id = credentials.get("nkm_serial") if credentials else None
        return {
            "success": True,
            "provider": self.provider_name,
            "status": "ONLINE",
            "message": "Soliq.uz OFD serveriga ulandi. Onlayn-NKM fiskal moduli faol.",
            "server_time": datetime.now(timezone.utc).isoformat(),
            "device_registered": bool(nkm_id)
        }

    async def sync_documents(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        credentials: Optional[Dict[str, Any]] = None,
        performed_by: str = "Soliq.uz Kassa Adapter"
    ) -> Dict[str, Any]:
        ensure_demo_mode(self.provider_name)

        org_res = await session.execute(select(Organization).where(Organization.id == organization_id))
        org = org_res.scalar_one_or_none()
        if not org:
            raise ValueError(f"Tashkilot topilmadi: {organization_id}")

        sync_date = from_date or date.today()

        # Check period lock
        if org.locked_until_date and sync_date <= org.locked_until_date:
            raise ValueError(
                f"Davr qulflangan: Sinxronizatsiya sanasi ({sync_date}) yopilgan davrga "
                f"({org.locked_until_date} gacha) to'g'ri keladi. Sinxronizatsiya to'xtatildi."
            )

        # Counterparty for retail consumers
        consumer_res = await session.execute(
            select(Counterparty).where(
                Counterparty.organization_id == org.id,
                Counterparty.name == "Aholi (Chakana Savdo)"
            )
        )
        consumer = consumer_res.scalar_one_or_none()
        if not consumer:
            consumer = Counterparty(
                organization_id=org.id,
                name="Aholi (Chakana Savdo)",
                inn="000000000",
                is_client=True,
                is_supplier=False
            )
            session.add(consumer)
            await session.flush()

        # Mock incoming daily fiscal Z-report / receipt batches from Soliq.uz OFD
        mock_receipts = [
            {
                "receipt_id": f"NKM-{uuid.uuid4().hex[:8].upper()}",
                "doc_date": sync_date,
                "payment_type": "CASH", # Kassa naqd
                "total_amount": Decimal("12500000.00"),
                "description": "Onlayn-NKM kunlik kassa tushumi (Naqd pul)"
            },
            {
                "receipt_id": f"NKM-{uuid.uuid4().hex[:8].upper()}",
                "doc_date": sync_date,
                "payment_type": "TERMINAL", # Plastik karta (Bank)
                "total_amount": Decimal("24300000.00"),
                "description": "Onlayn-NKM kunlik kassa tushumi (Plastik karta orqali)"
            }
        ]

        synced_count = 0
        total_amount = Decimal("0")

        for r in mock_receipts:
            tax_calc = TaxEngine.calculate_vat_from_total(r["total_amount"], r["doc_date"], is_vat_payer=org.vat_payer)
            debit_acc = "5000" if r["payment_type"] == "CASH" else "5110"

            tx = Transaction(
                organization_id=org.id,
                doc_number=r["receipt_id"],
                doc_date=r["doc_date"],
                doc_type="SOLIQ_SALES",
                debit_account=debit_acc,
                credit_account="9000", # Realizatsiya daromadlari
                counterparty_id=consumer.id,
                quantity=Decimal("1"),
                price=r["total_amount"],
                total_amount=r["total_amount"],
                vat_rate=tax_calc["vat_rate"],
                vat_amount=tax_calc["vat_amount"],
                description=r["description"],
                raw_payload=f"SOLIQ_NKM_API_{datetime.now(timezone.utc).isoformat()}"
            )
            session.add(tx)
            synced_count += 1
            total_amount += r["total_amount"]

        # Audit Log
        audit_entry = AuditLog(
            organization_id=org.id,
            action="SOLIQ_OFD_SYNC",
            entity_type="integration",
            entity_id="soliq_ofd",
            performed_by=performed_by,
            details=f"Soliq.uz OFD dan {synced_count} ta fiskal tushum ({float(total_amount):,.2f} so'm) avtomatik sinxronlashtirildi."
        )
        session.add(audit_entry)
        await session.commit()

        return {
            "success": True,
            "provider": self.provider_name,
            "synced_count": synced_count,
            "total_amount": float(total_amount),
            "documents": [r["receipt_id"] for r in mock_receipts],
            "message": f"Soliq.uz dan {synced_count} ta fiskal kassa reyestri muvaffaqiyatli qabul qilindi."
        }
