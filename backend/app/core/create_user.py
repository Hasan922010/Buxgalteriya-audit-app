"""
Create a user from the command line.

    python -m app.core.create_user admin --superuser
    python -m app.core.create_user kassir1 --role OPERATOR --org <organization-uuid>

The password is read interactively (never passed as an argument).
"""
import argparse
import asyncio
import getpass
import sys
import uuid

from app.core.database import AsyncSessionLocal, Base, engine
from app.core.rbac import UserRole
from app.models import user as _user_models  # noqa: F401  (registers tables)
from app.services.user_service import UserServiceError, create_user


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Yangi foydalanuvchi yaratish")
    parser.add_argument("username")
    parser.add_argument("--full-name", default="")
    parser.add_argument("--role", choices=[r.value for r in UserRole], default=UserRole.CHIEF_ACCOUNTANT.value)
    parser.add_argument("--superuser", action="store_true", help="Barcha tashkilotlarga kirish va foydalanuvchilarni boshqarish")
    parser.add_argument("--org", action="append", default=[], help="Kirish ruxsati beriladigan tashkilot UUID (bir necha marta)")
    return parser.parse_args()


async def _run(args: argparse.Namespace, password: str) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        user = await create_user(
            session,
            username=args.username,
            password=password,
            role=UserRole(args.role),
            full_name=args.full_name,
            is_superuser=args.superuser,
            organization_ids=[uuid.UUID(o) for o in args.org],
        )
        await session.commit()
        print(f"Foydalanuvchi yaratildi: {user.username} ({user.role}{', superuser' if user.is_superuser else ''})")
    await engine.dispose()


def main() -> int:
    args = _parse_args()
    password = getpass.getpass("Parol: ")
    if password != getpass.getpass("Parolni takrorlang: "):
        print("Parollar mos kelmadi", file=sys.stderr)
        return 1
    try:
        asyncio.run(_run(args, password))
    except (UserServiceError, ValueError) as e:
        print(f"Xatolik: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
