import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(64), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False, default="")
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False)  # app.core.rbac.UserRole value
    is_superuser = Column(Boolean, nullable=False, default=False)  # sees all organizations, manages users
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class UserOrganization(Base):
    """Which organizations a (non-superuser) user may access."""
    __tablename__ = "user_organizations"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True, index=True
    )
