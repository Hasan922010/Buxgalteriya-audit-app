import uuid
from abc import ABC, abstractmethod
from datetime import date
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings


class IntegrationDemoModeDisabled(RuntimeError):
    """Raised when a simulated adapter is asked to write to the books outside demo mode."""


def ensure_demo_mode(provider_name: str) -> None:
    """The adapters fabricate sample documents; refuse to run unless demo mode is on."""
    if not settings.INTEGRATIONS_DEMO_MODE:
        raise IntegrationDemoModeDisabled(
            f"{provider_name}: haqiqiy API ulanmagan, demo hujjatlar faqat INTEGRATIONS_DEMO_MODE=True bo'lganda yaratiladi."
        )


class BaseIntegrationAdapter(ABC):
    """
    Abstract base class for all external fiscal and electronic document integrations
    (Didox.uz, Soliq.uz, Bank-Client APIs).
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns human-readable name of the external integration provider."""
        pass

    @abstractmethod
    async def test_connection(self, credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validates API credentials or connectivity with the external service."""
        pass

    @abstractmethod
    async def sync_documents(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        credentials: Optional[Dict[str, Any]] = None,
        performed_by: str = "Tizim Integratsiyasi"
    ) -> Dict[str, Any]:
        """
        Pulls electronic documents from the external provider and ingests them
        into the database as verified transactions.
        """
        pass
