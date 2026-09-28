import uuid
from datetime import date
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.config import settings
from app.core.auth import ensure_org_access, get_current_user
from app.models.user import User
from app.core.database import get_db
from app.core.rbac import UserRole, require_roles, ROLE_LABELS
from app.services.integrations import DidoxAdapter, SoliqAdapter
from app.services.integrations.base_adapter import BaseIntegrationAdapter

router = APIRouter()

didox_adapter = DidoxAdapter()
soliq_adapter = SoliqAdapter()

# The adapters do not call the real Didox / Soliq APIs yet: they fabricate sample
# documents. They may only run when demo mode is explicitly enabled.
DEMO_DISABLED_DETAIL = (
    "Didox/Soliq integratsiyasi hali haqiqiy API'ga ulanmagan. Hozirgi adapterlar faqat demo "
    "(simulyatsiya) hujjatlar yaratadi va haqiqiy buxgalteriyaga yozilmasligi kerak. "
    "Faqat test bazasida INTEGRATIONS_DEMO_MODE=True sozlab sinab ko'ring."
)

class SyncRequest(BaseModel):
    organization_id: uuid.UUID
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    api_token: Optional[str] = None
    nkm_serial: Optional[str] = None

async def _connection_status(adapter: BaseIntegrationAdapter, credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not settings.INTEGRATIONS_DEMO_MODE:
        return {
            "success": False,
            "provider": adapter.provider_name,
            "status": "NOT_CONFIGURED",
            "demo_mode": False,
            "message": "Haqiqiy API integratsiyasi hali ulanmagan."
        }
    result = await adapter.test_connection(credentials)
    return {**result, "status": "DEMO", "demo_mode": True}

def _require_demo_mode() -> None:
    if not settings.INTEGRATIONS_DEMO_MODE:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=DEMO_DISABLED_DETAIL)

@router.get("/status")
async def get_integrations_status():
    """
    Returns connectivity status for Didox.uz and Soliq.uz integrations.
    """
    return {
        "didox": await _connection_status(didox_adapter),
        "soliq": await _connection_status(soliq_adapter)
    }

@router.post("/didox/test")
async def test_didox_connection(credentials: Optional[Dict[str, Any]] = None):
    return await _connection_status(didox_adapter, credentials)

@router.post("/didox/sync")
async def sync_didox_documents(
    payload: SyncRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_role: UserRole = Depends(require_roles([UserRole.CHIEF_ACCOUNTANT, UserRole.OPERATOR]))
):
    """
    DEMO ONLY: generates simulated Didox invoices as accounting entries.
    Disabled unless INTEGRATIONS_DEMO_MODE=True. Protected: CHIEF_ACCOUNTANT or OPERATOR.
    """
    _require_demo_mode()
    await ensure_org_access(db, current_user, payload.organization_id)
    try:
        res = await didox_adapter.sync_documents(
            session=db,
            organization_id=payload.organization_id,
            from_date=payload.from_date,
            to_date=payload.to_date,
            credentials={"api_token": payload.api_token},
            performed_by=f"{ROLE_LABELS.get(current_role, 'Bosh Buxgalter')} (Didox DEMO)"
        )
        return {**res, "demo_mode": True}
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Sinxronizatsiya xatosi: {str(e)}")

@router.post("/soliq/test")
async def test_soliq_connection(credentials: Optional[Dict[str, Any]] = None):
    return await _connection_status(soliq_adapter, credentials)

@router.post("/soliq/sync")
async def sync_soliq_receipts(
    payload: SyncRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_role: UserRole = Depends(require_roles([UserRole.CHIEF_ACCOUNTANT, UserRole.OPERATOR]))
):
    """
    DEMO ONLY: generates simulated Soliq OFD receipts as accounting entries.
    Disabled unless INTEGRATIONS_DEMO_MODE=True. Protected: CHIEF_ACCOUNTANT or OPERATOR.
    """
    _require_demo_mode()
    await ensure_org_access(db, current_user, payload.organization_id)
    try:
        res = await soliq_adapter.sync_documents(
            session=db,
            organization_id=payload.organization_id,
            from_date=payload.from_date,
            to_date=payload.to_date,
            credentials={"nkm_serial": payload.nkm_serial},
            performed_by=f"{ROLE_LABELS.get(current_role, 'Bosh Buxgalter')} (Soliq DEMO)"
        )
        return {**res, "demo_mode": True}
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Sinxronizatsiya xatosi: {str(e)}")
