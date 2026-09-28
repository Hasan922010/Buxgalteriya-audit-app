from fastapi import APIRouter, Depends

from app.api.v1.endpoints import (
    auth,
    documents,
    reports,
    accounts,
    counterparties,
    organizations,
    ai_chat,
    tasks,
    integrations,
    backup,
    system
)
from app.core.auth import get_current_user
from app.modules.ocr.router import router as ocr_router
from app.modules.documents.router import router as modular_documents_router

api_router = APIRouter()

# Public: login (the auth router protects its own non-login routes)
api_router.include_router(auth.router, prefix="/auth", tags=["Autentifikatsiya"])

# Everything else requires a valid bearer token
protected = APIRouter(dependencies=[Depends(get_current_user)])
protected.include_router(organizations.router, prefix="/organizations", tags=["Tashkilotlar"])
protected.include_router(accounts.router, prefix="/accounts", tags=["Schotlar Rejasi (BHMS)"])
protected.include_router(counterparties.router, prefix="/counterparties", tags=["Kontragentlar"])
protected.include_router(documents.router, prefix="/documents", tags=["Hujjatlar va ETL Ingestion"])
protected.include_router(reports.router, prefix="/reports", tags=["Buxgalteriya Hisobotlari"])
protected.include_router(ai_chat.router, prefix="/ai", tags=["AI Moliyaviy Tahlilchi"])
protected.include_router(tasks.router, prefix="/tasks", tags=["Asinxron Fon Vazifalari"])
protected.include_router(integrations.router, prefix="/integrations", tags=["Tashqi Tizim Integratsiyalari (Didox / Soliq)"])
protected.include_router(backup.router, prefix="/backup", tags=["Zaxira Nusxalash va Tiklash (Backup Engine)"])
protected.include_router(system.router, prefix="/system", tags=["Tizim Boshqaruvi va Reset"])

# Antigravity Modular Monolith Routers
protected.include_router(ocr_router)
protected.include_router(modular_documents_router)

api_router.include_router(protected)
