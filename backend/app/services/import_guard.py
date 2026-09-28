"""Duplicate-import protection: the same document must not be booked twice by accident."""
import hashlib
import uuid
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import DocumentIngestionLog

_CHUNK = 1024 * 1024


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(*parts: Any) -> str:
    """Stable fingerprint for documents that do not come from a file (e.g. OCR-reviewed invoices)."""
    return hashlib.sha256("|".join("" if p is None else str(p) for p in parts).encode("utf-8")).hexdigest()


async def find_previous_import(db: AsyncSession, org_id: uuid.UUID, digest: str) -> Optional[DocumentIngestionLog]:
    result = await db.execute(
        select(DocumentIngestionLog)
        .where(
            DocumentIngestionLog.organization_id == org_id,
            DocumentIngestionLog.file_sha256 == digest,
            DocumentIngestionLog.status == "COMPLETED",
        )
        .order_by(DocumentIngestionLog.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def ensure_not_duplicate(db: AsyncSession, org_id: uuid.UUID, digest: str, allow_duplicate: bool) -> None:
    """409 when this organization already booked the same document, unless explicitly allowed."""
    if allow_duplicate:
        return
    previous = await find_previous_import(db, org_id, digest)
    if previous:
        when = previous.created_at.strftime("%d.%m.%Y %H:%M") if previous.created_at else "avval"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Bu hujjat ({previous.filename}) allaqachon import qilingan: {when}, "
                f"{previous.rows_committed} ta yozuv. Qayta kiritish yozuvlarni ikki baravar ko'paytiradi. "
                "Ataylab qayta import qilish uchun allow_duplicate=true yuboring."
            ),
        )


STATUS_COMPLETED = "COMPLETED"
STATUS_FORCED_DUPLICATE = "COMPLETED_DUPLICATE"  # deliberate re-import; excluded from the unique index


async def record_import(
    db: AsyncSession,
    org_id: uuid.UUID,
    filename: str,
    document_type: str,
    digest: str,
    rows_committed: int,
    metadata: Optional[Dict[str, Any]] = None,
    allow_duplicate: bool = False,
) -> None:
    # Only an explicitly allowed re-import may coexist with an earlier COMPLETED row; a normal
    # import is always COMPLETED so a concurrent duplicate hits the unique index.
    already_booked = allow_duplicate and await find_previous_import(db, org_id, digest) is not None
    db.add(DocumentIngestionLog(
        organization_id=org_id,
        filename=filename[:255],
        document_type=document_type[:50],
        rows_parsed=rows_committed,
        rows_committed=rows_committed,
        status=STATUS_FORCED_DUPLICATE if already_booked else STATUS_COMPLETED,
        file_sha256=digest,
        metadata_info=metadata or {},
    ))


async def commit_or_conflict(db: AsyncSession) -> None:
    """Commits; a concurrent duplicate that slipped past the pre-check becomes a 409 (whole import rolled back)."""
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        if "uq_ingestion_org_file_completed" in str(e) or "document_ingestion_logs" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bu hujjat hozirgina boshqa so'rov orqali import qilindi. Qayta kiritish yozuvlarni ikki baravar ko'paytiradi.",
            ) from e
        raise
