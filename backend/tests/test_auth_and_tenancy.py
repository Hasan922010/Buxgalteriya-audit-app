"""Real JWT authentication, RBAC-from-token and organization isolation (audit findings C1 / H4)."""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import AsyncSessionLocal, engine
from app.core.rbac import UserRole
from app.core.security import create_access_token
from app.db.seed import seed_database
from app.main import app
from app.models.organization import Organization
from app.models.transaction import Transaction
from app.services.user_service import create_user

pytestmark = pytest.mark.real_auth

PASSWORD = "Str0ng-pass-123"
PUBLIC_PATHS = {"/api/v1/auth/login", "/", "/health"}


@pytest.fixture(autouse=True)
async def seeded_db():
    await seed_database()
    yield
    await engine.dispose()


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _make_org(name: str) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        org = Organization(name=name, inn=f"{uuid.uuid4().int % 10**9:09d}")
        session.add(org)
        await session.flush()
        session.add(Transaction(
            organization_id=org.id, doc_number=f"TX-{name}", doc_date=date(2025, 3, 1), doc_type="BANK",
            debit_account="5110", credit_account="6000", total_amount=Decimal("1000.00"),
        ))
        await session.commit()
        return org.id


async def _make_user(role: UserRole = UserRole.CHIEF_ACCOUNTANT, orgs=(), superuser=False, active=True) -> str:
    username = f"u_{uuid.uuid4().hex[:10]}"
    async with AsyncSessionLocal() as session:
        user = await create_user(session, username=username, password=PASSWORD, role=role,
                                 is_superuser=superuser, organization_ids=orgs)
        user.is_active = active
        await session.commit()
    return username


async def _token(client: AsyncClient, username: str, password: str = PASSWORD) -> str:
    resp = await client.post("/api/v1/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------- authentication

@pytest.mark.asyncio
async def test_every_non_public_route_requires_a_token():
    paths = app.openapi()["paths"]
    failures = []
    async with _client() as client:
        for path, ops in paths.items():
            if path in PUBLIC_PATHS:
                continue
            concrete = path.replace("{org_id}", str(uuid.uuid4())).replace("{tx_id}", str(uuid.uuid4())) \
                .replace("{task_id}", "x").replace("{filename}", "x.json").replace("{format}", "excel") \
                .replace("{user_id}", str(uuid.uuid4()))
            for method in ops:
                resp = await client.request(method.upper(), concrete)
                if resp.status_code != 401:
                    failures.append(f"{method.upper()} {path} -> {resp.status_code}")
    assert not failures, failures


@pytest.mark.asyncio
async def test_login_returns_token_and_me_works():
    username = await _make_user(UserRole.OPERATOR)
    async with _client() as client:
        token = await _token(client, username)
        me = await client.get("/api/v1/auth/me", headers=_auth(token))
    assert me.status_code == 200
    assert me.json()["username"] == username
    assert me.json()["role"] == "OPERATOR"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["wrong-password", ""])
async def test_login_rejects_bad_password(bad):
    username = await _make_user()
    async with _client() as client:
        resp = await client.post("/api/v1/auth/login", data={"username": username, "password": bad})
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
async def test_login_unknown_user_and_inactive_user_get_same_error():
    inactive = await _make_user(active=False)
    async with _client() as client:
        unknown = await client.post("/api/v1/auth/login", data={"username": "nobody_x", "password": PASSWORD})
        blocked = await client.post("/api/v1/auth/login", data={"username": inactive, "password": PASSWORD})
    assert unknown.status_code == blocked.status_code == 401
    assert unknown.json()["detail"] == blocked.json()["detail"]


@pytest.mark.asyncio
async def test_login_is_throttled_after_repeated_failures():
    username = await _make_user()
    async with _client() as client:
        codes = [
            (await client.post("/api/v1/auth/login", data={"username": username, "password": "nope-nope"})).status_code
            for _ in range(6)
        ]
        # even the correct password is refused while blocked
        blocked = await client.post("/api/v1/auth/login", data={"username": username, "password": PASSWORD})
    assert codes[:5] == [401] * 5
    assert codes[5] == 429
    assert blocked.status_code == 429


@pytest.mark.asyncio
@pytest.mark.parametrize("token", [
    "not-a-jwt",
    create_access_token(str(uuid.uuid4())),  # unknown user id
    create_access_token(str(uuid.uuid4()), expires_delta=timedelta(seconds=-5)),
])
async def test_invalid_tokens_are_rejected(token):
    async with _client() as client:
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_signed_with_other_key_is_rejected():
    from jose import jwt
    forged = jwt.encode({"sub": str(uuid.uuid4()), "type": "access"}, "attacker-key" * 4, algorithm="HS256")
    async with _client() as client:
        resp = await client.get("/api/v1/auth/me", headers=_auth(forged))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_deactivated_user_token_stops_working():
    username = await _make_user(superuser=True)
    async with _client() as client:
        token = await _token(client, username)
        async with AsyncSessionLocal() as session:
            from sqlalchemy import update
            from app.models.user import User
            await session.execute(update(User).where(User.username == username).values(is_active=False))
            await session.commit()
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password():
    username = await _make_user()
    async with _client() as client:
        token = await _token(client, username)
        bad = await client.post("/api/v1/auth/change-password", headers=_auth(token),
                                json={"current_password": "wrong-one", "new_password": "N3w-password!"})
        ok = await client.post("/api/v1/auth/change-password", headers=_auth(token),
                               json={"current_password": PASSWORD, "new_password": "N3w-password!"})
        relogin = await client.post("/api/v1/auth/login", data={"username": username, "password": "N3w-password!"})
    assert bad.status_code == 400
    assert ok.status_code == 204
    assert relogin.status_code == 200


# ---------------------------------------------------------------- RBAC from token

@pytest.mark.asyncio
async def test_role_header_cannot_escalate_privileges():
    org = await _make_org("Header Test")
    username = await _make_user(UserRole.OPERATOR, orgs=[org])
    async with _client() as client:
        token = await _token(client, username)
        resp = await client.post(
            "/api/v1/backup/create",
            json={"organization_id": str(org)},
            headers={**_auth(token), "X-User-Role": "CHIEF_ACCOUNTANT"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_user_management_is_superuser_only():
    normal = await _make_user(UserRole.CHIEF_ACCOUNTANT)
    admin = await _make_user(superuser=True)
    async with _client() as client:
        normal_token = await _token(client, normal)
        admin_token = await _token(client, admin)
        denied = await client.get("/api/v1/auth/users", headers=_auth(normal_token))
        created = await client.post("/api/v1/auth/users", headers=_auth(admin_token), json={
            "username": f"new_{uuid.uuid4().hex[:6]}", "password": PASSWORD, "role": "AUDITOR",
        })
    assert denied.status_code == 403
    assert created.status_code == 201
    assert created.json()["role"] == "AUDITOR"


@pytest.mark.asyncio
async def test_factory_reset_requires_superuser():
    chief = await _make_user(UserRole.CHIEF_ACCOUNTANT)
    async with _client() as client:
        token = await _token(client, chief)
        resp = await client.post("/api/v1/system/factory-reset", headers=_auth(token), json={"confirmation": "TOZALASH"})
    assert resp.status_code == 403


# ---------------------------------------------------------------- tenancy

@pytest.fixture
async def two_tenants():
    org_a = await _make_org("Alpha")
    org_b = await _make_org("Beta")
    user_a = await _make_user(UserRole.CHIEF_ACCOUNTANT, orgs=[org_a])
    async with _client() as client:
        token_a = await _token(client, user_a)
    return org_a, org_b, token_a


@pytest.mark.asyncio
async def test_organization_list_only_shows_own_organizations(two_tenants):
    org_a, org_b, token_a = two_tenants
    async with _client() as client:
        ids = [o["id"] for o in (await client.get("/api/v1/organizations", headers=_auth(token_a))).json()]
    assert ids == [str(org_a)]


@pytest.mark.asyncio
@pytest.mark.parametrize("method, path_tpl", [
    ("GET", "/api/v1/organizations/{org}"),
    ("GET", "/api/v1/organizations/{org}/audit-logs"),
    ("PATCH", "/api/v1/organizations/{org}/lock-period"),
    ("GET", "/api/v1/reports/oborotka?organization_id={org}&from_date=2025-01-01&to_date=2025-12-31"),
    ("GET", "/api/v1/reports/dashboard?organization_id={org}"),
    ("GET", "/api/v1/reports/material-report?organization_id={org}&from_date=2025-01-01&to_date=2025-12-31"),
    ("GET", "/api/v1/counterparties?organization_id={org}"),
])
async def test_foreign_organization_is_invisible(two_tenants, method, path_tpl):
    org_a, org_b, token_a = two_tenants
    async with _client() as client:
        own = await client.request(method, path_tpl.format(org=org_a), headers=_auth(token_a), json={})
        foreign = await client.request(method, path_tpl.format(org=org_b), headers=_auth(token_a), json={})
    assert own.status_code != 404, own.text
    assert foreign.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("path, body", [
    ("/api/v1/documents/commit", {"file_id": "x.xlsx", "format_type": "DIDOX_EHF"}),
    ("/api/v1/documents/commit-parsed", {"records": []}),
    ("/api/v1/counterparties", {"name": "Evil", "inn": "123456789"}),
    ("/api/v1/backup/create", {}),
])
async def test_cannot_write_into_foreign_organization(two_tenants, path, body):
    org_a, org_b, token_a = two_tenants
    async with _client() as client:
        resp = await client.post(path, headers=_auth(token_a), json={**body, "organization_id": str(org_b)})
    assert resp.status_code == 404
    # must be rejected by the tenancy check, not by some later "file not found"
    assert resp.json()["detail"] == "Tashkilot topilmadi"


@pytest.mark.asyncio
async def test_created_organization_is_granted_to_creator(two_tenants):
    _, _, token_a = two_tenants
    async with _client() as client:
        created = await client.post("/api/v1/organizations", headers=_auth(token_a), json={
            "name": "Yangi MCHJ", "inn": f"{uuid.uuid4().int % 10**9:09d}", "mode": "BHMS", "vat_payer": True,
        })
        ids = [o["id"] for o in (await client.get("/api/v1/organizations", headers=_auth(token_a))).json()]
    assert created.status_code == 200
    assert created.json()["id"] in ids


@pytest.mark.asyncio
async def test_backup_listing_is_filtered_by_organization(two_tenants):
    org_a, org_b, token_a = two_tenants
    admin = await _make_user(superuser=True)
    async with _client() as client:
        admin_token = await _token(client, admin)
        await client.post("/api/v1/backup/create", headers=_auth(admin_token), json={"organization_id": str(org_b)})
        own = await client.post("/api/v1/backup/create", headers=_auth(token_a), json={"organization_id": str(org_a)})
        listing = (await client.get("/api/v1/backup/list", headers=_auth(token_a))).json()
        foreign_names = [b["filename"] for b in
                         (await client.get("/api/v1/backup/list", headers=_auth(admin_token))).json()
                         if b["organization_id"] == str(org_b)]
        foreign_verify = await client.get(f"/api/v1/backup/{foreign_names[0]}/verify", headers=_auth(token_a))
    assert own.status_code == 200
    assert {b["organization_id"] for b in listing} == {str(org_a)}
    assert foreign_verify.status_code == 404


@pytest.mark.asyncio
async def test_tasks_are_private_to_their_owner(two_tenants):
    from app.services.task_manager import task_manager
    _, _, token_a = two_tenants
    other = task_manager.create_task("someone else's import", owner_id=str(uuid.uuid4()))
    async with _client() as client:
        listing = (await client.get("/api/v1/tasks", headers=_auth(token_a))).json()
        direct = await client.get(f"/api/v1/tasks/{other.id}", headers=_auth(token_a))
    assert other.id not in [t["id"] for t in listing]
    assert direct.status_code == 404


@pytest.mark.asyncio
async def test_akt_sverka_rejects_counterparty_of_another_organization(two_tenants):
    """Security review H1: an accessible org id must not unlock a foreign counterparty."""
    from app.models.counterparty import Counterparty
    org_a, org_b, token_a = two_tenants
    async with AsyncSessionLocal() as session:
        foreign_cp = Counterparty(organization_id=org_b, name="Beta Maxfiy Hamkor", inn="777888999")
        session.add(foreign_cp)
        await session.commit()
        foreign_cp_id = foreign_cp.id
    async with _client() as client:
        resp = await client.get("/api/v1/reports/akt-sverka", headers=_auth(token_a), params={
            "organization_id": str(org_a), "counterparty_id": str(foreign_cp_id),
            "from_date": "2025-01-01", "to_date": "2025-12-31",
        })
    assert resp.status_code == 404
    assert "777888999" not in resp.text and "Maxfiy" not in resp.text


@pytest.mark.asyncio
async def test_superuser_can_demote_other_superuser_but_not_self():
    admin = await _make_user(superuser=True)
    other = await _make_user(superuser=True)
    async with _client() as client:
        token = await _token(client, admin)
        users = (await client.get("/api/v1/auth/users", headers=_auth(token))).json()
        ids = {u["username"]: u["id"] for u in users}
        demoted = await client.patch(f"/api/v1/auth/users/{ids[other]}", headers=_auth(token), json={"is_superuser": False})
        self_demote = await client.patch(f"/api/v1/auth/users/{ids[admin]}", headers=_auth(token), json={"is_superuser": False})
    assert demoted.status_code == 200
    assert demoted.json()["is_superuser"] is False
    assert self_demote.status_code == 400
