import asyncio
import logging
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, Base, engine
from app.modules.accounting.models import ChartOfAccount, AccountType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_bhms")

BHMS_ACCOUNTS = [
    {"code": "1000", "name": "Materiallar", "account_type": AccountType.ASSET},
    {"code": "2900", "name": "Tovarlar", "account_type": AccountType.ASSET},
    {"code": "4000", "name": "Xaridorlar va buyurtmachilar bilan hisob-kitoblar", "account_type": AccountType.ASSET},
    {"code": "5000", "name": "Milliy valyutadagi pul mablag'lari / Kassa", "account_type": AccountType.ASSET},
    {"code": "5110", "name": "Hisob-kitob schoti / Bank", "account_type": AccountType.ASSET},
    {"code": "6000", "name": "Mol yetkazib beruvchilar bilan hisob-kitoblar", "account_type": AccountType.LIABILITY},
    {"code": "9000", "name": "Asosiy faoliyatdan olingan daromadlar", "account_type": AccountType.REVENUE},
    {"code": "9400", "name": "Davr xarajatlari", "account_type": AccountType.EXPENSE},
]

async def seed_bhms():
    logger.info("Initializing BHMS Chart of Accounts...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        count = 0
        for acc in BHMS_ACCOUNTS:
            existing = await session.execute(
                select(ChartOfAccount).where(ChartOfAccount.code == acc["code"])
            )
            obj = existing.scalar_one_or_none()
            if not obj:
                account_obj = ChartOfAccount(
                    code=acc["code"],
                    name=acc["name"],
                    account_type=acc["account_type"],
                    is_active=True
                )
                session.add(account_obj)
                count += 1
        await session.commit()
        logger.info(f"BHMS seeding completed. Seeded {count} new accounts.")

if __name__ == "__main__":
    asyncio.run(seed_bhms())
