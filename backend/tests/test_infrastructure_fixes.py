"""Phase 4 infrastructure fixes: VAT history, health check, fail-fast startup, Alembic migrations."""
import asyncio
import os
from datetime import date
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, inspect

from app.core.config import settings
from app.main import app, lifespan
from app.services.tax_engine import TaxEngine

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.parametrize("day, rate", [
    (date(2018, 6, 1), "0.20"),
    (date(2019, 9, 30), "0.20"),
    (date(2019, 10, 1), "0.15"),
    (date(2022, 12, 31), "0.15"),
    (date(2023, 1, 1), "0.12"),
])
def test_vat_rate_history(day, rate):
    assert TaxEngine.get_vat_rate(day) == Decimal(rate)


@pytest.mark.asyncio
async def test_health_reports_database_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["database"] == "ok"
    assert "db_port" not in resp.json()  # no infrastructure details for anonymous callers


@pytest.mark.asyncio
async def test_startup_fails_fast_when_database_init_fails(monkeypatch):
    import app.main as main_module

    async def broken_seed():
        raise RuntimeError("database unreachable")

    monkeypatch.setattr(main_module, "seed_database", broken_seed)
    with pytest.raises(RuntimeError, match="database unreachable"):
        async with lifespan(app):
            pass


def _alembic(db_file: str, *args: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))
    original = settings.DATABASE_URL
    settings.DATABASE_URL = "sqlite+aiosqlite:///" + db_file.replace("\\", "/")
    try:
        getattr(command, args[0])(cfg, *args[1:])
    finally:
        settings.DATABASE_URL = original


def _schema(db_file: str):
    eng = create_engine("sqlite:///" + db_file.replace("\\", "/"))
    insp = inspect(eng)
    tables = set(insp.get_table_names())
    cols = {c["name"] for c in insp.get_columns("document_ingestion_logs")} if "document_ingestion_logs" in tables else set()
    eng.dispose()
    return tables, cols


EXPECTED_TABLES = {"users", "user_organizations", "audit_logs", "document_ingestion_logs", "transactions", "organizations"}


def test_migrations_build_full_schema_on_empty_database(tmp_path):
    db = str(tmp_path / "fresh.db")
    _alembic(db, "upgrade", "head")
    tables, cols = _schema(db)
    assert EXPECTED_TABLES <= tables
    assert "file_sha256" in cols


def test_migration_002_is_safe_on_database_created_by_create_all(tmp_path):
    """The existing dev DB was built with create_all: `stamp 001` then `upgrade head` must not fail."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.core.database import Base
    import app.models  # noqa: F401

    db = str(tmp_path / "legacy.db")

    async def build():
        eng = create_async_engine("sqlite+aiosqlite:///" + db.replace("\\", "/"))
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await eng.dispose()

    asyncio.run(build())
    _alembic(db, "stamp", "001_initial")
    _alembic(db, "upgrade", "head")
    tables, cols = _schema(db)
    assert EXPECTED_TABLES <= tables and "file_sha256" in cols
