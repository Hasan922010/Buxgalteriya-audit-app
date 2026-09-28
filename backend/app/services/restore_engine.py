"""Restores organizations from BackupEngine JSON snapshots (inverse of BackupEngine.create_backup)."""
import json
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import resolve_backup_path
from app.models.account import AccountingMode, AccountType, ChartOfAccount
from app.models.audit_log import AuditLog
from app.models.counterparty import Counterparty
from app.models.inventory import InventoryItem
from app.models.organization import Organization
from app.models.transaction import Transaction
from app.models.user import UserOrganization
from app.modules.documents.models import DocumentIngestionLog

SUPPORTED_VERSIONS = {"1.0", "1.1"}
_DATA_SECTIONS = ("organizations", "accounts", "counterparties", "inventory_items", "transactions", "audit_logs")


class RestoreError(ValueError):
    """The snapshot cannot be restored (corrupt, unsupported, or conflicts with current data)."""


# ---------------------------------------------------------------- parsing helpers

def _uuid(v: Any) -> Optional[uuid.UUID]:
    return uuid.UUID(str(v)) if v not in (None, "", "None") else None


def _dec(v: Any) -> Optional[Decimal]:
    if v in (None, "", "None"):
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation as e:
        raise RestoreError(f"Noto'g'ri son qiymati: {v}") from e


def _date(v: Any) -> Optional[date]:
    return date.fromisoformat(str(v)[:10]) if v not in (None, "", "None") else None


def _datetime(v: Any) -> Optional[datetime]:
    if v in (None, "", "None"):
        return None
    parsed = datetime.fromisoformat(str(v))
    return parsed.replace(tzinfo=None)  # audit_logs.created_at is a naive UTC column


def load_backup(filename: str) -> Dict[str, Any]:
    path = resolve_backup_path(filename)
    try:
        with open(path, "rb") as fh:
            payload = json.loads(fh.read().decode("utf-8"))
    except FileNotFoundError:
        raise
    except (ValueError, UnicodeDecodeError) as e:
        raise RestoreError("Zaxira fayli buzilgan (JSON o'qilmadi)") from e

    if payload.get("backup_version") not in SUPPORTED_VERSIONS:
        raise RestoreError(f"Qo'llab-quvvatlanmaydigan zaxira versiyasi: {payload.get('backup_version')}")
    data = payload.get("data")
    if not isinstance(data, dict) or any(not isinstance(data.get(k, []), list) for k in _DATA_SECTIONS):
        raise RestoreError("Zaxira fayli tuzilmasi noto'g'ri")
    if not data.get("organizations"):
        raise RestoreError("Zaxira faylida tashkilot yo'q")
    return payload


# ---------------------------------------------------------------- restore steps

async def _ensure_accounts(session: AsyncSession, accounts: List[Dict[str, Any]]) -> None:
    existing = set((await session.execute(select(ChartOfAccount.code))).scalars().all())
    for a in accounts:
        if a["code"] not in existing:
            session.add(ChartOfAccount(code=a["code"], name=a["name"], account_type=AccountType(a["account_type"]),
                                       is_active=a.get("is_active", True)))


async def _org_has_data(session: AsyncSession, org_id: uuid.UUID) -> bool:
    for model in (Transaction, Counterparty, InventoryItem):
        count = (await session.execute(select(func.count()).select_from(model).where(model.organization_id == org_id))).scalar_one()
        if count:
            return True
    return False


async def _wipe_org(session: AsyncSession, org_id: uuid.UUID) -> None:
    for model in (Transaction, InventoryItem, Counterparty, AuditLog, DocumentIngestionLog):
        await session.execute(delete(model).where(model.organization_id == org_id))


async def _upsert_org(session: AsyncSession, row: Dict[str, Any]) -> None:
    org_id = _uuid(row["id"])
    clash = (await session.execute(
        select(Organization).where(Organization.inn == row["inn"], Organization.id != org_id)
    )).scalar_one_or_none()
    if clash:
        # e.g. the fresh demo organization created by a factory reset: only an empty one may be replaced
        if await _org_has_data(session, clash.id):
            raise RestoreError(f"STIR {row['inn']} boshqa tashkilot ({clash.name}) tomonidan band, u ma'lumotlarga ega")
        clash_members = list((await session.execute(
            select(UserOrganization.user_id).where(UserOrganization.organization_id == clash.id)
        )).scalars().all())
        await _wipe_org(session, clash.id)
        await session.execute(delete(UserOrganization).where(UserOrganization.organization_id == clash.id))
        await session.delete(clash)
        await session.flush()
    else:
        clash_members = []

    org = (await session.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if org is None:
        org = Organization(id=org_id, inn=row["inn"])
        session.add(org)
    org.inn = row["inn"]
    org.name = row["name"]
    org.mode = AccountingMode(row["mode"])
    org.vat_payer = bool(row.get("vat_payer"))
    org.created_at = _date(row.get("created_at")) or date.today()
    org.locked_until_date = _date(row.get("locked_until_date"))
    await session.flush()

    # Users who could access the replaced organization keep access to the restored one
    existing = set((await session.execute(
        select(UserOrganization.user_id).where(UserOrganization.organization_id == org_id)
    )).scalars().all())
    session.add_all(UserOrganization(user_id=u, organization_id=org_id) for u in clash_members if u not in existing)


def _rows_for(rows: Iterable[Dict[str, Any]], org_ids: set) -> List[Dict[str, Any]]:
    return [r for r in rows if _uuid(r.get("organization_id")) in org_ids]


def _insert_rows(session: AsyncSession, data: Dict[str, Any], org_ids: set) -> Dict[str, int]:
    cps = _rows_for(data.get("counterparties", []), org_ids)
    items = _rows_for(data.get("inventory_items", []), org_ids)
    txs = _rows_for(data.get("transactions", []), org_ids)
    logs = _rows_for(data.get("audit_logs", []), org_ids)

    session.add_all(Counterparty(
        id=_uuid(c["id"]), organization_id=_uuid(c["organization_id"]), name=c["name"], inn=c.get("inn"),
        mfo=c.get("mfo"), bank_account=c.get("bank_account"), phone=c.get("phone"),
        is_supplier=c.get("is_supplier", True), is_client=c.get("is_client", True),
    ) for c in cps)
    session.add_all(InventoryItem(
        id=_uuid(i["id"]), organization_id=_uuid(i["organization_id"]), name=i["name"], ikpu_code=i.get("ikpu_code"),
        package_code=i.get("package_code"), unit=i.get("unit") or "dona", min_stock_alert=_dec(i.get("min_stock_alert")) or 0,
    ) for i in items)
    session.add_all(Transaction(
        id=_uuid(t["id"]), organization_id=_uuid(t["organization_id"]), doc_number=t.get("doc_number"),
        doc_date=_date(t["doc_date"]), doc_type=t["doc_type"], debit_account=t.get("debit_account"),
        credit_account=t.get("credit_account"), counterparty_id=_uuid(t.get("counterparty_id")), item_id=_uuid(t.get("item_id")),
        quantity=_dec(t.get("quantity")) or 0, price=_dec(t.get("price")) or 0, total_amount=_dec(t["total_amount"]),
        vat_rate=_dec(t.get("vat_rate")) or 0, vat_amount=_dec(t.get("vat_amount")) or 0,
        description=t.get("description"), raw_payload=t.get("raw_payload"),
        is_reversed=bool(t.get("is_reversed")), reversal_ref_id=_uuid(t.get("reversal_ref_id")),
        reversal_reason=t.get("reversal_reason"), created_at=_date(t.get("created_at")) or date.today(),
    ) for t in txs)
    session.add_all(AuditLog(
        id=_uuid(entry["id"]), organization_id=_uuid(entry["organization_id"]), action=entry["action"],
        entity_type=entry["entity_type"], entity_id=entry.get("entity_id"), performed_by=entry.get("performed_by"),
        details=entry.get("details"), created_at=_datetime(entry.get("created_at")) or datetime.utcnow(),
    ) for entry in logs)
    return {"counterparties": len(cps), "inventory_items": len(items), "transactions": len(txs), "audit_logs": len(logs)}


async def restore_backup(session: AsyncSession, payload: Dict[str, Any], performed_by: str) -> Dict[str, Any]:
    """
    Replaces the operational data of every organization in the snapshot with the snapshot content.
    Organizations not in the snapshot are left untouched. Does not commit.
    """
    data = payload["data"]
    try:
        org_ids = {_uuid(o["id"]) for o in data["organizations"]}
        await _ensure_accounts(session, data.get("accounts", []))
        for org_row in data["organizations"]:
            await _upsert_org(session, org_row)
        await session.flush()
        for org_id in org_ids:
            await _wipe_org(session, org_id)
        await session.flush()
        counts = _insert_rows(session, data, org_ids)
        await session.flush()
    except (KeyError, TypeError, ValueError) as e:
        if isinstance(e, RestoreError):
            raise
        raise RestoreError(f"Zaxira faylidagi ma'lumot noto'g'ri: {e}") from e

    for org_id in org_ids:
        session.add(AuditLog(
            organization_id=org_id, action="BACKUP_RESTORED", entity_type="backup", entity_id=payload.get("backup_id"),
            performed_by=performed_by, details=f"Zaxira nusxasidan tiklandi ({payload.get('created_at')}).",
        ))
    return {"organizations": len(org_ids), **counts}
