import asyncio
import argparse
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import date
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine, Base
from app.models.organization import Organization
from app.models.account import ChartOfAccount, AccountingMode
from app.models.counterparty import Counterparty
from app.models.inventory import InventoryItem
from app.models.transaction import Transaction
from app.models.audit_log import AuditLog
from app.models.user import UserOrganization
from app.modules.documents.models import DocumentIngestionLog
from app.core.seed_bhms import seed_bhms
from app.services.backup_engine import BackupEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reset_database")

async def reset_organization_data(session: AsyncSession, org_id: uuid.UUID) -> Dict[str, Any]:
    """
    Cleans all operational and financial records for a specific organization:
    - Transactions
    - Inventory Items
    - Counterparties
    - Document Ingestion Logs
    - Audit Logs
    - Unlocks period lock (locked_until_date = None)
    The organization profile and BHMS chart of accounts remain intact.
    """
    org = (await session.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        raise ValueError(f"Tashkilot topilmadi: {org_id}")

    # 1. Delete transactions
    tx_del = await session.execute(delete(Transaction).where(Transaction.organization_id == org_id))
    deleted_txs = tx_del.rowcount

    # 2. Delete inventory items
    inv_del = await session.execute(delete(InventoryItem).where(InventoryItem.organization_id == org_id))
    deleted_items = inv_del.rowcount

    # 3. Delete counterparties
    cp_del = await session.execute(delete(Counterparty).where(Counterparty.organization_id == org_id))
    deleted_cps = cp_del.rowcount

    # 4. Delete document ingestion logs
    try:
        doc_del = await session.execute(delete(DocumentIngestionLog).where(DocumentIngestionLog.organization_id == org_id))
        deleted_docs = doc_del.rowcount
    except Exception:
        deleted_docs = 0

    # 5. Delete audit logs
    try:
        audit_del = await session.execute(delete(AuditLog).where(AuditLog.organization_id == org_id))
        deleted_audits = audit_del.rowcount
    except Exception:
        deleted_audits = 0

    # 6. Reset period lock
    org.locked_until_date = None

    # 7. Add fresh audit record
    new_log = AuditLog(
        organization_id=org.id,
        action="ORGANIZATION_RESET",
        entity_type="organization",
        entity_id=str(org.id),
        performed_by="Bosh Buxgalter",
        details=f"Tashkilot ma'lumotlari noldan tozalandi: {deleted_txs} ta o'tkazma, {deleted_items} ta tovar, {deleted_cps} ta kontragent o'chirildi."
    )
    session.add(new_log)
    await session.commit()

    logger.info(f"Organization {org.name} ({org.inn}) data reset successfully.")
    return {
        "success": True,
        "organization_id": str(org.id),
        "organization_name": org.name,
        "deleted_transactions": deleted_txs,
        "deleted_inventory_items": deleted_items,
        "deleted_counterparties": deleted_cps,
        "message": f"{org.name} tashkilotining barcha operatsiyalari va qoldiqlari noldan tozalandi."
    }

class ResetAfterBackupError(RuntimeError):
    """A wipe failed after its safety backup was written; data may be partially deleted."""

    def __init__(self, backup_filename: str, cause: Exception):
        self.backup_filename = backup_filename
        super().__init__(
            f"Tozalash yarim yo'lda to'xtadi ({cause}). Ma'lumotlar qisman o'chgan bo'lishi mumkin; "
            f"tiklash uchun zaxira fayli: {backup_filename}"
        )

async def reset_organization_with_backup(
    session: AsyncSession,
    org_id: uuid.UUID,
    performed_by: str = "Bosh Buxgalter"
) -> Dict[str, Any]:
    """Snapshots the organization to a backup file, then wipes its operational data."""
    org = (await session.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        raise ValueError(f"Tashkilot topilmadi: {org_id}")

    backup = await BackupEngine.create_backup(
        session, organization_id=org_id, created_by=f"{performed_by} (tozalashdan oldin avtomatik)"
    )
    try:
        result = await reset_organization_data(session=session, org_id=org_id)
    except Exception as e:
        raise ResetAfterBackupError(backup["filename"], e) from e
    return {**result, "pre_reset_backup": backup["filename"]}

async def factory_reset_with_backup(session: AsyncSession, performed_by: str = "Bosh Buxgalter") -> Dict[str, Any]:
    """Snapshots the whole database to a backup file, then performs a factory reset."""
    backup = await BackupEngine.create_backup(
        session, organization_id=None, created_by=f"{performed_by} (factory reset oldidan avtomatik)"
    )
    try:
        result = await factory_reset_database(session=session, reseed_bhms=True, create_clean_demo_org=True)
    except Exception as e:
        raise ResetAfterBackupError(backup["filename"], e) from e
    return {**result, "pre_reset_backup": backup["filename"]}

async def factory_reset_database(
    session: AsyncSession,
    reseed_bhms: bool = True,
    create_clean_demo_org: bool = True
) -> Dict[str, Any]:
    """
    Performs full factory reset of the entire accounting database:
    - Clears all transactions, inventory, counterparties, documents, audit logs
    - Clears all organizations
    - Ensures standard BHMS chart of accounts are in place
    - Optionally creates one fresh clean demo organization
    """
    logger.info("Executing full factory reset...")

    # Delete all business entities
    await session.execute(delete(Transaction))
    await session.execute(delete(InventoryItem))
    await session.execute(delete(Counterparty))
    try:
        await session.execute(delete(DocumentIngestionLog))
    except Exception:
        pass
    try:
        await session.execute(delete(AuditLog))
    except Exception:
        pass
    # Memberships point at organizations; users themselves are kept
    await session.execute(delete(UserOrganization))
    await session.execute(delete(Organization))
    await session.commit()

    # Re-seed BHMS
    if reseed_bhms:
        await seed_bhms()

    # Re-create clean demo org if requested
    created_org_id = None
    if create_clean_demo_org:
        demo_org = Organization(
            name="Asosiy Korxona MCHJ",
            inn="123456789",
            mode=AccountingMode.BHMS,
            vat_payer=True,
            created_at=date.today(),
            locked_until_date=None
        )
        session.add(demo_org)
        await session.commit()
        await session.refresh(demo_org)
        created_org_id = str(demo_org.id)

    logger.info("Factory reset completed successfully.")
    return {
        "success": True,
        "reseeded_bhms": reseed_bhms,
        "created_demo_org_id": created_org_id,
        "message": "Ma'lumotlar bazasi noldan to'liq tozalandi va standart BHMS schotlar rejasi tiklandi."
    }

async def main():
    parser = argparse.ArgumentParser(description="Yordamchi Buxgalter AI - Database Reset Utility")
    parser.add_argument("--all", action="store_true", help="Factory reset entire database")
    parser.add_argument("--org-id", type=str, help="Specific organization UUID to reset")
    args = parser.parse_args()

    async with AsyncSessionLocal() as session:
        if args.all:
            res = await factory_reset_database(session)
            print(res)
        elif args.org_id:
            res = await reset_organization_data(session, uuid.UUID(args.org_id))
            print(res)
        else:
            print("Please specify --all or --org-id <uuid>")

if __name__ == "__main__":
    asyncio.run(main())
