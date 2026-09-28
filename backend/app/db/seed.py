import asyncio
import logging
from datetime import date
from sqlalchemy import select, text
from app.core.database import AsyncSessionLocal, Base, engine
from app.models.account import ChartOfAccount, AccountType, AccountingMode
from app.models.organization import Organization
from app.models.counterparty import Counterparty
from app.models.inventory import InventoryItem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed")

BHMS_ACCOUNTS = [
    # Aktiv schotlar (Assets)
    {"code": "0100", "name": "Asosiy vositalar", "account_type": AccountType.ASSET},
    {"code": "1000", "name": "Materiallar", "account_type": AccountType.ASSET},
    {"code": "1010", "name": "Xomashyo va materiallar", "account_type": AccountType.ASSET},
    {"code": "2000", "name": "Asosiy ishlab chiqarish", "account_type": AccountType.EXPENSE},
    {"code": "2900", "name": "Tovarlar", "account_type": AccountType.ASSET},
    {"code": "2910", "name": "Ombordagi tovarlar", "account_type": AccountType.ASSET},
    {"code": "4000", "name": "Xaridorlar va buyurtmachilar bilan hisob-kitoblar", "account_type": AccountType.ASSET},
    {"code": "4010", "name": "Xaridorlardan olinadigan hisoblar", "account_type": AccountType.ASSET},
    {"code": "5000", "name": "Kassa (Milliy valyuta)", "account_type": AccountType.ASSET},
    {"code": "5110", "name": "Hisob-kitob schoti (Bank hisobi)", "account_type": AccountType.ASSET},
    {"code": "5200", "name": "Valyuta schotlari", "account_type": AccountType.ASSET},
    
    # Passiv schotlar (Liabilities)
    {"code": "6000", "name": "Mol yetkazib beruvchilar va pudratchilar", "account_type": AccountType.LIABILITY},
    {"code": "6010", "name": "Mol yetkazib beruvchilarga to'lanadigan hisoblar", "account_type": AccountType.LIABILITY},
    {"code": "6700", "name": "Mehnat haqi bo'yicha xodimlar bilan hisob-kitoblar", "account_type": AccountType.LIABILITY},
    {"code": "6800", "name": "Soliqlar va majburiy to'lovlar bo'yicha qarzlar", "account_type": AccountType.LIABILITY},
    {"code": "6820", "name": "Qo'shilgan qiymat solig'i (QQS) bo'yicha qarz", "account_type": AccountType.LIABILITY},
    
    # Kapital (Equity)
    {"code": "8300", "name": "Ustav kapitali", "account_type": AccountType.EQUITY},
    {"code": "8500", "name": "Zaxira kapitali", "account_type": AccountType.EQUITY},
    {"code": "8700", "name": "Taqsimlanmagan foyda (qoplanmagan zarar)", "account_type": AccountType.EQUITY},
    
    # Daromad va Xarajatlar (Revenue & Expenses)
    {"code": "9000", "name": "Asosiy faoliyat daromadlari (Sotishdan tushum)", "account_type": AccountType.REVENUE},
    {"code": "9100", "name": "Sotilgan mahsulot (tovar)lar tannarxi", "account_type": AccountType.EXPENSE},
    {"code": "9400", "name": "Davr xarajatlari (Ma'muriy va sotish xarajatlari)", "account_type": AccountType.EXPENSE},
    {"code": "9900", "name": "Yakuniy moliyaviy natija (Foyda / Zarar)", "account_type": AccountType.EQUITY},
]

async def seed_database():
    """Initializes tables and populates BHMS Chart of Accounts and sample Organization."""
    logger.info("Connecting to database and verifying tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS locked_until_date DATE;"))
            await conn.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS is_reversed BOOLEAN DEFAULT FALSE;"))
            await conn.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS reversal_ref_id UUID;"))
            await conn.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS reversal_reason VARCHAR(255);"))
            await conn.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS created_at DATE DEFAULT CURRENT_DATE;"))
            await conn.execute(text("ALTER TABLE counterparties ADD COLUMN IF NOT EXISTS phone VARCHAR(50);"))
            await conn.execute(text("ALTER TABLE document_ingestion_logs ADD COLUMN IF NOT EXISTS file_sha256 VARCHAR(64);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_document_ingestion_logs_file_sha256 ON document_ingestion_logs (file_sha256);"))
            await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_ingestion_org_file_completed ON document_ingestion_logs (organization_id, file_sha256) WHERE status = 'COMPLETED';"))
        except Exception as alter_err:
            logger.info(f"Column verify info: {alter_err}")
    logger.info("Tables created or verified.")

    async with AsyncSessionLocal() as session:
        # 1. Seed Chart of Accounts
        for acc in BHMS_ACCOUNTS:
            existing = await session.execute(select(ChartOfAccount).where(ChartOfAccount.code == acc["code"]))
            if not existing.scalar_one_or_none():
                account_obj = ChartOfAccount(
                    code=acc["code"],
                    name=acc["name"],
                    account_type=acc["account_type"],
                    is_active=True
                )
                session.add(account_obj)
        await session.commit()
        logger.info(f"Seeded {len(BHMS_ACCOUNTS)} BHMS Chart of Accounts.")

        # 2. Seed Demo Organization
        inn = "123456789"
        existing_org = await session.execute(select(Organization).where(Organization.inn == inn))
        org = existing_org.scalar_one_or_none()
        if not org:
            org = Organization(
                name="O'zbekiston Savdo MCHJ",
                inn=inn,
                mode=AccountingMode.BHMS,
                vat_payer=True,
                created_at=date(2025, 1, 1)
            )
            session.add(org)
            await session.commit()
            await session.refresh(org)
            logger.info(f"Created demo organization: {org.name} (ID: {org.id})")
        else:
            logger.info(f"Demo organization already exists: {org.name}")

        # 3. Seed Sample Counterparties
        counterparties_data = [
            {
                "name": "Toshkent Mega Ta'minot MCHJ",
                "inn": "301234567",
                "mfo": "00440",
                "bank_account": "20208000900123456789",
                "is_supplier": True,
                "is_client": False
            },
            {
                "name": "Samarqand Savdo Fayz MCHJ",
                "inn": "309876543",
                "mfo": "00880",
                "bank_account": "20208000400987654321",
                "is_supplier": False,
                "is_client": True
            },
            {
                "name": "Agro Standart Logistika XK",
                "inn": "305555555",
                "mfo": "00014",
                "bank_account": "20208000100555555001",
                "is_supplier": True,
                "is_client": True
            }
        ]

        for cp in counterparties_data:
            existing_cp = await session.execute(
                select(Counterparty).where(
                    Counterparty.organization_id == org.id,
                    Counterparty.inn == cp["inn"]
                )
            )
            if not existing_cp.scalar_one_or_none():
                cp_obj = Counterparty(
                    organization_id=org.id,
                    name=cp["name"],
                    inn=cp["inn"],
                    mfo=cp["mfo"],
                    bank_account=cp["bank_account"],
                    is_supplier=cp["is_supplier"],
                    is_client=cp["is_client"]
                )
                session.add(cp_obj)

        # 4. Seed Sample Inventory Items
        items_data = [
            {
                "name": "A4 Format Qog'oz (SvetoCopy Classic)",
                "ikpu_code": "01712001001000000",
                "package_code": "100234",
                "unit": "dona",
                "min_stock_alert": 50
            },
            {
                "name": "Noutbuk Lenovo ThinkBook 15 G2",
                "ikpu_code": "04510002001000000",
                "package_code": "100987",
                "unit": "dona",
                "min_stock_alert": 5
            },
            {
                "name": "Printer Toner HP LaserJet 1005",
                "ikpu_code": "01719003001000000",
                "package_code": "100456",
                "unit": "dona",
                "min_stock_alert": 10
            }
        ]

        for it in items_data:
            existing_it = await session.execute(
                select(InventoryItem).where(
                    InventoryItem.organization_id == org.id,
                    InventoryItem.name == it["name"]
                )
            )
            if not existing_it.scalar_one_or_none():
                it_obj = InventoryItem(
                    organization_id=org.id,
                    name=it["name"],
                    ikpu_code=it["ikpu_code"],
                    package_code=it["package_code"],
                    unit=it["unit"],
                    min_stock_alert=it["min_stock_alert"]
                )
                session.add(it_obj)

        await session.commit()
        logger.info("Successfully seeded counterparties and inventory items.")

if __name__ == "__main__":
    asyncio.run(seed_database())
